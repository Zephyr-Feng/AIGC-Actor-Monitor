"""Single-factor source representation probe; no final Monitor or Actor calls."""
import argparse,json,time,shutil
from pathlib import Path
from protocol import BASE,ROOT
from run import sha
from compact import focused_input,compact_schema,compile_relations
from source_objects import grouped_input,grouped_prompt
from claim_verify import generate
from run_compact import native_count


def prepare(source,target):
 parent=json.loads((source/'manifest.json').read_text(encoding='utf8'))
 for n,h in parent['artifact_hashes'].items():
  if sha(source/n)!=h:raise ValueError('original G input changed '+n)
 for n,h in parent['protocol_hashes'].items():
  if sha(ROOT/n)!=h:raise ValueError('original G dependency changed '+n)
 packets=list(map(json.loads,(source/'inputs.jsonl').read_text(encoding='utf8').splitlines()))
 target.mkdir(parents=True,exist_ok=False);shutil.copyfile(source/'inputs.jsonl',target/'inputs.jsonl')
 for p in packets:
  cid=p['case_id'];shutil.copyfile(source/f'{cid}.focused.json',target/f'{cid}.focused.json')
  original=(source/f'{cid}.verify.schema.json').read_bytes()
  if json.loads(original)!=compact_schema(focused_input(p)):raise ValueError('schema changed')
  (target/f'{cid}.verify.schema.json').write_bytes(original)
  (target/f'{cid}.grouped.json').write_text(json.dumps(grouped_input(p),ensure_ascii=False),encoding='utf8')
  (target/f'{cid}.request.txt').write_text(grouped_prompt(p),encoding='utf8')
 dependencies=dict(parent['protocol_hashes'])
 for n in ['source_objects.py','run_source_objects.py','PLAN_ROUND7_20261010.md']:
  dependencies[(BASE/n).relative_to(ROOT).as_posix()]=sha(BASE/n)
 m={'cases':parent['cases'],'condition':'source_objects','parent_G_manifest_sha256':sha(source/'manifest.json'),
    'protocol_hashes':dependencies,'artifact_hashes':{p.name:sha(p) for p in target.iterdir() if p.is_file()},
    'final_monitor_executed':False,'independent_test':False,'annotations_read':False}
 (target/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf8')
 print(json.dumps({'cases':len(packets),'source_atoms':sum(len(focused_input(p)['observation_atoms']) for p in packets),'manifest_sha256':sha(target/'manifest.json')}))


def run(inputs,output,preflight_only=False):
 m=json.loads((inputs/'manifest.json').read_text())
 for n,h in m['artifact_hashes'].items():
  if sha(inputs/n)!=h:raise ValueError('input changed '+n)
 for n,h in m['protocol_hashes'].items():
  if sha(ROOT/n)!=h:raise ValueError('code changed '+n)
 output.mkdir(parents=True,exist_ok=False);counts=[]
 for cid in m['cases']:
  count=native_count((inputs/f'{cid}.request.txt').read_text(encoding='utf8'))
  counts.append({'case_id':cid,'input_tokens':count,'fits':count+4096<=24576})
 (output/'native_preflight.json').write_text(json.dumps(counts,indent=2))
 if not all(r['fits'] for r in counts):raise ValueError('context failure before generation')
 print(json.dumps({'event':'preflight','cases':len(counts),'all_fit':True,'max_tokens':max(r['input_tokens'] for r in counts)}),flush=True)
 if preflight_only:return
 runtime={'condition':'source_objects','manifest_sha256':sha(inputs/'manifest.json'),'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
 'model':'Qwen3.5-27B Q4_K_M','backend':'b11517/8a1a9b512','temperature':0,'seed':42,'repeat_penalty':1.05,'max_tokens':4096,'thinking':False,
 'timeout_seconds':120,'retries':0,'final_monitor_executed':False,'actor_actions_executed':False,'annotations_read':False,'sft':False}
 (output/'runtime.json').write_text(json.dumps(runtime,indent=2))
 with (output/'responses.jsonl').open('x',encoding='utf8') as handle:
  for index,cid in enumerate(m['cases'],1):
   data=json.loads((inputs/f'{cid}.focused.json').read_text(encoding='utf8'));start=time.monotonic();row={'case_id':cid,'condition':'source_objects'}
   print(json.dumps({'event':'source_start','index':index,'case_id':cid,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
   try:
    if data['observation_atoms'] or data['conflict_slots']:
     result=generate((inputs/f'{cid}.request.txt').read_text(encoding='utf8'),json.loads((inputs/f'{cid}.verify.schema.json').read_text()))
     row.update(result);row['compiled_relations']=compile_relations(result['raw'],data)
    else:row.update(skipped=True,raw='{"observations":{},"conflicts":{}}',compiled_relations={'observations':{},'conflicts':{}},usage={'prompt_tokens':0,'completion_tokens':0})
    row['parse_valid']=True
   except Exception as exc:row.update(parse_valid=False,error=type(exc).__name__+': '+str(exc))
   row['seconds']=round(time.monotonic()-start,4)
   (output/f'{cid}.source.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
   handle.write(json.dumps(row,ensure_ascii=False)+'\n');handle.flush()
   print(json.dumps({'event':'source_end','index':index,'valid':row['parse_valid'],'seconds':row['seconds'],'error':row.get('error')}),flush=True)
   if not row['parse_valid']:raise RuntimeError('source stage failed; preserve before further calls')
 runtime['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z');(output/'runtime.json').write_text(json.dumps(runtime,indent=2))
 print('Completed source representation probe. No final Monitor or Actor action.',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--prepare',type=Path);p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path);p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
 if a.prepare:prepare(a.source,a.prepare)
 else:run(a.inputs,a.output,a.preflight_only)
