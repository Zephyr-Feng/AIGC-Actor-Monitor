"""Reuse exactly thirteen reviewed fixtures; do not create new tool evidence."""
import argparse,copy,hashlib,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[2]
sys.path.insert(0,str(BASE));import contract
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf8'))
def dump(p,value):
 with p.open('x',encoding='utf8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
def prepare(source,review,target):
 m=load(source/'manifest.json')
 for n,h in m['artifact_hashes'].items():assert sha(source/n)==h,n
 for n,h in m['protocol_hashes'].items():assert sha(ROOT/n)==h,n
 assert sha(review)=='c1ade5e791674b15b520b7eb6aecec8734357b50ef1fac82693f835bab5be0c5'
 labels={r['name']:r for r in load(review)['rows']}
 train=[];evaluation=[];audit=[]
 for r in load(source/'records.json'):
  d=r['data'];entry=labels[r['name']];answer=copy.deepcopy(entry['target'])
  contract.parse(json.dumps(answer,ensure_ascii=False),d)
  held=d['case_id'] in {'terminal_0001','call_0385'}
  row={'id':r['name'],'task':'typed_evidence_contract','user_text':contract.prompt(d),
   'answer':answer,'evaluation_scope':'held_development_case' if held else 'training_recall',
   'label_provenance':'existing_agent_reviewed_engineering_supervision_not_gold'}
  evaluation.append(row)
  if not held:train.append(copy.deepcopy(row))
  audit.append({'id':r['name'],'kind':r['kind'],'case_id':d['case_id'],'audit_target':d['audit_target'],
   'status':answer['status'],'split':row['evaluation_scope'],'source_data_sha256':hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
   'target_copied_without_change':True,'full_return_absence_previously_reviewed':entry['absence_inspected_in_full_return']})
 assert len(train)==7 and len(evaluation)==13
 assert {json.loads(r['user_text'].split('\n待审核数据：\n')[1])['case_id'] for r in train}.isdisjoint({'terminal_0001','call_0385'})
 assert any(r['answer']['status']=='unassessable' for r in train)
 assert any(r['answer']['status']=='not_returned_by_source' for r in train)
 assert len({tuple(r['answer']) for r in train})==1
 target.mkdir(parents=True,exist_ok=False)
 dump(target/'train.json',train);dump(target/'evaluation.json',evaluation);dump(target/'source_audit.json',audit)
 deps={**m['protocol_hashes'],**{(BASE/n).relative_to(ROOT).as_posix():sha(BASE/n) for n in ['contract.py','prepare.py','run.py','PLAN_20261010.md']}}
 old=ROOT/'experiments/faithbench_monitor_v0/sft_smoke_v1/train_smoke.py';deps[old.relative_to(ROOT).as_posix()]=sha(old)
 dump(target/'manifest.json',{'stage':'CPU_supervision_preparation','training_records':7,'evaluation_records':13,
 'generation_requests':26,'parent_manifest_sha256':sha(source/'manifest.json'),'parent_review_sha256':sha(review),
 'artifact_hashes':{p.name:sha(p) for p in sorted(target.iterdir())},'protocol_hashes':deps,
 'new_tool_returns':0,'new_control_mutations':0,'targets_copied_without_change':True,'gold':False,'human_confirmed':0,
 'independent_test':False,'reserved_groups_read':False,'actor_actions_executed':False})
 print(json.dumps({'manifest_sha256':sha(target/'manifest.json'),'train':7,'evaluation':13,'new_evidence':0}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--target',type=Path,required=True);a=p.parse_args();prepare(a.source,a.review,a.target)
