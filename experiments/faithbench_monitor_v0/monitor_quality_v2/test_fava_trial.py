import json
import unittest
from fava_trial import score, pack, resume_cursor


class TrialTests(unittest.TestCase):
    def test_resume_preserves_prefix_and_rejects_wrong_token_count(self):
        rows = [{'input_ids': list(range(i+3)), 'prefix_length': 1} for i in range(17)]
        seen = sum(len(r['input_ids']) for r in rows[:16])
        state = {'position': 16, 'updates': 1, 'seen_tokens': seen}
        self.assertEqual(resume_cursor(state, rows, list(range(17))), (16, 1, seen, seen-16))
        with self.assertRaises(AssertionError):
            resume_cursor({**state, 'seen_tokens': seen+1}, rows, list(range(17)))

    def setUp(self):
        self.edit = {'起点': 2, '终点': 3, '回答原文': 'B', '建议': 'A'}
        self.row = {'messages': [{}, {'content': json.dumps({'待核回答': 'B B'})}],
                    'target': {'问题': [self.edit]}, 'author_corrected_answer': 'B A'}

    def test_exact_and_wrong_replacement(self):
        self.assertTrue(score(json.dumps(self.row['target']), self.row)['exact_author_corrected_answer'])
        result = score(json.dumps({'问题': [{**self.edit, '建议': 'C'}]}), self.row)
        self.assertTrue(result['edits_valid'])
        self.assertFalse(result['exact_author_edits'])

    def test_invalid_anchor_and_duplicate(self):
        for edits in [[{**self.edit, '回答原文': 'bad'}], [self.edit, self.edit], [{**self.edit, '起点': True}]]:
            self.assertFalse(score(json.dumps({'问题': edits}), self.row)['edits_valid'])

    def test_unmarked_edit(self):
        other = {**self.edit, '起点': 0, '终点': 1}
        self.assertEqual(score(json.dumps({'问题': [other]}), self.row)['edits_outside_author_spans'], 1)

    def test_insertion_before_deletion(self):
        edits = [{'起点': 0, '终点': 0, '回答原文': '', '建议': 'A'}, {'起点': 0, '终点': 1, '回答原文': 'B', '建议': ''}]
        r = {'messages': [{}, {'content': json.dumps({'待核回答': 'B'})}], 'target': {'问题': edits}, 'author_corrected_answer': 'A'}
        self.assertTrue(score(json.dumps({'问题': edits}), r)['exact_author_corrected_answer'])

    def test_prefix(self):
        class Tokenizer:
            def apply_chat_template(self, messages, **options):
                return [1, 2] if options['add_generation_prompt'] else [1, 2, 3]
        self.assertEqual(pack(Tokenizer(), {'messages': [{}, {}, {}]})['prefix_length'], 2)


if __name__ == '__main__':
    unittest.main()
