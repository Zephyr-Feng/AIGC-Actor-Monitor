import json
import unittest
from feedback_interface_v3 import fact_ledger


class TaskStateLedger(unittest.TestCase):
    def test_task_state_kept_and_direction_not_invented(self):
        state={'used_tools':['global_forensic_analyzer'],'max_tool_calls':4,'remaining_calls':3}
        cards=[{'id':'T','path':['task_state'],'value':state},
               {'id':'G','path':['observed_tool_return'],'value':{'tool':'global_forensic_analyzer','scope':{'num_regions_examined':6}}}]
        result=fact_ledger(cards)
        self.assertEqual(result[0],{'来源ID':'T','上下文':state})
        self.assertNotIn('signal',result[1])
        self.assertEqual(cards[0]['value'],state)

    def test_paired_inputs_only_add_ledger(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[3]/'data/monitor_fact_view_v1_20261021'
        rows=json.loads((root/'paired_inputs.json').read_text(encoding='utf8'))
        for source in ('case_008','case_009','case_010'):
            pair={r['arm']:r['messages'] for r in rows if r['source_id']==source}
            self.assertEqual(pair['plain'][0],pair['ledger'][0])
            data=json.loads(pair['ledger'][1]['content'])
            del data['程序事实账本']
            self.assertEqual(data,json.loads(pair['plain'][1]['content']))


if __name__=='__main__':
    unittest.main()
