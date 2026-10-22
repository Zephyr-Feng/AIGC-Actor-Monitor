import json
from pathlib import Path
import unittest

from monitor_net_gain import apply_response, edit_messages, valid_feedback


ROOT = Path(__file__).resolve().parents[3]


class NetGainTests(unittest.TestCase):
    def setUp(self):
        rows = json.loads((ROOT/'data/adviser_test_100_v1_20261021/actor/inputs.json').read_text(encoding='utf8'))
        self.row = next(r for r in rows if r['id'] == 'case_016_native')

    def test_feedback_cannot_invent_source(self):
        r = self.row
        review = {'messages':[{}, {'content':json.dumps({'待核回答':r['answer'], '证据卡':r['cards']})}]}
        payload = dict(结论='pass', 问题=[], 保留=[dict(回答原文=r['answer'][r['regions'][0]['start']:r['regions'][0]['end']], 证据ID=['E999'])], 说明='保留')
        self.assertIsNone(valid_feedback(review, json.dumps(payload))[0])

    def test_arms_have_identical_revision_material_except_feedback(self):
        a, b = edit_messages(self.row, {'说明':'A'}), edit_messages(self.row, {'说明':'B'})
        self.assertEqual(a[0], b[0])
        da, db = (json.loads(m[1]['content'][-1]['text']) for m in (a,b))
        da.pop('外部审核'); db.pop('外部审核')
        self.assertEqual(da, db)
        self.assertEqual(a[1]['content'][:-1], b[1]['content'][:-1])

    def test_edit_changes_only_allowed_field(self):
        payload = {'修改':[{'字段':1,'替换文本':'保留局部与互补工具实际相反的信号。'}], '未决':[]}
        result = apply_response(self.row, json.dumps(payload))
        self.assertEqual(result['status'], 'revised')
        original = dict(self.row['original_action']); original['action_reason'] = payload['修改'][0]['替换文本']
        self.assertEqual(result['candidate_action'], original)

    def test_out_of_scope_edit_rolls_back(self):
        result = apply_response(self.row, json.dumps({'修改':[{'字段':999,'替换文本':'错误'}], '未决':[]}))
        self.assertEqual(result['status'], 'rolled_back')
        self.assertEqual(result['candidate_action'], self.row['original_action'])


if __name__ == '__main__':
    unittest.main()
