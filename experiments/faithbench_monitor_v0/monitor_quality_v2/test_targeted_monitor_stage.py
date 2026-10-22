import json
import unittest
from copy import deepcopy
from pathlib import Path

from targeted_monitor_stage import TRAIN_IDS, DEV_IDS, authorize, controls, example


class TargetedPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[3]/'data/monitor_targeted_sft_v1_20261021'
        cls.rows=json.loads((cls.root/'inputs.json').read_text(encoding='utf8'))

    def test_controls_balanced_and_source_bound(self):
        for row in self.rows:
            specs=controls(row)
            self.assertEqual([s[1] for s in specs].count('pass'),4)
            self.assertEqual([s[1] for s in specs].count('revise'),4)
            self.assertEqual([s[1] for s in specs].count('uncertain'),4)
            for spec in specs:
                ex=example(row,spec)
                self.assertEqual(ex['messages'][0]['content'],row['monitor_system'])
                self.assertEqual(json.loads(ex['messages'][1]['content'])['证据卡'],row['cards'])
                self.assertFalse(ex['human_gold'])

    def test_group_separation_and_single_pass(self):
        train=json.loads((self.root/'train.json').read_text(encoding='utf8'))
        dev=json.loads((self.root/'development.json').read_text(encoding='utf8'))
        self.assertEqual({r['group'] for r in train},set(TRAIN_IDS))
        self.assertEqual({r['group'] for r in dev},set(DEV_IDS))
        self.assertFalse(set(TRAIN_IDS)&set(DEV_IDS))
        self.assertEqual(len(train),len({r['id'] for r in train}))
        self.assertEqual((len(train)+7)//8,12)

    def test_authorization_rejects_other_scope(self):
        auth=json.loads((self.root/'training_authorization.json').read_text(encoding='utf8'))
        self.assertTrue(auth['initial_adapter'].startswith('/root/'))
        self.assertNotIn(chr(92), auth['initial_adapter'])
        authorize(auth)
        for key,value in [('approved',False),('max_gpu_seconds',28800),('epochs',2),('actor_training_updates',1)]:
            invalid=deepcopy(auth);invalid[key]=value
            with self.assertRaises(AssertionError):authorize(invalid)


if __name__=='__main__':unittest.main()
