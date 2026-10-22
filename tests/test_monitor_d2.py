import copy
import unittest

from experiments.faithbench_monitor_v0.monitor_mechanism_v1.prepare_d2 import messages
from experiments.faithbench_monitor_v0.monitor_mechanism_v1.finalize_d2_api import transport_feedback


class D2InputTests(unittest.TestCase):
    def setUp(self):
        self.package = {'cases':{'case':{'prefix':[{'role':'system','content':'original'},
            {'role':'assistant','content':'invalid verdict'}]}},'general':'普通复核提醒',
            'review_contract':{'known':'共同规则','unknown':'未定义权重'},'suffix':'共同接口'}
        self.delivery = {'case':{'G':{'content':'未经筛选的反馈'},'M':{'content':'未经筛选的反馈'}}}

    def test_external_controls_receive_equal_contract_and_raw_feedback(self):
        self.assertEqual(messages(self.package,self.delivery,'case','G'),
                         messages(self.package,self.delivery,'case','M'))
        for arm in ('S','G','M'):
            trail = messages(self.package,self.delivery,'case',arm)
            self.assertEqual(trail[:-1],self.package['cases']['case']['prefix'])
            self.assertIn('共同规则',trail[-1]['content'])
            self.assertIn('未定义权重',trail[-1]['content'])
            if arm != 'S':
                self.assertIn(self.delivery['case'][arm]['content'],trail[-1]['content'])

    def test_each_branch_preserves_original_and_isolates_state(self):
        before = copy.deepcopy(self.package)
        s = messages(self.package,self.delivery,'case','S')
        m = messages(self.package,self.delivery,'case','M')
        s[0]['content'] = 'mutated'
        self.assertEqual(m[0]['content'],'original')
        self.assertEqual(self.package,before)
        self.assertEqual(m[1]['content'],'invalid verdict')

    def test_feedback_quality_is_not_a_delivery_filter(self):
        raw = '  这是可能错误的建议：要求不合法标签。\n'
        delivered = transport_feedback({'content':raw,'finish_reason':'stop'},{'status':'complete'})
        self.assertTrue(delivered['eligible'])
        self.assertEqual(delivered['content'],raw)
        self.assertFalse(delivered['semantic_quality_checked'])

    def test_empty_truncated_and_failed_feedback_preserve_failure(self):
        for response,state in [({'content':' ','finish_reason':'stop'},{'status':'complete'}),
            ({'content':'partial','finish_reason':'length'},{'status':'complete'}),
            ({'content':'text','finish_reason':'stop'},{'status':'failed_or_uncertain_no_retry'}),({}, {})]:
            self.assertFalse(transport_feedback(response,state)['eligible'])


if __name__ == '__main__':
    unittest.main()
