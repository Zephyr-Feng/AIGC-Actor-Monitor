from copy import deepcopy
import unittest
from actor_only_baseline import apply_response

class ActorOnlyBoundary(unittest.TestCase):
    def setUp(self):
        self.row={'answer':'原句','regions':[{'start':0,'end':2,'path':['action_reason']}],
                  'original_action':{'action_reason':'原句','final_verdict':'real','final_confidence':0.4}}
    def test_bounded_edit_preserves_fixed_fields(self):
        old=deepcopy(self.row)
        out=apply_response(self.row,'{"修改":[{"字段":1,"替换文本":"有据修订"}],"未决":[]}')
        self.assertEqual(out['status'],'revised');self.assertEqual(out['candidate_action']['action_reason'],'有据修订')
        self.assertEqual(out['candidate_action']['final_verdict'],'real');self.assertEqual(self.row,old)
    def test_unresolved_does_not_certify_original(self):
        out=apply_response(self.row,'{"修改":[],"未决":[{"字段":1,"理由":"资料未给"}]}')
        self.assertEqual(out['status'],'unresolved');self.assertEqual(out['answer'],'原句');self.assertFalse(out['semantic_verified'])
    def test_invalid_or_conflicting_field_rolls_back(self):
        for raw in ['{"修改":[{"字段":2,"替换文本":"越界"}],"未决":[]}',
                    '{"修改":[{"字段":true,"替换文本":"越界"}],"未决":[]}',
                    '{"修改":[{"字段":1,"替换文本":""}],"未决":[]}',
                    '{"修改":[{"字段":1,"替换文本":"新句"}],"未决":[{"字段":1,"理由":"未知"}]}']:
            out=apply_response(self.row,raw);self.assertEqual(out['status'],'rolled_back');self.assertEqual(out['edits'],[])
    def test_terminal_label_in_text_is_protected(self):
        out=apply_response(self.row,'{"修改":[{"字段":1,"替换文本":"最终结论为fake"}],"未决":[]}')
        self.assertEqual(out['status'],'rolled_back');self.assertEqual(out['candidate_action'],self.row['original_action'])
if __name__=='__main__':unittest.main()