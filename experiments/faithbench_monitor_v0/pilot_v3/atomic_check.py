"""Atomic source fragments plus one authoritative record per audit check."""
import copy
import json
import re
import time
from pathlib import Path
from protocol import BASE, ROOT, obj, evidence_catalog, applicable_checks, response_schema
from run import sha, validate
from claim_verify import verification_input, generate
from experiments.faithbench_monitor_v0.pilot_v2.protocol import parse_response, render_request
from experiments.faithbench_monitor_v0.monitor_protocol import FAILURE_TYPES


def atomic_input(packet):
    data = verification_input(packet)
    grouped = {}
    visual = []
    for claim in data['claims']:
        if claim['source'] == 'visual':
            visual.extend(claim['claim_ids']); continue
        key = json.dumps({'actor_claim':claim['actor_claim'],'prior_returns':claim['prior_returns']},sort_keys=True,ensure_ascii=False)
        if key in grouped:
            grouped[key]['claim_ids'].extend(claim['claim_ids'])
        else:
            value=copy.deepcopy(claim)
            value.pop('pixels_supplied_to_monitor',None);value.pop('raw_retry_not_accepted',None)
            grouped[key]=value
    claims=[]; atoms=[]
    for claim in grouped.values():
        claim['claim_id']=f'C{len(claims)+1:03d}'
        claim['claim_ids']=list(dict.fromkeys(claim['claim_ids']))
        # Conservative mechanical fragments. No named-entity model or truth label.
        pieces=[p.strip() for p in re.split(r'[，。；（）(),;]',claim['actor_claim'].get('observation','')) if p.strip()]
        for piece in pieces:
            atoms.append({'atom_id':f'A{len(atoms)+1:03d}','claim_id':claim['claim_id'],'text':piece,
                          'claim_reference_ids':claim['claim_ids'],'prior_returns':claim['prior_returns'],
                          'source_card_ids':claim['source_card_ids']})
        claims.append(claim)
    used=set(data['synthesis_reference_ids'])
    for claim in claims:
        used.update(claim['claim_ids']);used.update(claim['source_card_ids'])
        for p in claim['prior_returns']:used.update(p['observation_ids']);used.update(p['capability_ids'])
    return {'claims':claims,'observation_atoms':atoms,'latest_synthesis':data['latest_synthesis'],
            'synthesis_reference_ids':data['synthesis_reference_ids'],
            'source_pool':{eid:ref for eid,ref in data['source_pool'].items() if eid in used},
            'visual_text_audit':{'status':'unassessable','original_reference_ids':list(dict.fromkeys(visual)),
                               'reason':'Monitor未取得像素，无法核查Actor自己的视觉陈述；这不表示Actor没有图像，不能对其视觉内容判错。'}}


def atomic_schema(data):
    text={'type':'string','minLength':1}
    ids=set(data['source_pool']) | set(data['synthesis_reference_ids'])
    refs={'type':'array','items':{'type':'string','enum':sorted(ids)}}
    def relation(states):
        return obj({'status':{'type':'string','enum':states},'reason':text,'reference_ids':refs})
    return obj({'observations':obj({a['atom_id']:relation(['supported_by_source','not_returned_by_source','unassessable']) for a in data['observation_atoms']}),
                'interpretations':obj({c['claim_id']:relation(['within_role','exceeds_role','unassessable']) for c in data['claims']}),
                'synthesis':relation(['within_role','exceeds_role','unassessable'])})


def validate_atomic(raw,data,packet):
    result=json.loads(raw)
    if set(result['observations'])!={a['atom_id'] for a in data['observation_atoms']} or set(result['interpretations'])!={c['claim_id'] for c in data['claims']}:
        raise ValueError('incomplete atomic coverage')
    catalog=evidence_catalog(packet)
    for value in list(result['observations'].values())+list(result['interpretations'].values())+[result['synthesis']]:
        if any(eid not in catalog for eid in value['reference_ids']):raise ValueError('unknown reference')
        if value['status'] in ['not_returned_by_source','exceeds_role'] and not value['reference_ids']:raise ValueError('uncited accusation')
    return result


def typed_schema(packet):
    original=response_schema(packet)
    refs=original['properties']['proposal']['properties']['reference_ids']
    records={}
    for key in applicable_checks(packet):
        status=original['properties']['checks']['properties'][key]
        if packet['review_mode']=='terminal' and not packet['trajectory']['raw_parse_valid'] and key in ['verdict_supported','verdict_inconsistency']:
            status={'type':'string','enum':['unassessable']}
        records[key]=obj({'status':status,'reason':{'type':'string','minLength':1},'reference_ids':refs})
    return obj({'check_records':obj(records),'proposal':original['properties']['proposal']})


def parse_typed(raw,packet):
    result=json.loads(raw);records=result['check_records']
    if set(records)!=set(applicable_checks(packet)):raise ValueError('wrong check scope')
    checks={k:v['status'] for k,v in records.items()}
    findings=[{'failure_type':k,'assessment':'violated' if v['status']=='fail' else 'unassessable',
               'explanation':v['reason'],'reference_ids':v['reference_ids']}
              for k,v in records.items() if k in FAILURE_TYPES and v['status']!='pass']
    uncertainties=[v['reason'] for v in records.values() if v['status']=='unassessable']
    simplified={'checks':checks,'findings':findings,'uncertainties':uncertainties,'proposal':result['proposal']}
    return simplified,parse_response(json.dumps(simplified,ensure_ascii=False),packet)


def audit_prompt(packet,data,verified):
    # Keep all original visible evidence; change output instruction only.
    original=render_request(packet)
    marker='代码计算的审核范围与执行条件'
    visible=original[original.index(marker):]
    guidelines=(BASE.parent/'ANNOTATION_GUIDELINES.md').read_text(encoding='utf8')
    limits={'review_mode':packet['review_mode'],'remaining_calls':packet['runtime_snapshot']['budget']['remaining_before'],
            'raw_parse_valid':packet['trajectory'].get('raw_parse_valid'),'visual_status':data['visual_text_audit']}
    return '\n\n'.join([(BASE/'typed_audit.md').read_text(encoding='utf8'),guidelines,
                         '代码边界：'+json.dumps(limits,ensure_ascii=False),visible,
                         '机器来源核验（非独立证据，可推翻）：'+json.dumps({'claims':data['claims'],'atoms':data['observation_atoms'],'relations':verified},ensure_ascii=False)])


def prepare(source,output):
    _,packets=validate(source)
    output.mkdir(parents=True,exist_ok=False)
    (output/'inputs.jsonl').write_bytes((source/'inputs.jsonl').read_bytes())
    for packet in packets:
        data=atomic_input(packet);cid=packet['case_id']
        (output/f'{cid}.atomic.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
    manifest={'case_ids':[p['case_id'] for p in packets],'annotations_read':False,'stages':2,
              'source_manifest_sha256':sha(source/'manifest.json'),
              'protocol_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in BASE.iterdir() if p.is_file()},
              'artifact_hashes':{p.name:sha(p) for p in output.iterdir() if p.is_file()}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'prepared_cases':len(packets),'manifest_sha256':sha(output/'manifest.json')}))


def run(inputs,output):
    manifest=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for name,expected in manifest['artifact_hashes'].items():
        if sha(inputs/name)!=expected:raise ValueError('input changed: '+name)
    for name,expected in manifest['protocol_hashes'].items():
        if sha(ROOT/name)!=expected:raise ValueError('code changed: '+name)
    packets=list(map(json.loads,(inputs/'inputs.jsonl').read_text(encoding='utf8').splitlines()))
    output.mkdir(parents=True,exist_ok=False)
    runtime={'manifest_sha256':sha(inputs/'manifest.json'),'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
             'model':'Qwen3.5-27B Q4_K_M','backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,
             'max_tokens_per_stage':4096,'thinking':False,'retries':0,'timeout_seconds':120,'actor_actions_executed':False,'annotations_read':False}
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
        for i,packet in enumerate(packets,1):
            cid=packet['case_id'];data=json.loads((inputs/f'{cid}.atomic.json').read_text(encoding='utf8'))
            row={'case_id':cid,'condition':'atomic_typed_audit'}
            print(json.dumps({'event':'verification_start','case':i,'total':len(packets),'case_id':cid,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
            start=time.monotonic()
            try:
                if data['claims']:
                    prompt=(BASE/'atomic_verifier.md').read_text(encoding='utf8')+'\n工具声明及实际返回：\n'+json.dumps(data,ensure_ascii=False)
                    result=generate(prompt,atomic_schema(data));row['verification']=result
                    verified=validate_atomic(result['raw'],data,packet)
                    result['parse_valid']=True
                else:
                    verified={'observations':{},'interpretations':{},'synthesis':{'status':'unassessable','reason':'尚无取证工具来源声明；不将跳过当通过。','reference_ids':data['synthesis_reference_ids']}}
                    row['verification']={'skipped':True,'reason':'no_tool_source_claim','parse_valid':True,'raw':json.dumps(verified,ensure_ascii=False),'usage':{'prompt_tokens':0,'completion_tokens':0}}
                row['verification_seconds']=round(time.monotonic()-start,4)
                # Persist each stage before aggregation; partial verifier output survives a failed request.
                (output/f'{cid}.verification.json').write_text(json.dumps(row['verification'],ensure_ascii=False,indent=2),encoding='utf8')
                print(json.dumps({'event':'verification_end','case':i,'seconds':row['verification_seconds'],'skipped':row['verification'].get('skipped',False)}),flush=True)
                print(json.dumps({'event':'audit_start','case':i,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
                start=time.monotonic()
                result=generate(audit_prompt(packet,data,verified),typed_schema(packet));row['typed_raw']=result.pop('raw')
                row.update(result)
                simple,checked=parse_typed(row['typed_raw'],packet)
                row.update(raw=json.dumps(simple,ensure_ascii=False),parse_valid=True,checked=checked)
            except (ValueError,TypeError,KeyError) as exc:
                row.update(parse_valid=False,parse_error=str(exc))
            except Exception as exc:
                row.update(parse_valid=False,request_error=type(exc).__name__+': '+str(exc))
            row['audit_seconds']=round(time.monotonic()-start,4) if 'verification_seconds' in row else 0
            row['seconds']=row.get('verification_seconds',round(time.monotonic()-start,4))+row['audit_seconds']
            handle.write(json.dumps(row,ensure_ascii=False)+'\n');handle.flush()
            print(json.dumps({'event':'case_end','case':i,'valid':row['parse_valid'],'seconds':row['seconds'],'error':row.get('parse_error',row.get('request_error'))}),flush=True)
            if row.get('request_error'):raise RuntimeError('HTTP failed; inspect server before continuing')
    runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    print('Completed atomic and typed audits. No Actor actions executed.',flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);parser.add_argument('--prepare',type=Path)
    parser.add_argument('--inputs',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.prepare:prepare(args.source,args.prepare)
    else:run(args.inputs,args.output)
