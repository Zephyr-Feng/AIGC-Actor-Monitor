import argparse,json,shutil
from pathlib import Path
import controlled_claims as c
from prepare_reasoned_portable import dump
def prepare(source,target):
 if c.sha(source/'manifest.json')!='4c784bb107664bad75a88b2201672105b173de56fb847b6cdf532a02a8f8850b':raise ValueError('wrong R10 input')
 m=json.loads((source/'manifest.json').read_text(encoding='utf8'))
 for n,h in m['artifact_hashes'].items():
  if c.sha(source/n)!=h:raise ValueError('R10 artifact changed '+n)
 target.mkdir(parents=True,exist_ok=False)
 for n in ['fixtures.json','schema.json']:shutil.copyfile(source/n,target/n)
 definitions=(c.BASE/'region_field_contract.md').read_text(encoding='utf8');marker='\n待审核数据：\n'
 for s in m['schedule']:
  raw=(source/(s['name']+'.txt')).read_text(encoding='utf8')
  if raw.count(marker)!=1:raise ValueError('unexpected prompt boundary')
  (target/(s['name']+'.txt')).write_bytes(raw.replace(marker,'\n字段契约：\n'+definitions+marker,1).encode('utf8'))
 deps=dict(m['protocol_hashes'])
 for n in ['prepare_field_scoped.py','region_field_contract.md','PLAN_ROUND11_20261010.md']:deps[(c.BASE/n).relative_to(c.ROOT).as_posix()]=c.sha(c.BASE/n)
 result={**m,'condition':'explicit_field_semantics','parent_R10_manifest_sha256':c.sha(source/'manifest.json'),
  'protocol_hashes':deps,'artifact_hashes':{p.name:c.sha(p) for p in sorted(target.iterdir()) if p.is_file()}}
 dump(target/'manifest.json',result);print(json.dumps({'requests':6,'manifest_sha256':c.sha(target/'manifest.json')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();prepare(a.source,a.prepare)
