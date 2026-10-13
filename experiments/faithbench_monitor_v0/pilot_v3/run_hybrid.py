"""Frozen contract hybrid pilot and paired unseen-input development comparison."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from protocol import BASE, ROOT, render_request, response_schema
from run import sha, validate, http
from claim_verify import generate
from hybrid import hybrid_schema, hybrid_prompt, parse_hybrid, contract_records
from experiments.faithbench_monitor_v0.pilot_v2.protocol import render_request as render_v2, parse_response
from experiments.faithbench_monitor_v0.pilot_v1.pilot_protocol import enrich_packet


def prepare(source,output):
    _,pilot=validate(source)
    original=BASE.parent/'private/inputs.jsonl'
    if sha(original)!='1afce6d06564622c176797466dde6ddfdcef9364d25f2d60bd1e8799f8ce8bb5':raise ValueError('dev source changed')
    pool=[p for p in map(json.loads,original.read_text(encoding='utf8').splitlines()) if p['review_mode']=='terminal']
    excluded={p['case_id'] for p in pilot};selected=[]
    for block in range(4):
        candidates=[p for p in pool if 20*block<int(p['case_id'].split('_')[1])<=20*(block+1) and p['case_id'] not in excluded]
        candidates.sort(key=lambda p:hashlib.sha256(('monitor-transfer-20261010:'+p['case_id']).encode()).hexdigest())
        selected.extend(enrich_packet(p) for p in candidates[:3])
    output.mkdir(parents=True,exist_ok=False)
    packets=pilot+selected
    (output/'inputs.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in packets),encoding='utf8')
    schedule=[{'case_id':p['case_id'],'condition':'contract_hybrid','phase':'eight_regression'} for p in pilot]
    for i,p in enumerate(selected):
        for condition in (['schema_control','contract_hybrid'] if i%2==0 else ['contract_hybrid','schema_control']):
            schedule.append({'case_id':p['case_id'],'condition':condition,'phase':'new_input_transfer'})
    lookup={p['case_id']:p for p in packets}
    for item in schedule:
        p=lookup[item['case_id']];name=item['case_id']+'_'+item['condition']
        prompt=hybrid_prompt(p) if item['condition']=='contract_hybrid' else render_v2(p)
        schema=hybrid_schema(p) if item['condition']=='contract_hybrid' else response_schema(p)
        (output/f'{name}.txt').write_text(prompt,encoding='utf8')
        (output/f'{name}.schema.json').write_text(json.dumps(schema,ensure_ascii=False),encoding='utf8')
    manifest={'schedule':schedule,'transfer_case_ids':[p['case_id'] for p in selected],'selection':'3 per 20-case condition block, salted SHA order, exclude original 5 terminals',
              'source_sha256':sha(original),'annotations_read':False,'independent_test':False,
              'protocol_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in BASE.iterdir() if p.is_file()},
              'artifact_hashes':{p.name:sha(p) for p in output.iterdir() if p.is_file()}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'requests':len(schedule),'transfer_case_ids':manifest['transfer_case_ids'],'manifest_sha256':sha(output/'manifest.json')}))


def run(inputs,output):
    manifest=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for name,expected in manifest['artifact_hashes'].items():
        if sha(inputs/name)!=expected:raise ValueError('input changed: '+name)
    for name,expected in manifest['protocol_hashes'].items():
        if sha(ROOT/name)!=expected:raise ValueError('code changed: '+name)
    packets={p['case_id']:p for p in map(json.loads,(inputs/'inputs.jsonl').read_text(encoding='utf8').splitlines())}
    output.mkdir(parents=True,exist_ok=False)
    runtime={'manifest_sha256':sha(inputs/'manifest.json'),'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
             'model':'Qwen3.5-27B Q4_K_M','backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,
             'max_tokens':4096,'thinking':False,'retries':0,'timeout_seconds':120,'actor_actions_executed':False,'annotations_read':False}
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    preflight=[]
    for item in manifest['schedule']:
        name=item['case_id']+'_'+item['condition'];prompt=(inputs/f'{name}.txt').read_text(encoding='utf8')
        native=http('/apply-template',{'messages':[{'role':'user','content':prompt}],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}},20)['prompt']
        count=len(http('/tokenize',{'content':native,'add_special':False},20)['tokens'])
        preflight.append({**item,'native_input_tokens':count,'fits':count+4096<=24576})
    (output/'native_preflight.json').write_text(json.dumps(preflight,indent=2))
    if any(not p['fits'] for p in preflight):raise ValueError('context failure before inference; no silent replacement')
    print(json.dumps({'preflight':len(preflight),'max_input_tokens':max(p['native_input_tokens'] for p in preflight)}),flush=True)
    with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
        for i,item in enumerate(manifest['schedule'],1):
            print(json.dumps({'event':'request_start','index':i,'total':len(manifest['schedule']),**item,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
            start=time.monotonic();row={**item};p=packets[item['case_id']];name=item['case_id']+'_'+item['condition']
            try:
                result=generate((inputs/f'{name}.txt').read_text(encoding='utf8'),json.loads((inputs/f'{name}.schema.json').read_text(encoding='utf8')))
                if item['condition']=='contract_hybrid':
                    row['typed_raw']=result.pop('raw');row.update(result)
                    simple,checked,records=parse_hybrid(row['typed_raw'],p)
                    row.update(raw=json.dumps(simple,ensure_ascii=False),checked=checked,contract_records=records,parse_valid=True)
                else:
                    row.update(result);row.update(parse_valid=True,checked=parse_response(row['raw'],p))
            except (ValueError,TypeError,KeyError) as exc:row.update(parse_valid=False,parse_error=str(exc))
            except Exception as exc:row.update(parse_valid=False,request_error=type(exc).__name__+': '+str(exc))
            row['seconds']=round(time.monotonic()-start,4)
            handle.write(json.dumps(row,ensure_ascii=False)+'\n');handle.flush()
            print(json.dumps({'event':'request_end','index':i,'valid':row['parse_valid'],'seconds':row['seconds'],'error':row.get('parse_error',row.get('request_error'))}),flush=True)
            if row.get('request_error'):raise RuntimeError('HTTP error: inspect before further requests')
    runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    print('Completed regression and paired transfer. No Actor actions executed.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);parser.add_argument('--prepare',type=Path)
    parser.add_argument('--inputs',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.prepare:prepare(args.source,args.prepare)
    else:run(args.inputs,args.output)
