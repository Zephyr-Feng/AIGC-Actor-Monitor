import json
from pathlib import Path
import tempfile
import unittest

from prepare_pair_review import inspect_output, run


class PairReviewTests(unittest.TestCase):
    def setUp(self):
        self.material = {'待核回答': '值为3。', '证据卡': [{'id': 'E001', 'path': ['值'], 'value': 3}]}
        self.payload = {'结论': 'pass', '问题': [], '保留': [{'回答原文': '值为3。', '证据ID': ['E001']}], '说明': '字段给3。'}

    def output(self, index):
        return {'id': f'dev:{index}', 'raw': json.dumps(self.payload, ensure_ascii=False),
            'source_anchors_valid': True, 'hit_token_cap': False}

    def test_missing_output_is_pending_and_valid_anchor_is_not_semantic_proof(self):
        self.assertIsNone(inspect_output(None, self.material)['contract_and_anchors_valid'])
        checked = inspect_output(self.output(0), self.material)
        self.assertTrue(checked['contract_and_anchors_valid'])
        self.assertFalse(checked['semantic_verified'])

    def test_existing_id_with_nonexistent_quote_is_rejected(self):
        bad = self.output(0)
        bad['raw'] = bad['raw'].replace('值为3。', '值为4。')
        bad['source_anchors_valid'] = False
        checked = inspect_output(bad, self.material)
        self.assertTrue(checked['json_parsed'])
        self.assertFalse(checked['contract_and_anchors_valid'])

    def fixture(self, root):
        pack, saved = root / 'pack', root / 'saved'
        pack.mkdir(); saved.mkdir()
        inputs = [{'id': f'dev:{i}', 'group': f'g{i}', 'messages': [{'role': 'user', 'content': json.dumps(self.material)}]} for i in range(80)]
        refs = [{'id': r['id'], 'original_reference': {'unchanged': True}} for r in inputs]
        reviews = [{'id': r['id'], 'raw_modified': False, 'human_gold': False} for r in inputs]
        for path, values in [(pack / 'proposed_development.inputs.jsonl', inputs),
                             (pack / 'proposed_development.references.jsonl', refs),
                             (saved / 'before.jsonl', [self.output(i) for i in range(80)]),
                             (root / 'reviews.jsonl', reviews)]:
            path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in values), encoding='utf8')
        return pack, saved, root / 'reviews.jsonl'

    def test_all_80_kept_without_after_and_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pack, saved, reviews = self.fixture(root)
            summary = run(pack, saved, reviews, root / 'out')
            self.assertEqual(summary['missing_after_rows'], 80)
            self.assertFalse(summary['review_ready'])
            packets = [json.loads(r) for r in (root / 'out/review_packets.jsonl').read_text(encoding='utf8').splitlines()]
            self.assertEqual(len(packets), 80)
            self.assertTrue(all(r['after'] is None and r['after_content_review'] is None for r in packets))
            with self.assertRaises(FileExistsError):
                run(pack, saved, reviews, root / 'out')

    def test_reordered_after_is_not_accepted_as_a_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pack, saved, reviews = self.fixture(root)
            (saved / 'after.jsonl').write_text(json.dumps(self.output(1)) + '\n', encoding='utf8')
            with self.assertRaisesRegex(AssertionError, 'ordered prefix'):
                run(pack, saved, reviews, root / 'out')
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
