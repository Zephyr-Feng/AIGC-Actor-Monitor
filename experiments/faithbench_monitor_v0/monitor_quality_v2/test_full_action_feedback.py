from copy import deepcopy
import json
from pathlib import Path
import unittest

from .full_action_feedback import edit_messages, review_messages, text_view, validate_revision

ROOT = Path(__file__).resolve().parents[3]


class FullActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = json.loads((ROOT/'data/monitor_net_gain_v1_20261021/natural_rows.json').read_text(encoding='utf-8'))
        cls.row = next(r for r in rows if r['source_id'] == 'case_016')

    def test_known_residual_is_visible_and_editable(self):
        original = self.row['original_action']
        self.assertIn('局部纹理分析与全局表征分析方向冲突', text_view(original))
        user = json.loads(review_messages(self.row)[1]['content'])
        self.assertIn('[unresolved_conflicts/0]', user['待核回答'])
        changed = deepcopy(original)
        changed['unresolved_conflicts'] = ['local与comp实际信号相反，仍需说明取舍依据。']
        accepted = validate_revision(original, '```json\n'+json.dumps(changed, ensure_ascii=False)+'\n```')
        self.assertEqual(accepted, changed)
        empty_gap = deepcopy(original)
        empty_gap['evidence_gap'] = ''
        self.assertEqual(validate_revision(empty_gap, json.dumps(empty_gap)), empty_gap)

    def test_cannot_change_original_evidence_or_label(self):
        original = self.row['original_action']
        for key in ('direction', 'observation', 'source'):
            changed = deepcopy(original)
            changed['current_evidence'][0][key] = 'changed'
            with self.assertRaises(ValueError):
                validate_revision(original, json.dumps(changed))
        changed = deepcopy(original)
        changed['final_verdict'] = 'fake' if original['final_verdict'] == 'real' else 'real'
        with self.assertRaises(ValueError):
            validate_revision(original, json.dumps(changed))

    def test_invalid_feedback_can_be_reviewed_without_automatic_rollback(self):
        messages = edit_messages(self.row, 'raw critique', 'missing evidence id')
        user = json.loads(messages[1]['content'][-1]['text'])
        self.assertEqual(user['外部审核原文'], 'raw critique')
        self.assertEqual(user['审核格式检查'], 'missing evidence id')
        self.assertEqual(user['原始完整动作'], self.row['original_action'])

    def test_patch_or_empty_explanations_cannot_pass(self):
        original = self.row['original_action']
        with self.assertRaises(ValueError):
            validate_revision(original, '{"修改": []}')
        changed = deepcopy(original)
        changed['evidence_gap'] = ''
        with self.assertRaises(ValueError):
            validate_revision(original, json.dumps(changed))


if __name__ == '__main__':
    unittest.main()
