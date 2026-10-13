"""Stable UTF-8/LF and sorted manifest; preserve failed preparation v1."""
import argparse,json,random
from pathlib import Path
import reasoned_control as r
c=r.c
def dump(path,value):path.write_bytes(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True).encode('utf8'))
def prepare(source,target):
 if c.sha(source/'manifest.json')!='f008ec796ea2abd7426384ec9546f4e03fe7d97dd685f6121ef1efc082e51211':raise ValueError('wrong R9 source')
 m=json.loads((source/'manifest.json').read_text(encoding='utf8'))
 for n,h in m['artifact_hashes'].items():
  if c.sha(source/n)!=h:raise ValueError('R9 source changed '+n)
 fs=r.fixtures(source);target.mkdir(parents=True,exist_ok=False);dump(target/'fixtures.json',fs);dump(target/'schema.json',r.SCHEMA)
 order=list(fs);random.Random(42).shuffle(order);schedule=[]
 for f in order:
  name=f['fixture_id']+'_json_reason';(target/(name+'.txt')).write_bytes(r.prompt(f).encode('utf8'));schedule.append({'fixture_id':f['fixture_id'],'name':name,'mode':'json_reason'})
 deps=dict(m['protocol_hashes'])
 for n in ['reasoned_control.py','PLAN_ROUND10_20261010.md','prepare_reasoned_portable.py','ROUND10_PREPARATION_FIX_20261010.md']:deps[(c.BASE/n).relative_to(c.ROOT).as_posix()]=c.sha(c.BASE/n)
 result={'condition':'missing_list_count_factorial','schedule':schedule,'parent_R9_manifest_sha256':c.sha(source/'manifest.json'),
  'protocol_hashes':deps,'artifact_hashes':{p.name:c.sha(p) for p in sorted(target.iterdir()) if p.is_file()},'targets_in_requests':False,'sft':False,'independent_test':False,'preparation_encoding':'utf8_lf_sorted_v2'}
 dump(target/'manifest.json',result);print(json.dumps({'requests':6,'manifest_sha256':c.sha(target/'manifest.json')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();prepare(a.source,a.prepare)
