"""Check controlled facts, relation coverage and full-answer supervision boundaries."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('relation_coverage', ROOT / 'data/monitor_relation_coverage_v1_20261021/prepare.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = json.loads((ROOT / 'data/monitor_net_gain_sft_v2_20261021/forensic.sources.json').read_text(encoding='utf-8'))
        cls.before = json.dumps(cls.sources, ensure_ascii=False)
        cls.rows = module.build(cls.sources)

    def test_worlds_cover_both_directions_and_protect_originals(self):
        self.assertEqual(len(self.rows), 432)
        self.assertEqual(json.dumps(self.sources, ensure_ascii=False), self.before)
        pairs = set()
        for row in self.rows:
            signals = [x['constructed']['signal'] for x in row['counterfactual_changes']]
            if len(signals) == 2:
                pairs.add(tuple(signals))
        self.assertEqual(pairs, {('real_like', 'real'), ('real_like', 'fake'), ('synthetic_like', 'real'), ('synthetic_like', 'fake')})

    def test_constructed_scores_and_claims_agree(self):
        for row in self.rows:
            for change in row['counterfactual_changes']:
                value = change['constructed']
                threshold = float(module.re.search(r'阈值为\s*([0-9.]+)', value['observation'])[1].rstrip('.'))
                self.assertEqual(value['score'] < threshold, value['signal'] in ('real_like', 'real'))
                self.assertNotIn('strength', value)
            if row['variant'] == 4 and row['relation']:
                target = row['target']['问题'][0]
                signals = [x['constructed']['signal'] for x in row['counterfactual_changes']]
                self.assertTrue(all(s in target['理由'] for s in signals))

    def test_multi_field_errors_and_unknowns_remain_distinct(self):
        for row in self.rows:
            target = row['target']
            if row['variant'] in (1, 2):
                self.assertEqual(len(target['问题']), 3)
            if row['variant'] in (5, 6):
                self.assertEqual(target['结论'], 'uncertain')
                self.assertTrue(all(x['状态'] == '未决' for x in target['问题']))
            if row['variant'] == 7:
                self.assertEqual({x['状态'] for x in target['问题']}, {'未决', '明确错误'})

    def test_cannot_guess_an_unprovided_threshold(self):
        source = json.loads(self.before)[0]
        comp = next(c for c in source['cards'] if c['value'].get('tool') == 'complementary_forensic_analyzer')
        comp['value']['observation'] = '未提供阈值'
        with self.assertRaises(AssertionError):
            module.build([source])


if __name__ == '__main__':
    unittest.main()
