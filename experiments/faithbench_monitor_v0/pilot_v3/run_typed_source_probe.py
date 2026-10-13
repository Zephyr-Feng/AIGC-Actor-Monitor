"""Bounded existing-model probe; no training, retries or Actor actions."""
import argparse,json,os,time
from pathlib import Path
import controlled_claims as c
import typed_source_portable as t
from prepare_reasoned_portable import dump

def run(inputs,output):
    from run import http
    from run_compact import native_count
    m=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
    for name,h in m['artifact_hashes'].items():
        if c.sha(inputs/name)!=h:raise ValueError('input changed '+name)
    for name,h in m['protocol_hashes'].items():
        if c.sha(c.ROOT/name)!=h:raise ValueError('protocol changed '+name)
    rows=json.loads((inputs/'records.json').read_text(encoding='utf8'))
    if [r['name'] for r in rows]!=[s['name'] for s in m['schedule']] or len(rows)!=13:
        raise ValueError('wrong schedule')
    lock=output.parent/'controlled_claims.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    try:
        output.mkdir(exist_ok=False,parents=True)
        counts=[{'name':row['name'],'input_tokens':native_count((inputs/(row['name']+'.txt')).read_text(encoding='utf8'))} for row in rows]
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
                result={'name':name,'kind':row['kind']}
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
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.inputs,args.output)
