import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from compact import focused_input,compact_schema,compile_relations,planning_prompt


class CompactBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets={p['case_id']:p for p in map(json.loads,(ROOT/'experiments/faithbench_monitor_v0/private/pilot_v2_locked/inputs.jsonl').read_text(encoding='utf8').splitlines())}

    def test_schema_only_exposes_same_source_return(self):
        data=focused_input(self.packets['terminal_0001']);schema=compact_schema(data)
        for a in data['observation_atoms']:
            expected={eid for p in a['prior_returns'] for eid in p['observation_ids']}
            supplied=set(schema['properties']['observations']['properties'][a['atom_id']]['properties']['source_reference_ids']['items']['enum'])
            self.assertEqual(supplied,expected)

    def test_compilation_binds_actor_without_inventing_semantic_status(self):
        data=focused_input(self.packets['terminal_0001'])
        result={'observations':{a['atom_id']:{'status':'unassessable','reason':'语义未知','source_reference_ids':a['prior_returns'][0]['observation_ids'][:1]} for a in data['observation_atoms']},'conflicts':{}}
        output=compile_relations(json.dumps(result,ensure_ascii=False),data)
        for a in data['observation_atoms']:
            self.assertEqual(output['observations'][a['atom_id']]['status'],'unassessable')
            self.assertTrue(set(a['claim_reference_ids'])<=set(output['observations'][a['atom_id']]['reference_ids']))
        key=data['observation_atoms'][0]['atom_id'];result['observations'][key]['source_reference_ids']=['E9999']
        with self.assertRaisesRegex(ValueError,'cross-source'):compile_relations(json.dumps(result),data)

    def test_final_prompt_does_not_duplicate_source_pool(self):
        data=focused_input(self.packets['terminal_0002']);prompt=planning_prompt(self.packets['terminal_0002'],data)
        self.assertNotIn('"source_pool"',prompt)
        self.assertNotIn('"prior_returns"',prompt)
        self.assertIn('原始待审数据',prompt)


if __name__=='__main__':unittest.main()
