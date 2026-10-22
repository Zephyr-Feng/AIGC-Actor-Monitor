import statistics
import unittest
from build_contract_candidates import context,examples


class ContractCandidateTests(unittest.TestCase):
    def tools(self):
        return {'local_texture_analyzer':{'limitations':'可能误报，强度不是校准概率'},
            'complementary_forensic_analyzer':{'limitations':'可能受分布变化影响'},
            'global_forensic_analyzer':{'limitations':'偏离不是来源真假概率'}}

    def test_missing_mean_has_same_summary_different_means_witness(self):
        for index in (0,1,2,3,99):
            source,witness=context(self.tools(),index)
            a,b=witness['values_a'],witness['values_b']
            self.assertEqual(statistics.median(a),statistics.median(b))
            self.assertEqual(a[-3:],b[-3:])
            self.assertNotEqual(statistics.mean(a),statistics.mean(b))
            self.assertEqual(len(a),source['global_return']['scope']['num_regions_examined'])
            self.assertEqual(sum(v>=95 for v in a),source['global_return']['observations']['num_atypical_regions'])

    def test_completeness_changes_judgment_without_changing_claim(self):
        rows=[r for r in examples(self.tools(),2) if r['family']=='source_completeness']
        self.assertEqual(rows[0]['input']['待核回答'],rows[1]['input']['待核回答'])
        self.assertEqual([r['target']['结论'] for r in rows],['revise','uncertain'])
        self.assertEqual(rows[1]['target']['问题'][0]['状态'],'未决')

    def test_all_targets_resolve_and_no_actual_images_or_invented_final_label(self):
        rows=list(examples(self.tools(),4))
        self.assertEqual(len(rows),16)
        self.assertEqual(len({r['id'] for r in rows}),16)
        self.assertTrue(all(r['provenance']['actual_images']==0 for r in rows))
        self.assertTrue(all(not r['provenance']['natural_actor_output'] for r in rows))
        self.assertFalse(any('最终判定为fake' in p['建议'] for r in rows for p in r['target']['问题']))
        wrong=next(r for r in rows if r['family']=='call_budget' and r['target']['结论']=='revise')
        budget=next(c['value'] for c in wrong['input']['证据卡'] if c['path']==['budget'])
        self.assertEqual(budget['remaining_calls'],0)

    def test_missing_enum_is_not_invented_and_mixed_errors_not_hidden(self):
        rows=list(examples(self.tools(),7))
        interface=[r for r in rows if r['family']=='stop_enum_visibility']
        self.assertEqual([r['target']['结论'] for r in interface],['revise','uncertain'])
        self.assertEqual(interface[0]['input']['待核回答'],interface[1]['input']['待核回答'])
        mixed=next(r for r in rows if r['family']=='mapping_policy_boundary' and r['target']['结论']=='revise')
        self.assertEqual({p['状态'] for p in mixed['target']['问题']},{'明确错误','未决'})


if __name__=='__main__':
    unittest.main()
