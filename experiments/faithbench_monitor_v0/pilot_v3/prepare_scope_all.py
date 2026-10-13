import argparse,json,shutil
from pathlib import Path
import controlled_claims as c
from prepare_reasoned_portable import dump
from prepare_observation_scope import SCOPE
def prepare(source,target):
 if c.sha(source/'manifest.json')!='8127e9a8a9b06be467d8fa249f4a8d0f690aeb282c31ff91e20a1c1afedbf143':raise ValueError('wrong R12')
 m=json.loads((source/'manifest.json').read_text(encoding='utf8'))
 for n,h in m['artifact_hashes'].items():
  if c.sha(source/n)!=h:raise ValueError('R12 changed '+n)
 target.mkdir(parents=True,exist_ok=False);shutil.copyfile(source/'records.json',target/'records.json')
 for s in m['schedule']:
  n=s['name'];raw=(source/(n+'.txt')).read_text(encoding='utf8');marker='\n待审核数据：\n'
  if raw.count(marker)!=1:raise ValueError('prompt boundary')
  (target/(n+'.txt')).write_bytes(raw.replace(marker,'\n'+SCOPE+marker,1).encode('utf8'));shutil.copyfile(source/(n+'.schema.json'),target/(n+'.schema.json'))
 deps=dict(m['protocol_hashes'])
 for n in ['prepare_observation_scope.py','prepare_scope_all.py','PLAN_ROUND14_20261010.md']:deps[(c.BASE/n).relative_to(c.ROOT).as_posix()]=c.sha(c.BASE/n)
 dump(target/'manifest.json',{'condition':'explicit_scope_all_observations','schedule':m['schedule'],'parent_R12_manifest_sha256':c.sha(source/'manifest.json'),'protocol_hashes':deps,'artifact_hashes':{p.name:c.sha(p) for p in sorted(target.iterdir())},'independent_test':False,'targets_read':False});print(json.dumps({'requests':len(m['schedule']),'manifest_sha256':c.sha(target/'manifest.json')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();prepare(a.source,a.prepare)
