import copy
import json
from pathlib import Path
import tempfile
import unittest

from prepare_natural_full import packets, refresh, validate_review


class FullReviewTests(unittest.TestCase):
    def setUp(self):
        self.cards = [{'id': 'E001', 'path': [], 'value': 'The source says one.'}]
        self.label = {'start': 0, 'end': 3, 'text': 'two'}
        self.record = {'id': 'ragtruth:1', 'group': 'g1', 'split': 'train',
                       'input': {'原始资料': 'The source says one.', '待核回答': 'two and two'}, 'target': {}}
        self.candidate = {'id': 'c1', 'origin': 'ragtruth:1', 'group': 'g1',
                          'input': {'证据卡': self.cards, '待核回答': 'two and two'},
                          'human_span_annotation': self.label}

    def make_packet(self):
        second = copy.deepcopy(self.candidate)
        second.update(id='c2', human_span_annotation={'start': 8, 'end': 11, 'text': 'two'})
        return packets([self.candidate, second], {'ragtruth:1': self.record},
                       {'ragtruth:1': {'labels': [self.label, second['human_span_annotation']]}})[0]

    def review(self):
        return {'origin': 'ragtruth:1', 'group': 'g1', 'human_gold': False, 'approved_for_training': False,
                'reviewer': 'assistant_nonblind', 'full_source_read': True, 'full_answer_read': True,
                'status': 'assistant_reference_prepared', 'author_annotation_assessment': 'Both spans preserved.',
                'coverage_note': 'Both repeated errors reviewed.',
                'target': {'结论': 'revise', '问题': [{'状态': '明确错误', '回答原文': 'two', '证据ID': ['E001'],
                            '理由': '来源为一，两次都写成二。', '建议': '两处二均改为一。'}], '保留': [], '说明': '已核全文。'}}

    def test_merge_preserves_spans_and_resolves_every_occurrence(self):
        packet = self.make_packet()
        self.assertEqual(len(packet['original_candidates']), 2)
        self.assertEqual(len(packet['author_annotation']['labels']), 2)
        result = validate_review(packet, self.review())
        self.assertEqual(result['feedback']['问题'][0]['定位候选'], [[0, 3], [8, 11]])
        self.assertFalse(result['semantic_verified'])

    def test_bad_source_and_inconsistent_answer_rejected(self):
        self.record['input']['原始资料'] = 'different source'
        with self.assertRaises(ValueError):
            self.make_packet()
        self.record['input']['原始资料'] = 'The source says one.'
        self.candidate['input']['待核回答'] = 'different answer'
        with self.assertRaises(ValueError):
            self.make_packet()

    def test_inherited_hold_stays_in_full_review_order_without_release(self):
        packet = self.make_packet()
        packet['inherited_hold'] = True
        with tempfile.TemporaryDirectory(prefix='natural-full-test-') as temporary:
            output = Path(temporary)
            (output / 'review_packets.jsonl').write_text(json.dumps(packet) + '\n', encoding='utf8')
            summary = refresh(output)
            self.assertEqual(summary['next_pending'], packet['origin'])
            self.assertEqual(summary['awaiting_full_review'], 1)
            self.assertEqual(summary['unreviewed_held_answers'], 1)
            self.assertEqual(summary['pending_answers'], 0)
            review = self.review()
            review['status'] = 'held_for_adjudication'
            (output / 'reviews_001.jsonl').write_text(json.dumps(review) + '\n', encoding='utf8')
            summary = refresh(output)
            self.assertIsNone(summary['next_pending'])
            self.assertEqual(summary['awaiting_full_review'], 0)
            self.assertEqual(summary['held_answers'], 1)
            self.assertEqual(summary['assistant_full_references'], 0)

    def test_hold_gold_and_invalid_evidence_cannot_pass(self):
        packet = self.make_packet()
        packet['inherited_hold'] = True
        with self.assertRaises(ValueError):
            validate_review(packet, self.review())
        packet['inherited_hold'] = False
        review = self.review()
        review['human_gold'] = True
        with self.assertRaises(ValueError):
            validate_review(packet, review)
        review = self.review()
        review['target']['问题'][0]['证据ID'] = ['E999']
        with self.assertRaises(ValueError):
            validate_review(packet, review)


if __name__ == '__main__':
    unittest.main()
