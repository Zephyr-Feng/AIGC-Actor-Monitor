"""Check the observed supervision defects and preserve frozen evidence."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('repair_existing', ROOT / 'data/monitor_supervision_audit_20261021/repair_existing.py')
repair_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair_module)


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads((ROOT / 'data/monitor_net_gain_sft_v2_20261021/train.json').read_text(encoding='utf-8'))
        cls.fixed, cls.ledger = repair_module.repair(cls.original)
        cls.by_id = {r['id']: r for r in cls.fixed}

    def test_residual_is_labeled_without_changing_native(self):
        old = next(r for r in self.original if r['id'] == 'case_002_native_full')
        new = self.by_id[old['id']]
        self.assertEqual(old['messages'][1], new['messages'][1])
        self.assertEqual(len(new['target']['问题']), 5)
        answer = json.loads(self.by_id['case_002_corrected_full']['messages'][1]['content'])['待核回答']
        self.assertNotIn('现有证据矛盾未解', answer)

    def test_source_and_signal_claims_are_grounded(self):
        target = json.loads(self.by_id['case_001_provenance_error']['messages'][-1]['content'])
        self.assertIn('已返回inconclusive', target['问题'][0]['理由'])
        self.assertIn('E003', target['问题'][0]['证据ID'])
        relation = self.by_id['case_002_global_chain_full']['target']['问题'][0]
        self.assertIn('real_like', relation['理由'])
        self.assertIn('E004', relation['证据ID'])

    def test_public_data_and_natural_answers_are_preserved(self):
        for before, after in zip(self.original, self.fixed):
            if before['task'].startswith('public_'):
                self.assertEqual(before, after)
            if before['id'].endswith('_native_full'):
                self.assertEqual(before['messages'][1], after['messages'][1])

    def test_missing_expected_quote_fails_closed(self):
        broken = [r for r in self.original if r['id'] == 'case_002_corrected_full']
        broken = json.loads(json.dumps(broken))
        material = json.loads(broken[0]['messages'][1]['content'])
        material['待核回答'] = material['待核回答'].replace('现有证据矛盾未解', 'different')
        broken[0]['messages'][1]['content'] = json.dumps(material)
        with self.assertRaises(AssertionError):
            repair_module.repair(broken)


if __name__ == '__main__':
    unittest.main()
