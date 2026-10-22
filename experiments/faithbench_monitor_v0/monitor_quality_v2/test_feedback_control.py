from copy import deepcopy
import unittest

from feedback_control import actor_request, apply_decisions, compare_fields, prepare
from prepare_feedback_control_run import apply_to_action, project


class FeedbackControlTests(unittest.TestCase):
    def payload(self, quote='周二23点关门', state='明确错误'):
        return {'结论': 'uncertain' if state == '未决' else 'revise', '问题': [
            {'状态': state, '回答原文': quote, '证据ID': ['E1'], '理由': '来源为20点', '建议': '改为周二20点关门'}],
            '保留': [], '说明': '核对时间'}

    def prepared(self, answer='周二23点关门', payload=None, **kwargs):
        return prepare(answer, [{'id': 'E1', 'value': '周二20点关门'}], payload or self.payload(), **kwargs)

    def decision(self, quote='周二23点关门', replacement='周二20点关门', number=1, choice='接受'):
        return {'问题编号': number, '决定': choice, '依据': '原始E1给出20点', '证据ID': ['E1'],
                '回答原文': quote, '替换文本': replacement}

    def test_local_patch_preserves_surroundings_and_inputs(self):
        p = self.prepared('开头。周二23点关门。尾部。'); before = deepcopy(p)
        result = apply_decisions(p, {'复核': [self.decision()]})
        self.assertEqual(result['answer'], '开头。周二20点关门。尾部。')
        self.assertEqual(p, before)
        self.assertFalse(result['semantic_verified'])

    def test_invalid_reference_rejects_whole_feedback(self):
        payload = self.payload(); payload['问题'][0]['证据ID'] = ['E003']
        p = self.prepared(payload=payload)
        self.assertEqual(p['status'], 'rejected_feedback')
        self.assertIsNone(actor_request(p))
        self.assertEqual(apply_decisions(p, None)['answer'], p['answer'])

    def test_ambiguous_quote_is_unresolved(self):
        self.assertEqual(self.prepared('周二23点关门，周二23点关门')['status'], 'unresolved')

    def test_unresolved_routing_differs_between_arms(self):
        payload = self.payload(state='未决')
        self.assertEqual(self.prepared(payload=payload)['status'], 'unresolved')
        self.assertEqual(self.prepared(payload=payload, controlled=False)['status'], 'ready')

    def test_noop_feedback_filtered(self):
        payload = self.payload(); payload['问题'][0]['建议'] = ' 周二23点关门 '
        self.assertEqual(self.prepared(payload=payload)['items'][0]['route'], 'filtered')

    def test_internal_whitespace_is_not_assumed_semantically_irrelevant(self):
        payload = self.payload('now here'); payload['问题'][0]['建议'] = 'nowhere'
        p = self.prepared('now here', payload)
        self.assertEqual(p['status'], 'ready')
        result = apply_decisions(p, {'复核': [self.decision('now here', 'nowhere')]})
        self.assertEqual(result['answer'], 'nowhere')

    def test_region_boundary_checked(self):
        p = self.prepared('周二23点关门。其他', allowed_ranges=[(8, 10)])
        self.assertEqual(p['status'], 'unresolved')

    def test_rejection_and_unresolved_do_not_edit(self):
        for choice, expected in [('拒绝', 'retained'), ('未决', 'unresolved')]:
            result = apply_decisions(self.prepared(), {'复核': [self.decision(replacement=None, choice=choice)]})
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['answer'], '周二23点关门')

    def test_missing_duplicate_unknown_and_malformed_decisions_rollback(self):
        for payload in ({}, {'复核': []}, {'复核': [self.decision(), self.decision()]},
                        {'复核': [self.decision(number=True)]}, {'复核': [self.decision(number=2)]}):
            result = apply_decisions(self.prepared(), payload)
            self.assertEqual(result['status'], 'rolled_back')
            self.assertEqual(result['answer'], '周二23点关门')

    def test_actor_cannot_invent_quote_or_evidence(self):
        for key, value in [('回答原文', '周五23点关门'), ('证据ID', ['E003'])]:
            decision = self.decision(); decision[key] = value
            self.assertEqual(apply_decisions(self.prepared(), {'复核': [decision]})['status'], 'rolled_back')

    def test_overlap_rolls_back_related_edits_only(self):
        answer = '周二23点关门，周三21点关门'
        payload = self.payload(); payload['问题'] += [dict(payload['问题'][0], 回答原文='23点'),
                                                   dict(payload['问题'][0], 回答原文='周三21点关门')]
        decisions = [self.decision(), self.decision('23点', '20点', 2), self.decision('周三21点关门', '周三20点关门', 3)]
        result = apply_decisions(self.prepared(answer, payload), {'复核': decisions})
        self.assertEqual(result['answer'], '周二23点关门，周三20点关门')
        self.assertEqual(result['status'], 'revised_with_unresolved')
        self.assertEqual([x['applied'] for x in result['records']], [False, False, True])

    def test_identical_duplicate_edits_are_applied_once(self):
        payload = self.payload(); payload['问题'].append(deepcopy(payload['问题'][0]))
        result = apply_decisions(self.prepared(payload=payload), {'复核': [self.decision(), self.decision(number=2)]})
        self.assertEqual(result['answer'], '周二20点关门')
        self.assertEqual(len(result['edits']), 1)

    def test_pass_is_retained_without_semantic_certification(self):
        payload = {'结论': 'pass', '问题': [], '保留': [{'回答原文': '周二23点关门', '证据ID': ['E1']}], '说明': '声称支持'}
        result = apply_decisions(self.prepared(payload=payload), None)
        self.assertEqual(result['status'], 'retained')
        self.assertFalse(result['semantic_verified'])

    def test_valid_anchors_do_not_block_semantically_bad_deletion(self):
        result = apply_decisions(self.prepared(), {'复核': [self.decision(replacement='')]})
        self.assertEqual(result['answer'], '')
        self.assertFalse(result['semantic_verified'])

    def test_request_preserves_original_evidence(self):
        text = actor_request(self.prepared())
        self.assertIn('周二20点关门', text)
        self.assertIn('允许拒绝建议', text)

    def test_explicit_field_mapping_does_not_guess_context_or_null(self):
        field = dict(entity='门店A', attribute='romantic', time='当前', unit='', value=False)
        self.assertEqual(compare_fields(dict(field, value=True), field), 'conflict')
        self.assertEqual(compare_fields(dict(field, value=None), field), 'unverified')
        self.assertEqual(compare_fields(dict(field, entity='门店B'), field), 'unverified')
        self.assertEqual(compare_fields(dict(field, time='去年'), field), 'unverified')
        self.assertEqual(compare_fields(dict(field, unit='小时'), field), 'unverified')
        self.assertEqual(compare_fields(dict(field, value=0), field), 'unverified')
        self.assertEqual(compare_fields(field, field), 'supported')

    def test_action_projection_preserves_labels_direction_and_source(self):
        original = dict(action_reason='原理由', evidence_gap='缺口', final_verdict='fake', final_confidence='high',
                        current_evidence=[dict(source='global', observation='原观察', interpretation='原解释', direction='fake')])
        answer, regions = project(original)
        first = regions[0]
        edits = [dict(start=first['start'], end=first['end'], replacement='新理由')]
        changed = apply_to_action(original, regions, edits)
        self.assertEqual(changed, dict(original, action_reason='新理由'))
        self.assertEqual(project(changed)[0], answer.replace('原理由', '新理由'))
        with self.assertRaises(AssertionError):
            apply_to_action(original, regions, [dict(start=0, end=2, replacement='越界')])


if __name__ == '__main__':
    unittest.main()
