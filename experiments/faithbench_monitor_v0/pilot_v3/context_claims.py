"""Expand only same-source fields, preserving every frozen counterfactual."""
import argparse,copy,json,random
from pathlib import Path
import controlled_claims as c
BASE=c.BASE;ROOT=c.ROOT
def expanded_fixtures(source,old):
 original=c.load_original(source)
 fs=json.loads((old/'fixtures.json').read_text(encoding='utf8'))
 targets=json.loads((old/'targets.json').read_text(encoding='utf8'))
 for f,t in zip(fs,targets):
  r=next(r for r in original[t['original_case']]['source_pool']['grouped_tool_returns'] if r['source']==f['source'])
  expanded=copy.deepcopy(r['original_return']);projection=f['source_return']
  if t['family']=='regions' and 'most_atypical_regions' not in projection:expanded.pop('most_atypical_regions')
  expanded.update(copy.deepcopy(projection));f['source_return']=expanded
 return fs,targets
def prepare(source,old,target):
 prior=json.loads((old/'manifest.json').read_text(encoding='utf8'))
 for n,h in prior['artifact_hashes'].items():
  if c.sha(old/n)!=h:raise ValueError('R8 input changed '+n)
 if c.sha(old/'targets.json')!=prior['targets_sha256']:raise ValueError('targets changed')
 fs,targets=expanded_fixtures(source,old);target.mkdir(parents=True,exist_ok=False)
 c.dump(target/'fixtures.json',fs);c.dump(target/'targets.json',targets);c.dump(target/'schema.json',c.SCHEMA)
 byid={f['fixture_id']:f for f in fs}
 for s in prior['schedule']:(target/(s['name']+'.txt')).write_text(c.prompt(byid[s['fixture_id']],s['mode']),encoding='utf8')
 deps=dict(prior['protocol_hashes'])
 for n in ['context_claims.py','PLAN_ROUND9_20261010.md']:deps[(BASE/n).relative_to(ROOT).as_posix()]=c.sha(BASE/n)
 m={**prior,'condition':'complete_same_source_control','parent_R8_manifest_sha256':c.sha(old/'manifest.json'),'protocol_hashes':deps,
  'artifact_hashes':{p.name:c.sha(p) for p in target.iterdir() if p.is_file() and p.name!='targets.json'},'targets_sha256':c.sha(target/'targets.json')}
 c.dump(target/'manifest.json',m);print(json.dumps({'requests':24,'manifest_sha256':c.sha(target/'manifest.json')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--old',type=Path);p.add_argument('--prepare',type=Path);p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 if a.prepare:prepare(a.source,a.old,a.prepare)
 else:c.run(a.inputs,a.output)
