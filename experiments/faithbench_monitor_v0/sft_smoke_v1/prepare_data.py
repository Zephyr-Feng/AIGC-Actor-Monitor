"""Small engineering supervision from pinned, previously reviewed development outputs."""
import argparse,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
import single_source as single
import reasoned_control as reasoned
from prepare_reasoned_portable import dump
PINS={'round11':'62a2347d10b933f25df059922699d9c9adc91e21ad401ba9fa0674e1fa912323','round13':'a0ed028c74f730a6f6bdea0a14cfb57bacc1de066098afff0f7b491abee80639','round14':'aec1d35f9cae1b74b330598dc7345f26c3ba8d826a70c3fac59cb2fadb6c1fb8'}
CONTROLS=['terminal_0002_A003','terminal_0002_A004','terminal_0002_A006','terminal_0002_A008','terminal_0061_A007','terminal_0061_A008','terminal_0041_A006','terminal_0041_A002']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def checked_rows(name,path):
 if sha(path/'responses.jsonl')!=PINS[name]:raise ValueError('changed reviewed responses '+name)
 rows=[json.loads(x) for x in (path/'responses.jsonl').read_text(encoding='utf8').splitlines()]
 if any(not x['parse_valid'] or x['finish_reason']!='stop' for x in rows):raise ValueError('invalid source output')
 return rows
def prepare(iterations,r11,r13,r14,target):
 train=[];evaluations=[];deps={}
 for name in ['round11','round13','round14']:
  inputs=iterations/(name+'_inputs');m=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
  for n,h in m['artifact_hashes'].items():
   if sha(inputs/n)!=h:raise ValueError('source input changed '+name+'/'+n)
  deps.update(m['protocol_hashes'])
 for x in checked_rows('round11',r11):
  prompt=(iterations/'round11_inputs'/(x['name']+'.txt')).read_text(encoding='utf8');answer=reasoned.parse(x['raw'])
  train.append({'id':'R11_'+x['name'],'task':'relation_reason','label_provenance':'synthetic_diagnostic_reviewed_not_gold','user_text':prompt,'answer':answer})
 records={v['case_id']+'_'+v['atom_id']:v for v in json.loads((iterations/'round13_inputs/records.json').read_text(encoding='utf8'))}
 for x in checked_rows('round13',r13):
  prompt=(iterations/'round13_inputs'/(x['name']+'.txt')).read_text(encoding='utf8');answer=single.parse(x['raw'],records[x['name']]);curation=None
  if x['name']=='call_0385_A008':
   answer={'status':answer['status'],'reason':'工具limitations说明表征偏离不构成图像来源证明，罕见真实内容或后处理也可产生高偏离值；“偏离不等于伪造”是忠实释义。','source_reference_ids':[records[x['name']]['prior_source_returns'][0]['field_references']['/limitations/0'],records[x['name']]['prior_source_returns'][0]['field_references']['/limitations/1']]};single.parse(json.dumps(answer,ensure_ascii=False),records[x['name']]);curation='remove_extra_neighbor_claims_and_references'
  item={'id':'R13_'+x['name'],'task':'source_status_reason_citations','label_provenance':'agent_proposed_silver_reviewed_not_gold','user_text':prompt,'answer':answer,'curation':curation};train.append(item)
  evaluations.append({**item,'evaluation_scope':'training_row_regression'})
 byname={x['name']:x for x in checked_rows('round14',r14)}
 r14records={v['case_id']+'_'+v['atom_id']:v for v in json.loads((iterations/'round14_inputs/records.json').read_text(encoding='utf8'))}
 for name in CONTROLS:
  x=byname[name];answer=single.parse(x['raw'],r14records[name])
  if answer['status']!='supported_by_source':raise ValueError('unexpected control label')
  evaluations.append({'id':'R14_'+name,'task':'source_status_reason_citations','label_provenance':'agent_proposed_silver_reviewed_not_gold','user_text':(iterations/'round14_inputs'/(name+'.txt')).read_text(encoding='utf8'),'answer':answer,'evaluation_scope':'out_of_training_row_same_development_sources'})
 if len(train)!=14 or len(evaluations)!=16 or any(x['id'] in {v['id'] for v in train} for x in evaluations if x['evaluation_scope'].startswith('out_of')):raise ValueError('scope mismatch')
 target.mkdir(parents=True,exist_ok=False);dump(target/'train.json',train);dump(target/'evaluation.json',evaluations)
 for n in ['PLAN_20261010.md','prepare_data.py','train_smoke.py']:deps[(BASE/n).relative_to(ROOT).as_posix()]=sha(BASE/n)
 dump(target/'manifest.json',{'training_records':14,'evaluation_records':16,'source_response_sha256':PINS,'protocol_hashes':deps,'artifact_hashes':{p.name:sha(p) for p in sorted(target.iterdir())},'independent_test':False,'human_confirmed':0,'gold':False,'actor_actions_executed':False,'reserved_groups_read':False,'teacher_answers_in_user_text':False})
 print(json.dumps({'training_records':14,'evaluation_records':16,'manifest_sha256':sha(target/'manifest.json')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--iterations',type=Path,required=True);p.add_argument('--r11-output',type=Path,required=True);p.add_argument('--r13-output',type=Path,required=True);p.add_argument('--r14-output',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();prepare(a.iterations,a.r11_output,a.r13_output,a.r14_output,a.prepare)
