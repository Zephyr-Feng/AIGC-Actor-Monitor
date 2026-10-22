import unittest

from train import score, supervised_positions
from summarize import quote_matches, relaxed_decision


class TrainingContractTests(unittest.TestCase):
    def test_wrapper_sensitivity_is_one_level_only(self):
        self.assertEqual(relaxed_decision('{"输出结构":{"判定":"存在来源忠实性问题","问题片段":[]}}'), '存在来源忠实性问题')
        self.assertIsNone(relaxed_decision('{"输出结构":{"输出结构":{"判定":"存在来源忠实性问题","问题片段":[]}}}'))

    def test_quote_matching_handles_overlap_and_empty(self):
        self.assertEqual(quote_matches('aaa', 'aa'), 2)
        self.assertEqual(quote_matches('a错误b', '错误'), 1)
        self.assertEqual(quote_matches('abc', ''), 0)
        self.assertEqual(quote_matches('abc', 'd'), 0)

    def test_shift_matches_masked_causal_targets(self):
        row = {'input_ids': [10, 11, 12, 20, 21], 'prefix_length': 3}
        positions, target = supervised_positions(row)
        self.assertEqual(positions, [2, 3])
        self.assertEqual(target, [20, 21])
        full_labels = [-100] * 3 + [20, 21]
        self.assertEqual([(i, value) for i, value in enumerate(full_labels[1:]) if value != -100],
                         list(zip(positions, target)))

    def test_span_requires_exact_unicode_slice(self):
        target = {'判定': '存在来源忠实性问题', '问题片段':
                  [{'起点': 1, '终点': 3, '原文': '错误', '原始错误类型': 'Evident Conflict'}]}
        import json
        correct = score(json.dumps(target, ensure_ascii=False), target, '有错误。')
        self.assertTrue(correct['status_correct'] and correct['span_offsets_valid'] and correct['exact_spans'])
        target['问题片段'][0]['起点'] = 0
        wrong_offset = score(json.dumps(target, ensure_ascii=False), target, '有错误。')
        self.assertFalse(wrong_offset['span_offsets_valid'])

    def test_malformed_output_never_counts_as_success(self):
        target = {'判定': '未标注来源忠实性问题', '问题片段': []}
        for raw in ('not json', '{"问题片段": []}', 'null'):
            result = score(raw, target, '')
            self.assertFalse(result['json_valid'] or result['status_correct'])


if __name__ == '__main__':
    unittest.main()
