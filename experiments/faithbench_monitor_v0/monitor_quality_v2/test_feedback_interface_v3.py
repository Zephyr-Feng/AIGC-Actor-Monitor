import unittest
from feedback_interface_v3 import explicit_labels, fact_ledger, messages, normalize
import test_feedback_interface_v2 as fixtures


class LedgerTests(unittest.TestCase):
    def test_empty_ledger_produces_identical_input_for_reuse(self):
        row = fixtures.ExplicitOperationTests().row()
        self.assertEqual(messages(row, 'S'), messages(row, 'T'))

    def cards(self, signal='real'):
        return [{'id': 'L', 'value': {'tool': 'local_texture_analyzer', 'signal': 'synthetic_like'}},
                {'id': 'C', 'value': {'tool': 'complementary_forensic_analyzer', 'signal': signal}}]

    def test_raw_direction_comparison_is_not_final_verdict(self):
        entry = fact_ledger(self.cards())[-1]
        self.assertIs(entry['值'], True)
        self.assertNotIn('final_verdict', entry)
        self.assertIs(fact_ledger(self.cards('fake'))[-1]['值'], False)
        self.assertIsNone(fact_ledger(self.cards(None))[-1]['值'])
        self.assertIsNone(fact_ledger(self.cards()[:1])[-1]['值'])

    def test_numbers_and_limits_are_copied_without_a_mean(self):
        card = {'id': 'G', 'value': {'tool': 'global_forensic_analyzer', 'scope': {'num_regions_examined': 13},
                'observations': {'num_atypical_regions': 3}, 'limitations': '偏离不证明来源'}}
        entry = fact_ledger([card])[0]
        self.assertEqual(entry['scope']['num_regions_examined'], 13)
        self.assertEqual(entry['observations'], {'num_atypical_regions': 3})

    def test_no_repeated_source_quote_required(self):
        row = fixtures.ExplicitOperationTests().row()
        response = {'复核': [{'问题编号': 1, '操作': '替换原句', '依据': 'E1明确13个', '证据ID': ['E1'],
                              '回答原文': '检查3个区域', '替换文本': '检查13个区域'}]}
        self.assertEqual(normalize(response, row)['复核'][0]['决定'], '接受')

    def test_explicit_terminal_change_is_blocked(self):
        row = fixtures.ExplicitOperationTests().row()
        row['answer'] = '最终结论为 inconclusive。'
        row['feedback']['问题'][0]['回答原文'] = row['answer']
        response = {'复核': [{'问题编号': 1, '操作': '替换原句', '依据': '仅测试越界', '证据ID': ['E1'],
                              '回答原文': row['answer'], '替换文本': '最终结论为 fake。'}]}
        with self.assertRaisesRegex(ValueError, 'outside_scope'):
            normalize(response, row)
        self.assertEqual(explicit_labels('final_verdict=real。'), ['real'])


if __name__ == '__main__':
    unittest.main()
