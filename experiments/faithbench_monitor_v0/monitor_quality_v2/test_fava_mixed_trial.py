import json
import unittest
from diagnose_fava_quotes import compact_score
from fava_mixed_trial import authorization


class MixedTrialTests(unittest.TestCase):
    def test_compact_contract_and_alignment(self):
        row = {'messages': [{}, {'content': json.dumps({'待核回答': 'cat cat'})}],
               'target': {'问题': []}, 'numeric_target': {'问题': []}, 'author_corrected_answer': 'cat cat'}
        self.assertTrue(compact_score('{"问题":[]}', row)['exact_author_corrected_answer'])
        self.assertEqual(compact_score('{"问题":[{"回答原文":"cat","建议":"dog"}]}', row)['failure'], 'ambiguous_quote')
        self.assertFalse(compact_score('{"问题":[{"起点":0,"终点":3,"回答原文":"cat","建议":"dog"}]}', row)['contract_valid'])
        self.assertEqual(compact_score('{"问题":[{"回答原文":"","建议":"dog"}]}', row)['failure'], 'insertion_location_not_inferred')

    def test_budget(self):
        auth = dict(approved=True, purpose='mixed_compact_noerror_chinese_replay', epochs=1, max_updates=500,
                    max_gpu_seconds=28800, max_generations=334, start_epoch=100, deadline_epoch=28900,
                    training_cutoff_epoch=25300)
        authorization(auth, 101)
        for change in ({'epochs': 2}, {'max_updates': 501}, {'max_gpu_seconds': 28801}, {'approved': False}):
            with self.assertRaises(AssertionError):
                authorization({**auth, **change}, 101)


if __name__ == '__main__':
    unittest.main()
