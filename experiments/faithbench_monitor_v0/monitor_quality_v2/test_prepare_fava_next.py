import json
import unittest
from prepare_fava_next import compact


def row(answer, edits, corrected):
    return {'messages': [{'role': 'system', 'content': ''}, {'role': 'user', 'content': json.dumps({'待核回答': answer})}],
            'target': {'问题': [{'起点': a, '终点': b, '回答原文': answer[a:b], '建议': text} for a, b, text in edits]},
            'author_corrected_answer': corrected}


class CompactTests(unittest.TestCase):
    def test_repeated_and_insertion(self):
        result, reason = compact(row('cat cat', [(4, 7, 'dog')], 'cat dog'))
        self.assertIsNone(reason)
        self.assertEqual(result['target']['问题'][0]['回答原文'], ' cat')
        result, reason = compact(row('ab', [(1, 1, 'X')], 'aXb'))
        self.assertIsNone(reason)
        self.assertTrue(result['target']['问题'][0]['回答原文'])

    def test_delete_and_empty(self):
        result, reason = compact(row('abc', [(1, 2, '')], 'ac'))
        self.assertEqual(result['target']['问题'][0]['建议'], '')
        result, reason = compact(row('abc', [], 'abc'))
        self.assertEqual(result['target'], {'问题': []})

    def test_overlap_and_unanchorable(self):
        result, reason = compact(row('', [(0, 0, 'X')], 'X'))
        self.assertIsNone(result)
        self.assertEqual(reason, 'no_unique_anchor_within_neighbor_bounds')
        result, reason = compact(row('aa', [(0, 1, 'b'), (1, 2, 'c')], 'bc'))
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
