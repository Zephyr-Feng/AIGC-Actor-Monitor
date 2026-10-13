"""Bounded two-stage focused experiment; preserve every original stage output."""
import argparse
import json
import time
from pathlib import Path
from protocol import BASE,ROOT
from run import sha,validate,http
from claim_verify import generate
from focused import focused_input,focused_schema,validate_focused,relation_flags,final_schema,final_prompt,parse_focused


def prepare(source,target):
    _,packets=validate(source);target.mkdir(parents=True,exist_ok=False)
    (target/'inputs.jsonl').write_bytes((source/'inputs.jsonl').read_bytes())
    for p in packets:
        data=focused_input(p);cid=p['case_id']
        (target/f'{cid}.focused.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        prompt=(BASE/'focused_verifier.md').read_text(encoding='utf8')+'\n输入：\n'+json.dumps(data,ensure_ascii=False)
        (target/f'{cid}.verify.txt').write_text(prompt,encoding='utf8')
        (target/f'{cid}.verify.schema.json').write_text(json.dumps(focused_schema(data),ensure_ascii=False),encoding='utf8')
    manifest={'cases':[p['case_id'] for p in packets],'condition':'focused_contract_audit','source_manifest_sha256':sha(source/'manifest.json'),
              'protocol_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in BASE.iterdir() if p.is_file()},
              'artifact_hashes':{p.name:sha(p) for p in target.iterdir() if p.is_file()},'independent_test':False,'annotations_read':False}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'cases':len(packets),'manifest_sha256':sha(target/'manifest.json')}))


def run(inputs,output):
    manifest=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for n,h in manifest['artifact_hashes'].items():
        if sha(inputs/n)!=h:raise ValueError('input changed '+n)
    for n,h in manifest['protocol_hashes'].items():
        if sha(ROOT/n)!=h:raise ValueError('code changed '+n)
    packets=list(map(json.loads,(inputs/'inputs.jsonl').read_text(encoding='utf8').splitlines()))
    output.mkdir(parents=True,exist_ok=False)
    runtime={'manifest_sha256':sha(inputs/'manifest.json'),'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'model':'Qwen3.5-27B Q4_K_M',
             'backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,'max_tokens_per_stage':4096,'thinking':False,
             'timeout_seconds':120,'retries':0,'sft':False,'actor_actions_executed':False,'annotations_read':False}
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    preflight=[]
    for p in packets:
        prompt=(inputs/f"{p['case_id']}.verify.txt").read_text(encoding='utf8')
        native=http('/apply-template',{'messages':[{'role':'user','content':prompt}],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}},20)['prompt']
        count=len(http('/tokenize',{'content':native,'add_special':False},20)['tokens'])
        preflight.append({'case_id':p['case_id'],'native_input_tokens':count,'fits':count+4096<=24576})
    (output/'native_preflight.json').write_text(json.dumps(preflight,indent=2))
    if any(not r['fits'] for r in preflight):raise ValueError('context failure before requests')
    with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
        for i,p in enumerate(packets,1):
            cid=p['case_id'];data=json.loads((inputs/f'{cid}.focused.json').read_text(encoding='utf8'))
            row={'case_id':cid,'condition':'focused_contract_audit'}
            started=time.monotonic()
            print(json.dumps({'event':'verification_start','index':i,'total':len(packets),'case_id':cid,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
            try:
                if data['observation_atoms'] or data['conflict_slots']:
                    result=generate((inputs/f'{cid}.verify.txt').read_text(encoding='utf8'),json.loads((inputs/f'{cid}.verify.schema.json').read_text(encoding='utf8')))
                    row['verification']=result
                    verified=validate_focused(result['raw'],data);result['parse_valid']=True
                else:
                    verified={'observations':{},'conflicts':{}}
                    row['verification']={'skipped':True,'reason':'no_tool_source_atoms_or_conflicts_unknown_not_pass','parse_valid':True,
                                         'raw':json.dumps(verified),'usage':{'prompt_tokens':0,'completion_tokens':0}}
                row['verification_seconds']=round(time.monotonic()-started,4)
                (output/f'{cid}.verification.json').write_text(json.dumps(row['verification'],ensure_ascii=False,indent=2),encoding='utf8')
                print(json.dumps({'event':'verification_end','index':i,'seconds':row['verification_seconds'],'skipped':row['verification'].get('skipped',False)}),flush=True)
                flags=relation_flags(data,verified);row['flags']=flags
                prompt=final_prompt(p,data,verified,flags);schema=final_schema(p,flags)
                (output/f'{cid}.audit.txt').write_text(prompt,encoding='utf8')
                (output/f'{cid}.audit.schema.json').write_text(json.dumps(schema,ensure_ascii=False),encoding='utf8')
                print(json.dumps({'event':'audit_start','index':i,'flags':list(flags),'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
                started=time.monotonic();result=generate(prompt,schema);row['typed_raw']=result.pop('raw');row.update(result)
                simple,checked,code,dispositions=parse_focused(row['typed_raw'],p,flags)
                row.update(raw=json.dumps(simple,ensure_ascii=False),checked=checked,contract_records=code,relation_dispositions=dispositions,parse_valid=True)
            except (ValueError,TypeError,KeyError) as exc:row.update(parse_valid=False,parse_error=str(exc))
            except Exception as exc:row.update(parse_valid=False,request_error=type(exc).__name__+': '+str(exc))
            if 'verification_seconds' in row:row['audit_seconds']=round(time.monotonic()-started,4)
            else:
                row['verification_seconds']=round(time.monotonic()-started,4);row['audit_seconds']=0
                if 'verification' in row:
                    row['verification']['parse_valid']=False;row['verification']['parse_error']=row.get('parse_error',row.get('request_error'))
                    (output/f'{cid}.verification.json').write_text(json.dumps(row['verification'],ensure_ascii=False,indent=2),encoding='utf8')
            row['seconds']=row['verification_seconds']+row['audit_seconds']
            handle.write(json.dumps(row,ensure_ascii=False)+'\n');handle.flush()
            print(json.dumps({'event':'case_end','index':i,'valid':row['parse_valid'],'seconds':row['seconds'],'error':row.get('parse_error',row.get('request_error'))}),flush=True)
            if row.get('request_error'):raise RuntimeError('HTTP error; inspect before further requests')
    runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z');(output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    print('Completed focused audit. No Actor actions executed.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);parser.add_argument('--prepare',type=Path)
    parser.add_argument('--inputs',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.prepare:prepare(args.source,args.prepare)
    else:run(args.inputs,args.output)
