import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'experiments/faithbench_monitor_v0/pilot_v3/controlled_claims.py'
spec=importlib.util.spec_from_file_location('controlled_claims',path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ControlledClaimsTests(unittest.TestCase):
 def setUp(self):
  self.source=ROOT/'experiments/faithbench_monitor_v0/private/monitor_iterations_20261010/round7_source_inputs'
  self.fs,self.targets=mod.fixtures(mod.load_original(self.source))
 def test_counterfactuals_and_scope(self):
  self.assertEqual(len(self.fs),12)
  f={t['family']+'_'+t['variant']:v for t,v in zip(self.targets,self.fs)}
  self.assertNotIn('阈值',f['threshold_deleted']['source_return']['observation'])
  self.assertIn('0.7',f['threshold_opposite']['source_return']['observation'])
  self.assertNotIn('most_atypical_regions',f['regions_deleted']['source_return'])
  self.assertEqual(len(f['regions_opposite']['source_return']['most_atypical_regions']),1)
  self.assertEqual(f['regions_support']['source_return']['observations']['num_atypical_regions'],1)
  self.assertNotIn('semantic_location',f['attribution_deleted']['source_return']['most_atypical_regions'][0])
 def test_targets_hidden_and_balanced(self):
  with tempfile.TemporaryDirectory() as tmp:
   target=Path(tmp)/'inputs';mod.prepare(self.source,target)
   m=json.loads((target/'manifest.json').read_text(encoding='utf8'))
   pairs=[m['schedule'][i:i+2] for i in range(0,24,2)]
   self.assertEqual(sum(p[0]['mode']=='json' for p in pairs),6)
   self.assertEqual(len({p[0]['fixture_id'] for p in pairs}),12)
   self.assertNotIn('targets.json',m['artifact_hashes'])
   for p in pairs:
    self.assertEqual(p[0]['fixture_id'],p[1]['fixture_id'])
    for s in p:
     text=(target/(s['name']+'.txt')).read_text(encoding='utf8')
     self.assertNotIn('expected',text);self.assertNotIn('original_case',text)
 def test_strict_output_no_repair(self):
  self.assertEqual(mod.parse('{"relation":"unknown"}','json'),'unknown')
  for raw,mode in [('supported because yes','label'),('{"relation":"supported","reason":"x"}','json')]:
   with self.assertRaises(ValueError):mod.parse(raw,mode)
if __name__=='__main__':unittest.main()
