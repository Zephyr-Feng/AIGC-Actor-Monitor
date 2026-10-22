import copy
import unittest
from convert_fava import convert
from test_convert_fava import row
from screen_fava import assess, duplicate_decisions, source_groups


def example():
    return convert(row('Long context B.', 'Long context <entity><mark>A</mark><delete>B</delete></entity>.'), 1)


class ScreeningTests(unittest.TestCase):
    def test_transitive_groups_include_partial_and_normalize_whitespace(self):
        rows = [example() for _ in range(4)]
        for i, r in enumerate(rows):
            r['input']['待核回答'] = str(i)
        rows[0]['input']['证据卡'] = [{'text': 'source A'}]
        rows[1]['input']['证据卡'] = [{'text': 'source A'}, {'text': 'source B'}]
        rows[1]['supervision']['all_flagged_issues_have_explicit_edits'] = False
        rows[2]['input']['证据卡'] = [{'text': 'source  B'}]
        rows[3]['input']['证据卡'] = [{'text': 'different'}]
        groups = source_groups(rows)
        self.assertEqual(groups[:3], [groups[0]] * 3)
        self.assertNotEqual(groups[0], groups[3])

    def test_duplicate_and_conflict(self):
        first = example()
        second = copy.deepcopy(first)
        self.assertEqual(duplicate_decisions([first, second]), {1: 'duplicate_input_and_annotation'})
        second['supervision']['issues'][0]['replacement'] = 'C'
        self.assertEqual(duplicate_decisions([first, second]), {0: 'conflicting_annotation', 1: 'conflicting_annotation'})

    def test_noop_empty_and_broad(self):
        self.assertEqual(assess(example())[0], 'candidate')
        noop = convert(row('Long context B.', 'Long context <entity><mark>B</mark><delete>B</delete></entity>.'), 1)
        self.assertEqual(assess(noop)[0], 'contains_no_effective_edit')
        broad = convert(row('B', '<entity><mark>A</mark><delete>B</delete></entity>'), 1)
        self.assertEqual(assess(broad)[0], 'broad_edit_review')
        empty = convert(row('B', '<contradictory><delete>B</delete></contradictory>'), 1)
        self.assertEqual(assess(empty)[0], 'empty_input_or_target')

    def test_partial_and_bad_replay(self):
        partial = convert(row('B', '<unverifiable>B</unverifiable>'), 1)
        self.assertEqual(assess(partial)[0], 'partial_supervision')
        broken = example()
        broken['supervision']['corrected_answer'] = 'wrong'
        with self.assertRaises(ValueError):
            assess(broken)


if __name__ == '__main__':
    unittest.main()
