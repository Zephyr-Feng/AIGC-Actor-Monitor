import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from source_objects import grouped_input,grouped_prompt
from compact import focused_input,verifier_prompt,compact_schema
from protocol import evidence_catalog

class SourceObjectBoundaryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.packets=list(map(json.loads,(ROOT/'experiments/faithbench_monitor_v0/private/pilot_v2_locked/inputs.jsonl').read_text(encoding='utf8').splitlines()))

 def test_information_and_values_are_preserved_for_all_eight(self):
  for p in self.packets:
   old=focused_input(p);new=grouped_input(p);cat=evidence_catalog(p)
   rest=new['source_pool']['actor_and_capability_fields'];ids=set(rest)
   for group in new['source_pool']['grouped_tool_returns']:
    root=group['observation_pointer'];matching=[e for e in p['runtime_snapshot']['evidence_ledger'] if e['observation_ref']==root]
    self.assertEqual(group['original_return'],matching[0]['observation'])
    allids={eid for eid,r in cat.items() if r['pointer'].startswith(root+'/')}
    self.assertEqual(allids,set(group['field_references'].values()))
    for field,eid in group['field_references'].items():self.assertEqual(root+field,cat[eid]['pointer'])
    ids.update(group['field_references'].values())
   self.assertEqual(ids,set(old['source_pool']))
   for key in ['observation_atoms','conflict_slots','visual_text_audit']:self.assertEqual(new[key],old[key])

 def test_prompt_instruction_and_schema_are_unchanged(self):
  for p in self.packets:
   old=verifier_prompt(focused_input(p));new=grouped_prompt(p)
   self.assertEqual(old.split('\n输入：\n')[0],new.split('\n输入：\n')[0])
   self.assertEqual(compact_schema(focused_input(p)),compact_schema(grouped_input(p)))

 def test_future_return_is_not_added(self):
  p=copy.deepcopy(self.packets[2]);old=grouped_input(p)
  e=copy.deepcopy(p['runtime_snapshot']['evidence_ledger'][0]);e['returned_after_step']=99;e['observation_ref']='/trajectory/steps/99/tool_observation';e['observation']={'forbidden_future':'未出现的未来值'}
  p['runtime_snapshot']['evidence_ledger'].append(e)
  self.assertEqual(grouped_input(p),old)
  self.assertNotIn('未出现的未来值',grouped_prompt(p))

 def test_original_packet_not_mutated(self):
  p=copy.deepcopy(self.packets[2]);old=copy.deepcopy(p);new=grouped_input(p)
  new['source_pool']['grouped_tool_returns'][0]['original_return']['evidence_type']='changed'
  self.assertEqual(p,old)

if __name__=='__main__':unittest.main()
