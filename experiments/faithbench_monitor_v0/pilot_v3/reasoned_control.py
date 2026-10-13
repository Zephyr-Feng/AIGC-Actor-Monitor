"""Six deterministic probes from already deployed R9 source fixtures."""
import argparse,copy,json,random,time
from pathlib import Path
import controlled_claims as c
BASE=c.BASE;ROOT=c.ROOT
SCHEMA=copy.deepcopy(c.SCHEMA)
SCHEMA['properties']['reason']={'type':'string','minLength':1};SCHEMA['required'].append('reason')
def fixtures(source):
 prior={f['fixture_id']:f for f in json.loads((source/'fixtures.json').read_text(encoding='utf8'))};fs=[]
 for keep_num,keep_scope in [(True,True),(True,False),(False,True),(False,False)]:
  f=copy.deepcopy(prior['F005'])
  if not keep_num:f['source_return']['observations'].pop('num_atypical_regions')
  if not keep_scope:f['source_return']['scope'].pop('num_regions_examined')
  f['fixture_id']=f'N{len(fs)+1:03d}';fs.append(f)
 for old in ['F004','F006']:
  f=copy.deepcopy(prior[old]);f['fixture_id']=f'N{len(fs)+1:03d}';fs.append(f)
 return fs
def prompt(f):return c.INSTRUCTION+'\n只输出含relation和reason的JSON，relation为supported、contradicted或unknown，reason用中文解释具体依据或缺失字段，不使用外部知识。\n待审核数据：\n'+json.dumps(f,ensure_ascii=False)
def prepare(source,target):
 m=json.loads((source/'manifest.json').read_text(encoding='utf8'))
 if c.sha(source/'manifest.json')!='f008ec796ea2abd7426384ec9546f4e03fe7d97dd685f6121ef1efc082e51211':raise ValueError('wrong R9 source')
 for n,h in m['artifact_hashes'].items():
  if c.sha(source/n)!=h:raise ValueError('R9 artifact changed '+n)
 fs=fixtures(source);target.mkdir(parents=True,exist_ok=False);c.dump(target/'fixtures.json',fs);c.dump(target/'schema.json',SCHEMA)
 order=list(fs);random.Random(42).shuffle(order);schedule=[]
 for f in order:
  name=f['fixture_id']+'_json_reason';(target/(name+'.txt')).write_text(prompt(f),encoding='utf8');schedule.append({'fixture_id':f['fixture_id'],'name':name,'mode':'json_reason'})
 deps=dict(m['protocol_hashes'])
 for n in ['reasoned_control.py','PLAN_ROUND10_20261010.md']:deps[(BASE/n).relative_to(ROOT).as_posix()]=c.sha(BASE/n)
 result={'condition':'missing_list_count_factorial','schedule':schedule,'parent_R9_manifest_sha256':c.sha(source/'manifest.json'),
  'protocol_hashes':deps,'artifact_hashes':{p.name:c.sha(p) for p in target.iterdir() if p.is_file()},'targets_in_requests':False,'sft':False,'independent_test':False}
 c.dump(target/'manifest.json',result);print(json.dumps({'requests':6,'manifest_sha256':c.sha(target/'manifest.json')}))
def parse(raw):
 v=json.loads(raw)
 if set(v)!= {'relation','reason'} or v['relation'] not in c.LABELS or not isinstance(v['reason'],str) or not v['reason'].strip():raise ValueError('invalid relation/reason')
 return v
def run(inputs,output):
 from run import http
 from run_compact import native_count
 m=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
 for n,h in m['artifact_hashes'].items():
  if c.sha(inputs/n)!=h:raise ValueError('input changed '+n)
 for n,h in m['protocol_hashes'].items():
  if c.sha(ROOT/n)!=h:raise ValueError('code changed '+n)
 lock=output.parent/'controlled_claims.lock'
 with lock.open('x') as h:h.write(str(__import__('os').getpid()))
 try:
  output.mkdir(parents=True,exist_ok=False)
  counts=[{**s,'native_input_tokens':native_count((inputs/(s['name']+'.txt')).read_text(encoding='utf8'))} for s in m['schedule']];c.dump(output/'native_preflight.json',counts)
  if any(s['native_input_tokens']+4096>24576 for s in counts):raise ValueError('context overflow')
  runtime={'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'manifest_sha256':c.sha(inputs/'manifest.json'),'model':'Qwen3.5-27B Q4_K_M',
   'backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,'thinking':False,'max_tokens':4096,'timeout_seconds':120,'retries':0,'targets_read':False,'actor_actions_executed':False,'sft':False}
  c.dump(output/'runtime.json',runtime)
  with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
   for i,s in enumerate(counts,1):
    row=dict(s);start=time.monotonic();c.dump(output/'inflight.json',{'index':i,**s,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')});print(json.dumps({'event':'start','index':i,**s}),flush=True)
    body={'messages':[{'role':'user','content':(inputs/(s['name']+'.txt')).read_text(encoding='utf8')}],'temperature':0,'seed':42,'repeat_penalty':1.05,
     'cache_prompt':False,'max_tokens':4096,'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object','schema':SCHEMA}}
    try:
     result=http('/v1/chat/completions',body);c.dump(output/(s['name']+'.http.json'),result);choice=result['choices'][0]
     row.update(raw=choice['message']['content'],finish_reason=choice['finish_reason'],usage=result['usage'])
     try:row.update(parse(row['raw']),parse_valid=True)
     except (ValueError,TypeError):row.update(parse_valid=False,error='invalid_output')
    except Exception as exc:row.update(parse_valid=False,request_error=type(exc).__name__+': '+str(exc))
    row['seconds']=round(time.monotonic()-start,4);c.dump(output/(s['name']+'.response.json'),row);handle.write(json.dumps(row,ensure_ascii=False)+'\n');handle.flush()
    print(json.dumps({'event':'end','index':i,'valid':row['parse_valid'],'seconds':row['seconds']}),flush=True)
    if 'request_error' in row:raise RuntimeError('transport failed; inspect before further generation')
  runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z');c.dump(output/'runtime.json',runtime);(output/'inflight.json').unlink()
 finally:lock.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--prepare',type=Path);p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.prepare:prepare(a.source,a.prepare)
 else:run(a.inputs,a.output)
