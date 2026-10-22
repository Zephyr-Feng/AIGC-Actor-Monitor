from copy import deepcopy
import json
from pathlib import Path
import unittest

from typed_feedback import apply_verified, verify


class TypedFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        rows = json.loads((root/'data/feedback_control_v1_20261020/inputs.json').read_text(encoding='utf8'))
        cls.rows = {r['id']: r for r in rows if r['kind'] == 'image_development'}

    def global_proposal(self, row):
        index = next(i for i, e in enumerate(row['original_action']['current_evidence']) if e['source'] == 'global_forensic_analyzer')
        ref = next(c['id'] for c in row['cards'] if isinstance(c['value'], dict) and c['value'].get('tool') == 'global_forensic_analyzer')
        return dict(rule='global_direction', evidence_id=ref, actor_index=index,
                    observed=row['original_action']['current_evidence'][index]['direction'], proposed='inconclusive')

    def test_verified_field_repair_preserves_labels_and_other_fields(self):
        for cid in ('case_005', 'case_016'):
            row = self.rows[cid]; original = row['original_action']; snapshot = deepcopy(original)
            proposal = self.global_proposal(row)
            result = apply_verified(original, row['cards'], proposal)
            self.assertEqual(result['verification']['status'], 'verified_repair' if cid == 'case_005' else 'already_valid')
            expected = deepcopy(original)
            if cid == 'case_005':
                expected['current_evidence'][proposal['actor_index']]['direction'] = 'inconclusive'
            self.assertEqual(result['candidate_action'], expected)
            self.assertEqual(original, snapshot)
            self.assertFalse(result['ready_for_publication'])

    def test_bad_binding_false_observed_value_and_bad_id_rejected(self):
        row = self.rows['case_005']; proposal = self.global_proposal(row)
        for key, value in [('evidence_id', []), ('evidence_id', 'E999'), ('actor_index', True),
                           ('observed', 'real'), ('proposed', 'fake')]:
            invalid = dict(proposal, **{key: value})
            self.assertEqual(verify(row['original_action'], row['cards'], invalid)['status'], 'rejected')

    def relation(self, row, claim):
        refs = [c['id'] for c in row['cards'] if isinstance(c['value'], dict) and c['value'].get('tool') in
                ('local_texture_analyzer', 'complementary_forensic_analyzer')]
        return dict(rule='signal_relation', evidence_ids=refs, claim=claim)

    def test_false_monitor_conflict_assertion_rejected_fact_not_error_proof(self):
        for cid in ('case_016', 'case_017'):
            row = self.rows[cid]
            wrong = apply_verified(row['original_action'], row['cards'], self.relation(row, 'same'))
            self.assertEqual(wrong['verification']['status'], 'rejected_false_assertion')
            self.assertEqual(wrong['candidate_action'], row['original_action'])
            correct = verify(row['original_action'], row['cards'], self.relation(row, 'opposed'))
            self.assertEqual(correct['status'], 'verified_fact_only')
            self.assertIsNone(correct['patch'])

    def test_missing_signal_is_unresolved_not_same(self):
        row = self.rows['case_016']; cards = deepcopy(row['cards'])
        next(c for c in cards if isinstance(c['value'], dict) and c['value'].get('tool') == 'local_texture_analyzer')['value']['signal'] = None
        self.assertEqual(verify(row['original_action'], cards, self.relation(row, 'same'))['status'], 'unresolved')

    def test_illegal_stop_records_error_without_picking_real_or_fake(self):
        row = self.rows['case_017']; proposal = dict(rule='stop_enum', observed=row['original_action']['final_verdict'])
        result = apply_verified(row['original_action'], row['cards'], proposal)
        self.assertEqual(result['verification']['status'], 'unresolved_protected_field')
        self.assertEqual(result['candidate_action'], row['original_action'])
        self.assertEqual(verify(row['original_action'], row['cards'], {'rule': 'free_prose'})['status'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
