import argparse,json,hashlib,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from prepare_reasoned_portable import dump
import single_source
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
TARGETS={
 'R13_terminal_0005_A006':('most_atypical_regions[0].region_id为R1，直接支持当前片段的区域编号。',['E0108']),
 'R13_terminal_0005_A007':('most_atypical_regions[0].region_id为R1；返回未包含“门牌号附近”的内容描述，区域编号不能支持这一物体语义。',['E0108']),
 'R13_terminal_0005_A009':('most_atypical_regions[0].deviation_percentile为66.66666666666667，四舍五入为66.7%，支持当前数值片段。',['E0104']),
 'R13_terminal_0001_A005':('most_atypical_regions[0].region_id为R1；同源返回没有“过曝天空”的语义描述，编号和位置属性不能作为该内容的工具依据。',['E0056']),
 'R13_terminal_0001_A006':('most_atypical_regions[1].region_id为R2；同源返回未描述“方尖碑顶部”，R2编号不提供该物体语义。',['E0066']),
 'R13_terminal_0001_A007':('most_atypical_regions[2].region_id为R3；同源返回未描述“云层”，区域编号不能支持该内容描述。',['E0076']),
 'R13_terminal_0001_A009':('observation明确写有“固定判定阈值为0.5”，直接支持该阈值片段。',['E0110']),
 'R13_call_0385_A008':('limitations[0]说明表征偏离不构成图像来源证明，支持“偏离不等于伪造”的限定释义。',['E0085'])}
def prepare(source,probe,target):
 assert sha(source/'manifest.json')=='5074f514b3e5db36f88d9124a07032c5572e9b5e4e95311bf4f216576cc1d5bf' and sha(probe/'manifest.json')=='bb95f8288075278d58f39b55f69440721adb5cdd1c36bc13eafb5f24827f475a'
 old=json.loads((source/'manifest.json').read_text(encoding='utf8'));pm=json.loads((probe/'manifest.json').read_text(encoding='utf8'))
 assert all(sha(source/n)==h for n,h in old['artifact_hashes'].items()) and all(sha(probe/n)==h for n,h in pm['artifact_hashes'].items())
 original=json.loads((source/'train.json').read_text(encoding='utf8'));train=copy.deepcopy(original);edits=[]
 for row in train:
  if row['id'] not in TARGETS:continue
  reason,refs=TARGETS[row['id']];prior=copy.deepcopy(row['answer']);row['answer']={**prior,'reason':reason,'source_reference_ids':refs};row['curation']='current_fragment_field_value_minimal_evidence';row['label_provenance']='agent_curated_engineering_supervision_not_gold'
  data=json.loads(row['user_text'].split('\n待审核数据：\n',1)[1]);single_source.parse(json.dumps(row['answer'],ensure_ascii=False),data);edits.append({'id':row['id'],'before':prior,'after':row['answer']})
 assert len(train)==14 and len(edits)==8 and all(a['id']==b['id'] and a['user_text']==b['user_text'] for a,b in zip(original,train))
 evaluation=json.loads((source/'evaluation.json').read_text(encoding='utf8'));byid={r['id']:r for r in train}
 for row in evaluation:
  if row['id'] in TARGETS:row['answer']=copy.deepcopy(byid[row['id']]['answer'])
 target.mkdir(parents=True,exist_ok=False);dump(target/'train.json',train);dump(target/'evaluation.json',evaluation);dump(target/'supervision_edits.json',edits);dump(target/'probe_evaluation.json',json.loads((probe/'evaluation.json').read_text(encoding='utf8')))
 deps={**old['protocol_hashes'],**pm['protocol_hashes']}
 for n in ['PLAN_20261010.md','prepare_curated.py','run_curated.py']:deps[(BASE/n).relative_to(ROOT).as_posix()]=sha(BASE/n)
 dump(target/'manifest.json',{'training_records':14,'evaluation_records':16,'extra_after_probe_requests':16,'generation_requests':48,'changed_assistant_targets':8,'parent_manifest_sha256':sha(source/'manifest.json'),'probe_manifest_sha256':sha(probe/'manifest.json'),'protocol_hashes':deps,'artifact_hashes':{p.name:sha(p) for p in sorted(target.iterdir())},'gold':False,'human_confirmed':0,'independent_test':False,'actor_actions_executed':False,'reserved_groups_read':False})
 print(json.dumps({'manifest_sha256':sha(target/'manifest.json'),'training_records':14,'generation_requests':48}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--probe',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();prepare(a.source,a.probe,a.prepare)
