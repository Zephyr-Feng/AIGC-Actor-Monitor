"""Nine existing atoms in a paired 2x2 prompt diagnostic; no training."""
import argparse,copy,json,os,time
from pathlib import Path
import controlled_claims as c
import typed_source_portable as t
from typed_source_factors import prompt
from prepare_reasoned_portable import dump

NAMES=['terminal_0041_A010','terminal_0005_A006','terminal_0005_A007',
       'terminal_0001_A005','terminal_0001_A006','terminal_0001_A007',
       'terminal_0001_A009','terminal_0041_A006','terminal_0041_A006_missing_list']
FACTORS=[('C00',False,False),('C10',True,False),('C01',False,True),('C11',True,True)]

def validate(inputs):
    m=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for name,h in m['artifact_hashes'].items():
        if c.sha(inputs/name)!=h:raise ValueError('input changed '+name)
    for name,h in m['protocol_hashes'].items():
        if c.sha(c.ROOT/name)!=h:raise ValueError('protocol changed '+name)
    return m

def prepare(source,target):
    if c.sha(source/'manifest.json')!='2208d958872dcd157749d322ff0d6f50ad75f1750f8456c8037ef7a1be296e04':
        raise ValueError('wrong parent')
    parent=validate(source)
    originals={r['name']:r for r in json.loads((source/'records.json').read_text(encoding='utf8'))};rows=[]
    target.mkdir(parents=True,exist_ok=False)
    for index,name in enumerate(NAMES):
        block=FACTORS[index%4:]+FACTORS[:index%4]
        for condition,scope,state in block:
            row=copy.deepcopy(originals[name]);row.update(name=name+'__'+condition,base_name=name,
                 condition=condition,restore_scope=scope,clarify_state=state)
            data=row['data'];rows.append(row)
            (target/(row['name']+'.txt')).write_bytes(prompt(data,scope,state).encode('utf8'))
            dump(target/(row['name']+'.schema.json'),t.schema(data))
    dump(target/'records.json',rows);deps=dict(parent['protocol_hashes'])
    for name in ['typed_source_scoped.py','typed_source_factors.py','typed_source_factor_probe.py','PLAN_TYPED_SOURCE_FACTORS_20261010.md','PLAN_TYPED_SOURCE_FACTORS_RUN_20261010.md']:
        deps[(c.BASE/name).relative_to(c.ROOT).as_posix()]=c.sha(c.BASE/name)
    dump(target/'manifest.json',{'condition':'typed_source_two_factors','parent_manifest_sha256':c.sha(source/'manifest.json'),
        'schedule':[{k:r[k] for k in ['name','base_name','kind','condition','restore_scope','clarify_state']} for r in rows],
        'protocol_hashes':deps,'artifact_hashes':{p.name:c.sha(p) for p in sorted(target.iterdir())},
        'model':parent['model'],'backend':parent['backend'],'targets_read':False,'independent_test':False,
        'sft':False,'actor_actions_executed':False})
    print(json.dumps({'requests':len(rows),'manifest_sha256':c.sha(target/'manifest.json')}))

def run(inputs,output):
    from run import http
    from run_compact import native_count
    m=validate(inputs);rows=json.loads((inputs/'records.json').read_text(encoding='utf8'))
    if [r['name'] for r in rows]!=[s['name'] for s in m['schedule']] or len(rows)!=36:
        raise ValueError('wrong schedule')
    lock=output.parent/'controlled_claims.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    try:
        output.mkdir(exist_ok=False,parents=True)
        counts=[{'name':r['name'],'input_tokens':native_count((inputs/(r['name']+'.txt')).read_text(encoding='utf8'))} for r in rows]
        dump(output/'native_preflight.json',counts)
        if any(r['input_tokens']+4096>24576 for r in counts):raise ValueError('context overflow')
        runtime={'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'manifest_sha256':c.sha(inputs/'manifest.json'),
                 'temperature':0,'seed':42,'repeat_penalty':1.05,'max_tokens':4096,'timeout_seconds':120,'retries':0,
                 'model':m['model'],'backend':m['backend'],'sft':False,'actor_actions_executed':False,'targets_read':False}
        dump(output/'runtime.json',runtime)
        with (output/'responses.jsonl').open('x',encoding='utf8') as f:
            for index,row in enumerate(rows,1):
                name=row['name'];data=row['data'];start=time.monotonic()
                inflight={'index':index,'name':name,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
                (output/'inflight.json').write_text(json.dumps(inflight),encoding='utf8')
                print(json.dumps({'event':'start',**inflight}),flush=True)
                body={'messages':[{'role':'user','content':(inputs/(name+'.txt')).read_text(encoding='utf8')}],
                      'temperature':0,'seed':42,'repeat_penalty':1.05,'max_tokens':4096,'cache_prompt':False,
                      'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object','schema':t.schema(data)}}
                dump(output/(name+'.request.json'),body)
                result={k:row[k] for k in ['name','base_name','kind','condition','restore_scope','clarify_state']}
                try:
                    response=http('/v1/chat/completions',body);dump(output/(name+'.http.json'),response)
                    choice=response['choices'][0]
                    result.update(raw=choice['message']['content'],finish_reason=choice['finish_reason'],usage=response['usage'])
                    try:json.loads(result['raw']);result['raw_json_valid']=True
                    except ValueError:result['raw_json_valid']=False
                    try:result.update(t.parse(result['raw'],data),parse_valid=True)
                    except (ValueError,TypeError):result.update(parse_valid=False,error='invalid_output')
                except Exception as exc:result.update(parse_valid=False,request_error=type(exc).__name__+': '+str(exc))
                result['seconds']=round(time.monotonic()-start,4)
                dump(output/(name+'.response.json'),result);f.write(json.dumps(result,ensure_ascii=False)+'\n');f.flush()
                print(json.dumps({'event':'end','index':index,'valid':result['parse_valid'],'seconds':result['seconds']}),flush=True)
                if 'request_error' in result:raise RuntimeError('HTTP failure; inspect before continuation')
        runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
        (output/'runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
        (output/'inflight.json').unlink()
    finally:lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--prepare',type=Path)
    p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.prepare:prepare(a.source,a.prepare)
    else:run(a.inputs,a.output)
