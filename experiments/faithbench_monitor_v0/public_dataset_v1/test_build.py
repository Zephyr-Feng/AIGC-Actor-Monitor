"""Synthetic checks only: no network, model or private research input."""
import unittest
from build import Groups, content_key, ragbench, ragtruth, sft


class DatasetTests(unittest.TestCase):
    def test_preference_position_is_not_distinct_content(self):
        record = {'task': 'visual_feedback_preference', 'image': 'x', 'input': {'问题与候选回答': 'q', '反馈A': 'good', '反馈B': 'bad'}, 'target': {'较优反馈': 'A'}}
        key, target = content_key(record)
        record['input']['反馈A'], record['input']['反馈B'] = 'bad', 'good'
        record['target']['较优反馈'] = 'B'
        self.assertEqual((key, target), content_key(record))
        record['target']['较优反馈'] = 'A'
        self.assertEqual(key, content_key(record)[0])
        self.assertNotEqual(target, content_key(record)[1])

    def test_spans_and_ambiguity(self):
        source = {'source_id': 's', 'source_info': {'count': 9}}
        row = {'quality': 'good', 'response': '有十项', 'labels': [{'start': 1, 'end': 2, 'text': '十', 'label_type': 'Evident Conflict'}]}
        visible, target = ragtruth(row, source)
        self.assertEqual(target['问题片段'][0]['原文'], '十')
        self.assertNotIn('labels', visible)
        row['labels'][0]['text'] = '九'
        with self.assertRaisesRegex(ValueError, 'span_text_mismatch'):
            ragtruth(row, source)
        row['labels'][0]['implicit_true'] = True
        with self.assertRaisesRegex(ValueError, 'requires_review'):
            ragtruth(row, source)

    def test_partial_support_and_invalid_reference(self):
        row = {'question': 'count?', 'documents': ['There are nine items.'], 'response': 'All ten are red.', 'documents_sentences': [[['0a', 'There are nine items.']]], 'response_sentences': [['a', 'All ten are red.']], 'sentence_support_information': [{'response_sentence_key': 'a', 'fully_supported': False, 'supporting_sentence_keys': ['0a']}], 'unsupported_response_sentence_keys': ['a'], 'adherence_score': False}
        _, target = ragbench(row)
        self.assertEqual(target['逐句核对'][0]['判定'], '未完整支持')
        self.assertEqual(target['逐句核对'][0]['原标注依据编号'], ['0a'])
        row['sentence_support_information'][0]['response_sentence_key'] = 'a.'
        row['sentence_support_information'][0]['supporting_sentence_keys'] = ['0a.']
        row['unsupported_response_sentence_keys'] = ['a.']
        _, target = ragbench(row)
        self.assertEqual(target['逐句核对'][0]['原标注依据编号'], ['0a'])
        row['sentence_support_information'][0]['supporting_sentence_keys'] = ['invented']
        with self.assertRaisesRegex(ValueError, 'unknown_support_reference'):
            ragbench(row)
        row['documents_sentences'] = None
        with self.assertRaisesRegex(ValueError, 'missing_sentence_annotations'):
            ragbench(row)

    def test_transitive_groups_and_label_separation(self):
        groups = Groups()
        a = groups.add([('document', 'x')])
        b = groups.add([('question', 'q')])
        c = groups.add([('document', 'x'), ('question', 'q')])
        self.assertEqual(groups.root(a), groups.root(b))
        self.assertEqual(groups.root(c), groups.root(a))
        record = {'id': 'x', 'group': 'g', 'task': 'ragbench_support', 'input': {'原文': 'observation'}, 'target': {'逐句核对': [{'判定': '未完整支持'}]}}
        exported = sft(record)
        self.assertNotIn('逐句核对', exported['messages'][1]['content'].split('材料')[1])
        self.assertIn('未完整支持', exported['messages'][2]['content'])


if __name__ == '__main__':
    unittest.main()
