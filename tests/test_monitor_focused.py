import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from focused import focused_input,validate_focused,relation_flags,final_schema,parse_focused


class FocusedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets={p['case_id']:p for p in map(json.loads,(ROOT/'experiments/faithbench_monitor_v0/private/pilot_v2_locked/inputs.jsonl').read_text(encoding='utf8').splitlines())}

    def unknowns(self,data):
        return {'observations':{a['atom_id']:{'status':'unassessable','reason':'无法确定来源对应','reference_ids':[]} for a in data['observation_atoms']},
                'conflicts':{s['slot_id']:{'pairs':[],'reason':'关系未知','reference_ids':[]} for s in data['conflict_slots']}}

    def test_support_needs_same_source_prior_return(self):
        data=focused_input(self.packets['terminal_0005']);result=self.unknowns(data);atom=data['observation_atoms'][0]
        result['observations'][atom['atom_id']]={'status':'supported_by_source','reason':'候选能力不能代替实际返回','reference_ids':atom['source_card_ids'][:1]}
        with self.assertRaisesRegex(ValueError,'same-source'):validate_focused(json.dumps(result),data)

    def test_accusation_needs_actor_and_prior_source(self):
        data=focused_input(self.packets['terminal_0001']);result=self.unknowns(data);a=data['observation_atoms'][0]
        result['observations'][a['atom_id']]={'status':'not_returned_by_source','reason':'不能只凭Actor句子判源缺少','reference_ids':a['claim_reference_ids'][:1]}
        with self.assertRaisesRegex(ValueError,'actor and prior'):validate_focused(json.dumps(result),data)

    def test_visual_and_future_sources_excluded(self):
        data=focused_input(self.packets['call_0001'])
        self.assertEqual(data['observation_atoms'],[])
        self.assertEqual(data['conflict_slots'],[])
        self.assertEqual(data['visual_text_audit']['status'],'unassessable')
        for s in focused_input(self.packets['call_0385'])['conflict_slots']:
            self.assertTrue(all(r['returned_after_step']<s['decision_step'] for r in s['prior_source_roles'].values()))

    def test_conflict_roles_do_not_erase_other_tension(self):
        data={'observation_atoms':[],'conflict_slots':[{'slot_id':'K001','prior_source_roles':{'x':{'role':{'kind':'non_directional','direction':None}},'y':{'role':{'kind':'directional','direction':'fake'}}}}]}
        result={'observations':{},'conflicts':{'K001':{'pairs':[{'left':'x','right':'y','type':'other_tension'}]}}}
        self.assertEqual(relation_flags(data,result),{})
        result['conflicts']['K001']['pairs'][0]['type']='direction_conflict'
        self.assertIn('K001_0',relation_flags(data,result))
        data['conflict_slots'][0]['prior_source_roles']['x']['role']={'kind':'directional','direction':'real'}
        self.assertEqual(relation_flags(data,result),{})

    def test_free_reason_cannot_supply_illegal_actor_feedback(self):
        p=self.packets['terminal_0002'];schema=final_schema(p,{})
        records={k:{'status':'pass','reason':'此项未见问题','reference_ids':['E0158']} for k in schema['properties']['check_records']['properties']}
        raw={'check_records':records,'relation_dispositions':{},'proposal':{'action':'REVISE_REASONING','reason':'建议改成inconclusive但这是待审机器理由','reference_ids':['E0158'],'gap':None}}
        simple,checked,_,_=parse_focused(json.dumps(raw,ensure_ascii=False),p,{})
        self.assertNotIn('inconclusive',simple['proposal']['feedback'])
        self.assertIn('final_verdict只用real或fake',simple['proposal']['feedback'])
        self.assertFalse(checked['executed'])


if __name__=='__main__':unittest.main()
