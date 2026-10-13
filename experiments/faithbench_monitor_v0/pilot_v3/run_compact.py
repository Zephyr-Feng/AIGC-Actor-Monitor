"""Two-stage length preflight and bounded compact audit, stop on stage failure."""
import argparse,json,time
from pathlib import Path
from protocol import BASE,ROOT
from run import sha,validate,http
from claim_verify import generate
from compact import focused_input,compact_schema,compile_relations,relation_flags,final_schema,final_prompt,parse_focused,verifier_prompt,planning_prompt


def prepare(source,target):
    _,packets=validate(source);target.mkdir(parents=True,exist_ok=False)
    (target/'inputs.jsonl').write_bytes((source/'inputs.jsonl').read_bytes())
    for p in packets:
        data=focused_input(p);cid=p['case_id']
        (target/f'{cid}.focused.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
        (target/f'{cid}.verify.txt').write_text(verifier_prompt(data),encoding='utf8')
        (target/f'{cid}.verify.schema.json').write_text(json.dumps(compact_schema(data),ensure_ascii=False),encoding='utf8')
    manifest={'cases':[p['case_id'] for p in packets],'condition':'compact_focused_audit','source_manifest_sha256':sha(source/'manifest.json'),
        'protocol_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in BASE.iterdir() if p.is_file()},
        'artifact_hashes':{p.name:sha(p) for p in target.iterdir() if p.is_file()},'independent_test':False,'annotations_read':False}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'cases':len(packets),'manifest_sha256':sha(target/'manifest.json')}))


def native_count(prompt):
    native=http('/apply-template',{'messages':[{'role':'user','content':prompt}],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}},20)['prompt']
    return len(http('/tokenize',{'content':native,'add_special':False},20)['tokens'])


def run(inputs,output,preflight_only=False):
    manifest=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for n,h in manifest['artifact_hashes'].items():
        if sha(inputs/n)!=h:raise ValueError('input changed '+n)
    for n,h in manifest['protocol_hashes'].items():
        if sha(ROOT/n)!=h:raise ValueError('code changed '+n)
    packets=list(map(json.loads,(inputs/'inputs.jsonl').read_text(encoding='utf8').splitlines()));output.mkdir(parents=True,exist_ok=False)
    preflight=[]
    for p in packets:
        data=json.loads((inputs/f"{p['case_id']}.focused.json").read_text(encoding='utf8'))
        verify_count=native_count((inputs/f"{p['case_id']}.verify.txt").read_text(encoding='utf8'))
        static_count=native_count(planning_prompt(p,data))
        preflight.append({'case_id':p['case_id'],'native_verify_tokens':verify_count,'native_final_static_tokens':static_count,
                          'reserved_dynamic_and_output_tokens':10240,'fits':verify_count+4096<=24576 and static_count+10240<=24576})
    (output/'native_preflight.json').write_text(json.dumps(preflight,indent=2))
    print(json.dumps({'event':'preflight','cases':len(preflight),'all_fit':all(r['fits'] for r in preflight),'max_static_tokens':max(r['native_final_static_tokens'] for r in preflight)}),flush=True)
    if any(not r['fits'] for r in preflight):raise ValueError('two-stage context failure before inference')
    if preflight_only:return
    runtime={'manifest_sha256':sha(inputs/'manifest.json'),'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'model':'Qwen3.5-27B Q4_K_M',
        'backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,'max_tokens_per_stage':4096,'thinking':False,
        'timeout_seconds':120,'retries':0,'sft':False,'actor_actions_executed':False,'annotations_read':False}
    (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
        for i,p in enumerate(packets,1):
            cid=p['case_id'];data=json.loads((inputs/f'{cid}.focused.json').read_text(encoding='utf8'));row={'case_id':cid,'condition':'compact_focused_audit'}
            start=time.monotonic();stage='verification'
            print(json.dumps({'event':'verification_start','index':i,'total':len(packets),'case_id':cid,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
            try:
                if data['observation_atoms'] or data['conflict_slots']:
                    result=generate((inputs/f'{cid}.verify.txt').read_text(encoding='utf8'),json.loads((inputs/f'{cid}.verify.schema.json').read_text(encoding='utf8')))
                    row['verification']=result;verified=compile_relations(result['raw'],data);result['parse_valid']=True
                else:
                    verified={'observations':{},'conflicts':{}}
                    row['verification']={'skipped':True,'reason':'no_tool_source_atoms_or_conflicts_unknown_not_pass','parse_valid':True,
                        'raw':json.dumps(verified),'usage':{'prompt_tokens':0,'completion_tokens':0}}
                row['compiled_relations']=verified;row['verification_seconds']=round(time.monotonic()-start,4)
                (output/f'{cid}.verification.json').write_text(json.dumps(row['verification'],ensure_ascii=False,indent=2),encoding='utf8')
                flags=relation_flags(data,verified);row['flags']=flags
                prompt=final_prompt(p,data,verified,flags);schema=final_schema(p,flags)
                (output/f'{cid}.audit.txt').write_text(prompt,encoding='utf8');(output/f'{cid}.audit.schema.json').write_text(json.dumps(schema,ensure_ascii=False),encoding='utf8')
                print(json.dumps({'event':'audit_start','index':i,'flags':list(flags),'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
                stage='audit';start=time.monotonic();result=generate(prompt,schema);row['typed_raw']=result.pop('raw');row.update(result)
                simple,checked,code,dispositions=parse_focused(row['typed_raw'],p,flags)
                row.update(raw=json.dumps(simple,ensure_ascii=False),checked=checked,contract_records=code,relation_dispositions=dispositions,parse_valid=True)
            except (ValueError,TypeError,KeyError) as exc:row.update(parse_valid=False,parse_error=stage+': '+str(exc))
            except Exception as exc:row.update(parse_valid=False,request_error=stage+': '+type(exc).__name__+': '+str(exc))
            if stage=='audit':row['audit_seconds']=round(time.monotonic()-start,4)
            else:
                row['verification_seconds']=round(time.monotonic()-start,4);row['audit_seconds']=0
                if 'verification' in row:
                    row['verification'].update(parse_valid=False,parse_error=row.get('parse_error',row.get('request_error')))
                    (output/f'{cid}.verification.json').write_text(json.dumps(row['verification'],ensure_ascii=False,indent=2),encoding='utf8')
            row['seconds']=row['verification_seconds']+row['audit_seconds'];handle.write(json.dumps(row,ensure_ascii=False)+'\n');handle.flush()
            print(json.dumps({'event':'case_end','index':i,'valid':row['parse_valid'],'seconds':row['seconds'],'error':row.get('parse_error',row.get('request_error'))}),flush=True)
            if not row['parse_valid']:raise RuntimeError('failed stage; preserve and inspect before further cases')
    runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z');(output/'runtime.json').write_text(json.dumps(runtime,indent=2))
    print('Completed compact audit. No Actor actions executed.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);parser.add_argument('--prepare',type=Path)
    parser.add_argument('--inputs',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--preflight-only',action='store_true');args=parser.parse_args()
    if args.prepare:prepare(args.source,args.prepare)
    else:run(args.inputs,args.output,args.preflight_only)
