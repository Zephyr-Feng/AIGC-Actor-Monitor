import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
import context_claims as ctx
class ContextClaimsTests(unittest.TestCase):
 def test_expansion_preserves_counterfactual_and_other_fields(self):
  b=ROOT/'experiments/faithbench_monitor_v0/private/monitor_iterations_20261010'
  fs,targets=ctx.expanded_fixtures(b/'round7_source_inputs',b/'round8_inputs')
  old=json.loads((b/'round8_inputs/fixtures.json').read_text(encoding='utf8'))
  for new,prior,t in zip(fs,old,targets):
   self.assertEqual({k:v for k,v in new.items() if k!='source_return'},{k:v for k,v in prior.items() if k!='source_return'})
   for k,v in prior['source_return'].items():self.assertEqual(new['source_return'][k],v)
   if t['family']=='regions' and t['variant']=='deleted':self.assertNotIn('most_atypical_regions',new['source_return'])
   if t['family']=='threshold' and t['variant']=='deleted':self.assertNotIn('阈值',new['source_return']['observation'])
   if t['family']=='paraphrase' and t['variant']=='deleted':self.assertEqual(new['source_return']['limitations'],[])
   if t['family']=='attribution' and t['variant']=='deleted':self.assertNotIn('semantic_location',new['source_return']['most_atypical_regions'][0])
  self.assertEqual(targets,json.loads((b/'round8_inputs/targets.json').read_text(encoding='utf8')))
if __name__=='__main__':unittest.main()
