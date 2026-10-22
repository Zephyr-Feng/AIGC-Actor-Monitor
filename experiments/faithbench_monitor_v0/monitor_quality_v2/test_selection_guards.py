"""CPU checks for observed execution failures; these are not semantic evals."""
import unittest

from feedback_selection_v1 import ABSTAIN, reconcile_choices
from selection_unseen_pipeline import candidate_boundary_failure


class SelectionGuards(unittest.TestCase):
    def test_symmetric_order_and_abstention(self):
        for choices, expected in [(['旧','旧'],'拒绝'), (['新','新'],'接受'),
                                  (['旧','新'],'未决'), (['新','旧'],'未决'),
                                  ([ABSTAIN],'未决'), (['旧'],'未决'), (['其他'],'未决')]:
            self.assertEqual(reconcile_choices(choices,'旧','新')[0], expected)

    def test_whole_field_for_subspan(self):
        row = {'answer':'第一句，错误推断。','regions':[{'start':0,'end':9}]}
        item = {'回答原文':'错误推断。'}
        self.assertEqual(candidate_boundary_failure(row,item,row['answer']),
                         'whole_existing_field_copied_into_subspan')
        self.assertIsNone(candidate_boundary_failure(row,item,'应改为有据限定。'))
        self.assertIsNone(candidate_boundary_failure(row,{'回答原文':row['answer']},'完整修订。'))


if __name__ == '__main__':
    unittest.main()
