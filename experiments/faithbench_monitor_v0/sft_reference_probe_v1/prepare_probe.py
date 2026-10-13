import argparse,json,re,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from prepare_reasoned_portable import dump
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SELECT=['R13_terminal_0005_A007','R13_terminal_0001_A005','R13_terminal_0001_A006','R13_terminal_0001_A007','R13_terminal_0001_A009','R14_terminal_0002_A004','R14_terminal_0041_A002','R14_terminal_0002_A006']
def prepare(source,target):
 assert sha(source/'manifest.json')=='5074f514b3e5db36f88d9124a07032c5572e9b5e4e95311bf4f216576cc1d5bf'
 m=json.loads((source/'manifest.json').read_text(encoding='utf8'));assert all(sha(source/n)==h for n,h in m['artifact_hashes'].items())
 byid={r['id']:r for r in json.loads((source/'evaluation.json').read_text(encoding='utf8'))};rows=[];maps={}
 for index,name in enumerate(SELECT):
  r=byid[name];ids=sorted(set(re.findall(r'\bE\d{4}\b',r['user_text'])));mapping={s:'E'+str(int(s[1:])+5000).zfill(4) for s in ids};assert all(len(s)==5 for s in mapping.values()) and not set(ids)&set(mapping.values())
  new=re.sub(r'\bE\d{4}\b',lambda x:mapping[x[0]],r['user_text']);inverse={v:k for k,v in mapping.items()};assert re.sub(r'\bE\d{4}\b',lambda x:inverse[x[0]],new)==r['user_text']
  ans=json.loads(re.sub(r'\bE\d{4}\b',lambda x:mapping[x[0]],json.dumps(r['answer'],ensure_ascii=False)))
  pair=[{**r,'id':name+'_original','pair_id':name,'reference_condition':'original'},{**r,'id':name+'_renamed','pair_id':name,'reference_condition':'renamed','user_text':new,'answer':ans}]
  rows.extend(pair if index%2==0 else pair[::-1]);maps[name]=mapping
 target.mkdir(parents=True,exist_ok=False);dump(target/'evaluation.json',rows);dump(target/'reference_maps.json',maps)
 deps=dict(m['protocol_hashes'])
 for n in ['PLAN_20261010.md','prepare_probe.py','run_probe.py']:deps[(BASE/n).relative_to(ROOT).as_posix()]=sha(BASE/n)
 dump(target/'manifest.json',{'evaluation_records':16,'generation_requests':32,'selected':SELECT,'adapter_sha256':'93775d127ef6420b679534a2cff9ec175228b341b0f50585e4f7d05793ffee8f','parent_manifest_sha256':sha(source/'manifest.json'),'artifact_hashes':{p.name:sha(p) for p in sorted(target.iterdir())},'protocol_hashes':deps,'training_steps':0,'gold':False,'independent_test':False,'reserved_groups_read':False})
 print(json.dumps({'manifest_sha256':sha(target/'manifest.json'),'requests':32}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();prepare(a.source,a.prepare)
