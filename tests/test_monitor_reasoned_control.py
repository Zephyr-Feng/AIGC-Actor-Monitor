import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
import reasoned_control as r
class ReasonedControlTests(unittest.TestCase):
 def test_factorial_only_removes_designated_fields(self):
  source=ROOT/'experiments/faithbench_monitor_v0/private/monitor_iterations_20261010/round9_inputs'
  fs=r.fixtures(source);old={f['fixture_id']:f for f in json.loads((source/'fixtures.json').read_text(encoding='utf8'))}
  self.assertEqual(len(fs),6)
  for f,(keep_num,keep_scope) in zip(fs[:4],[(True,True),(True,False),(False,True),(False,False)]):
   expected=copy.deepcopy(old['F005'])
   if not keep_num:expected['source_return']['observations'].pop('num_atypical_regions')
   if not keep_scope:expected['source_return']['scope'].pop('num_regions_examined')
   expected['fixture_id']=f['fixture_id'];self.assertEqual(f,expected)
   self.assertNotIn('most_atypical_regions',f['source_return'])
  self.assertEqual(len(fs[4]['source_return']['most_atypical_regions']),3)
  self.assertEqual(len(fs[5]['source_return']['most_atypical_regions']),1)
  self.assertEqual(r.parse('{"relation":"unknown","reason":"缺少列表"}')['relation'],'unknown')
if __name__=='__main__':unittest.main()
