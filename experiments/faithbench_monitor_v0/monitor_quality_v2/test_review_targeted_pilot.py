import json
from pathlib import Path
import unittest
from review_targeted_pilot import inspect


class InterfaceReview(unittest.TestCase):
    def test_status_does_not_certify_reason(self):
        root=Path(__file__).resolve().parents[3]/'data/monitor_targeted_sft_v1_20261021'
        source=json.loads((root/'inputs.json').read_text(encoding='utf8'))[0]
        row=json.loads((root/'train.json').read_text(encoding='utf8'))[0]
        result=inspect(source,row,json.dumps(row['target'],ensure_ascii=False))
        self.assertTrue(result['status_agreement'])
        self.assertFalse(result['semantic_verified'])
        self.assertEqual(result['interface_status'],'retained')
        self.assertFalse(inspect(source,row,'{')['json_valid'])


if __name__=='__main__':unittest.main()
