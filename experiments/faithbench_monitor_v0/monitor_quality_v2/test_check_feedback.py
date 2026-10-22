import json
import unittest
from check_feedback import check


class FeedbackChecks(unittest.TestCase):
    def payload(self,quote='blue',location='passage 1'):
        return json.dumps({'结论':'revise','问题':[{'回答原文':'red','来源原文':quote,'来源位置':location,'理由':'颜色不一致','建议':'按来源改蓝色'}],'说明':'颜色冲突'})

    def test_real_anchors_are_not_semantic_certification(self):
        result=check('passage 1:blue','red',self.payload())
        self.assertTrue(result['anchors_valid'])
        self.assertFalse(result['semantic_verified'])

    def test_wrong_passage_and_invented_quote(self):
        result=check({'passages':'passage 1:blue\npassage 2:green'},'red',self.payload(location='passage 2'))
        self.assertIn('quote_not_in_named_passage',[x['reason'] for x in result['failures']])
        self.assertFalse(check('blue','red',self.payload(location='passage 10'))['anchors_valid'])
        self.assertFalse(check('blue','red',self.payload(quote='purple'))['anchors_valid'])

    def test_invalid_contract_and_correct_pass(self):
        self.assertFalse(check('blue','red','{"结论":null}')['contract_valid'])
        self.assertFalse(check('blue','red',json.dumps({'结论':'revise','问题':[],'说明':'缺反馈'}))['contract_valid'])
        result=check('blue','blue',json.dumps({'结论':'pass','问题':[],'说明':'来源与回答一致'}))
        self.assertTrue(result['anchors_valid'])
        self.assertFalse(result['semantic_verified'])


if __name__=='__main__':
    unittest.main()
