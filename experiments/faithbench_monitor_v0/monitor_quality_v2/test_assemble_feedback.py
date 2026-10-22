from copy import deepcopy
import unittest
from assemble_feedback import assemble


class AssembleFeedbackTests(unittest.TestCase):
    def cards(self):
        return [{'id':'E2','path':['hours','Tuesday'],'value':'11:0-20:0'}]

    def payload(self):
        return {'结论':'revise','问题':[{'状态':'明确错误','回答原文':'周二23点关门','证据ID':['E2'],'理由':'来源记录20点','建议':'改为周二20点关门'}],
            '保留':[],'说明':'关门时间冲突'}

    def test_original_evidence_filled_and_inputs_unchanged(self):
        payload=self.payload();snapshot=deepcopy(payload)
        result=assemble('周二23点关门',self.cards(),payload)
        self.assertEqual(result['feedback']['问题'][0]['来源'][0]['value'],'11:0-20:0')
        self.assertEqual(payload,snapshot)
        self.assertFalse(result['semantic_verified'])

    def test_unknown_id_and_invented_quote_rejected(self):
        for key,value in (('证据ID',['E10']),('回答原文','周五22点关门')):
            payload=self.payload();payload['问题'][0][key]=value
            with self.assertRaises(ValueError):assemble('周二23点关门',self.cards(),payload)

    def test_real_id_is_not_proof_of_correct_reason(self):
        payload=self.payload();payload['问题'][0]['理由']='错误地说来源是19点'
        result=assemble('周二23点关门',self.cards(),payload)
        self.assertTrue(result['source_anchors_verified'])
        self.assertFalse(result['semantic_verified'])

    def test_repeat_is_not_assigned_a_position(self):
        result=assemble('周二23点关门，周二23点关门',self.cards(),self.payload())
        self.assertFalse(result['feedback']['问题'][0]['定位唯一'])
        self.assertEqual(len(result['feedback']['问题'][0]['定位候选']),2)

    def test_vacuous_pass_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):assemble('正确内容',self.cards(),{'结论':'pass','问题':[],'保留':[],'说明':'全部正确'})
        with self.assertRaises(ValueError):assemble('周二23点关门',self.cards()*2,self.payload())

    def test_unresolved_is_not_forced_into_confirmed_error(self):
        payload=self.payload();payload['结论']='uncertain';payload['问题'][0]['状态']='未决'
        self.assertFalse(assemble('周二23点关门',self.cards(),payload)['semantic_verified'])
        payload['结论']='revise'
        with self.assertRaises(ValueError):assemble('周二23点关门',self.cards(),payload)


if __name__=='__main__':
    unittest.main()
