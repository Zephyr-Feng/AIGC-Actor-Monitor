"""Model-generated, explicitly fallible source relations before final audit."""
import json
import sys
import time
from pathlib import Path
from protocol import BASE, ROOT, obj, source_alignment, evidence_catalog, response_schema
from run import http, sha, validate
from experiments.actor_b.actor_b_protocol import extract_object
from experiments.faithbench_monitor_v0.pilot_v2.protocol import parse_response


def verification_input(packet):
    catalog = evidence_catalog(packet)
    bindings = source_alignment(packet)
    claims = []
    lookup = {}
    for i, step in enumerate(packet['trajectory']['steps']):
        if step.get('actor_output'):
            for j, claim in enumerate(step['actor_output'].get('current_evidence', [])):
                lookup[(step['step'], j, False)] = claim
    if packet['review_mode'] == 'call_prefix':
        latest = packet['current_action']['actor_request']
        latest_prefix = '/current_action/actor_request'
        for j, claim in enumerate(latest.get('current_evidence', [])):
            lookup[(packet['current_action']['step'], j, False)] = claim
    else:
        latest_prefix = '/trajectory/raw_final_output'
        latest = packet['trajectory']['raw_final_output']
        if not packet['trajectory']['raw_parse_valid']:
            latest_prefix = '/trajectory/raw_terminal_text'
            latest = extract_object(packet['trajectory']['raw_terminal_text'])
            for j, claim in enumerate(latest.get('current_evidence', [])):
                lookup[(packet['runtime_snapshot']['decision_step'], j, True)] = claim
    positions = {}
    used = set()
    for binding in bindings:
        key = (binding['decision_step'], binding['raw_retry_not_accepted'])
        j = positions.get(key, 0); positions[key] = j + 1
        claim = lookup[(key[0], j, key[1])]
        item = {**binding, 'claim_id': f'C{len(claims)+1:03d}', 'actor_claim': claim}
        claims.append(item)
        used.update(binding['claim_ids']); used.update(binding['source_card_ids'])
        for prior in binding['prior_returns']:
            used.update(prior['observation_ids']); used.update(prior['capability_ids'])
    synthesis_ids = [eid for eid, ref in catalog.items() if ref['pointer'] == latest_prefix or
                     any(ref['pointer'].startswith(latest_prefix+'/'+key) for key in ['action_reason','evidence_gap','unresolved_conflicts'])]
    used.update(synthesis_ids)
    # Exclude repeated raw JSON text from the pool: decoded claims/synthesis carry
    # exact text, and the original raw leaf remains a valid single citation.
    pool = {eid: ref for eid, ref in catalog.items() if eid in used and ref['pointer'] != '/trajectory/raw_terminal_text'}
    return {'claims': claims, 'latest_synthesis': {k: latest.get(k) for k in ['action_reason','evidence_gap','unresolved_conflicts']},
            'synthesis_reference_ids': synthesis_ids, 'source_pool': pool, 'images_supplied': False}


def verification_schema(data):
    text = {'type':'string','minLength':1}
    ids = list(data['source_pool']) + data['synthesis_reference_ids']
    refs = {'type':'array','items':{'type':'string','enum':list(dict.fromkeys(ids))}}
    relation = obj({'observation':{'type':'string','enum':['supported_by_source','not_returned_by_source','unassessable']},
                    'direction':{'type':'string','enum':['within_role','exceeds_role','unassessable']},
                    'reason':text,'reference_ids':refs})
    return obj({'claims':obj({item['claim_id']:relation for item in data['claims']}),
                'synthesis':obj({'status':{'type':'string','enum':['within_role','exceeds_role','unassessable']},
                                 'reason':text,'reference_ids':refs})})


def verifier_prompt(data):
    return (BASE/'claim_verifier.md').read_text(encoding='utf8')+'\n声明/此前来源与能力卡（待审核数据）：\n'+json.dumps(data,ensure_ascii=False)


def validate_verification(raw, data, packet):
    result = json.loads(raw)
    if set(result['claims']) != {c['claim_id'] for c in data['claims']}:
        raise ValueError('missing or additional claim')
    catalog = evidence_catalog(packet)
    for item in list(result['claims'].values())+[result['synthesis']]:
        if any(eid not in catalog for eid in item['reference_ids']):
            raise ValueError('unknown verification reference')
        violated = item.get('observation') == 'not_returned_by_source' or item.get('direction') == 'exceeds_role' or item.get('status') == 'exceeds_role'
        if violated and not item['reference_ids']:
            raise ValueError('unsupported verifier accusation')
    return result


def prepare(source, output):
    _, packets = validate(source)
    output.mkdir(parents=True, exist_ok=False)
    (output/'inputs.jsonl').write_bytes((source/'inputs.jsonl').read_bytes())
    for packet in packets:
        cid=packet['case_id']; data=verification_input(packet)
        (output/f'{cid}.verify_input.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        (output/f'{cid}.verify.txt').write_text(verifier_prompt(data),encoding='utf8')
        (output/f'{cid}.schema.json').write_text(json.dumps(response_schema(packet),ensure_ascii=False),encoding='utf8')
        (output/f'{cid}.original.txt').write_bytes((source/f'{cid}_request.txt').read_bytes())
    manifest={'case_ids':[p['case_id'] for p in packets], 'annotations_read':False, 'stages':2,
              'source_manifest_sha256':sha(source/'manifest.json'),
              'protocol_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in BASE.iterdir() if p.is_file()},
              'artifact_hashes':{p.name:sha(p) for p in output.iterdir() if p.is_file()}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'prepared_cases':len(packets),'manifest_sha256':sha(output/'manifest.json')}))


def generate(prompt, schema):
    native=http('/apply-template',{'messages':[{'role':'user','content':prompt}], 'add_generation_prompt':True,
                                   'chat_template_kwargs':{'enable_thinking':False}},20)['prompt']
    count=len(http('/tokenize',{'content':native,'add_special':False},20)['tokens'])
    if count+4096>24576: raise ValueError('stage context too large')
    result=http('/v1/chat/completions',{'messages':[{'role':'user','content':prompt}], 'temperature':0,'max_tokens':4096,
                 'seed':42,'repeat_penalty':1.05,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False},
                 'response_format':{'type':'json_object','schema':schema}})
    choice=result['choices'][0]
    return {'raw':choice['message']['content'],'usage':result['usage'],'finish_reason':choice['finish_reason'],
            'reasoning_content':choice['message'].get('reasoning_content'),'native_input_tokens':count,'timings':result.get('timings')}


def run(inputs, output):
    manifest=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for name,expected in manifest['artifact_hashes'].items():
        if sha(inputs/name)!=expected: raise ValueError('input changed: '+name)
    for name,expected in manifest['protocol_hashes'].items():
        if sha(ROOT/name)!=expected: raise ValueError('code changed: '+name)
    packets=list(map(json.loads,(inputs/'inputs.jsonl').read_text(encoding='utf8').splitlines()))
    output.mkdir(parents=True,exist_ok=False)
    (output/'runtime.json').write_text(json.dumps({'manifest_sha256':sha(inputs/'manifest.json'), 'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
       'model':'Qwen3.5-27B Q4_K_M','backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,
       'max_tokens_per_stage':4096,'thinking':False,'retries':0,'timeout_seconds':120,'actor_actions_executed':False,'annotations_read':False},indent=2))
    with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
        for i,packet in enumerate(packets,1):
            cid=packet['case_id']; data=json.loads((inputs/f'{cid}.verify_input.json').read_text(encoding='utf8'))
            row={'case_id':cid,'condition':'claim_then_audit'}
            for stage in ['verification','audit']:
                print(json.dumps({'event':'stage_start','case':i,'total':len(packets),'case_id':cid,'stage':stage,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
                start=time.monotonic()
                if stage=='verification': row['verification']={}
                try:
                    if stage=='verification':
                        result=generate((inputs/f'{cid}.verify.txt').read_text(encoding='utf8'),verification_schema(data))
                        row['verification']=result
                        verified=validate_verification(result['raw'],data,packet)
                        result['parse_valid']=True
                    else:
                        instruction=(BASE/'claim_aggregation.md').read_text(encoding='utf8')
                        prompt=(inputs/f'{cid}.original.txt').read_text(encoding='utf8')+'\n\n'+instruction+'\n机器核验记录（可被推翻，非原始证据）：\n'+json.dumps({'claim_index':data['claims'],'relations':verified},ensure_ascii=False)
                        result=generate(prompt,json.loads((inputs/f'{cid}.schema.json').read_text(encoding='utf8')))
                        row.update(result)
                        row.update(parse_valid=True,checked=parse_response(row['raw'],packet))
                except (ValueError,TypeError,KeyError) as exc:
                    if stage=='verification': row['verification'].update(parse_valid=False,parse_error=str(exc))
                    row.update(parse_valid=False,parse_error=stage+': '+str(exc))
                except Exception as exc:
                    row.update(parse_valid=False,request_error=stage+': '+type(exc).__name__+': '+str(exc))
                seconds=round(time.monotonic()-start,4)
                row[stage+'_seconds']=seconds
                print(json.dumps({'event':'stage_end','case':i,'stage':stage,'seconds':seconds,'error':row.get('parse_error',row.get('request_error'))}),flush=True)
                if row.get('request_error') or (stage=='verification' and not row['verification']['parse_valid']): break
            row['seconds']=sum(row.get(k+'_seconds',0) for k in ['verification','audit'])
            handle.write(json.dumps(row,ensure_ascii=False)+'\n'); handle.flush()
            if row.get('request_error'): raise RuntimeError('HTTP error; preserve partial output and inspect')
    print('Completed source relations and audits. No feedback executed.',flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--source',type=Path); parser.add_argument('--prepare',type=Path)
    parser.add_argument('--inputs',type=Path); parser.add_argument('--output',type=Path); args=parser.parse_args()
    if args.prepare: prepare(args.source,args.prepare)
    else: run(args.inputs,args.output)
