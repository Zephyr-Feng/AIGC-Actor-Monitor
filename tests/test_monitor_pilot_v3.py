import copy
import json
import unittest
import sys
from pathlib import Path
from experiments.faithbench_monitor_v0.pilot_v3.protocol import response_schema, source_alignment

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/faithbench_monitor_v0/pilot_v3'))
from claim_verify import verification_input, validate_verification
from atomic_check import atomic_input, typed_schema, parse_typed
from role_gate import direction_gate
from hybrid import contract_records, hybrid_schema


class MonitorBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets = {p['case_id']: p for p in map(json.loads, (ROOT / 'experiments/faithbench_monitor_v0/private/pilot_v2_locked/inputs.jsonl').read_text(encoding='utf8').splitlines())}

    def test_exhausted_call_cannot_be_allowed(self):
        schema = response_schema(self.packets['call_0385'])
        self.assertNotIn('ALLOW_ACTION', schema['properties']['proposal']['properties']['action']['enum'])
        self.assertNotIn('premature_stop', schema['properties']['checks']['properties'])

    def test_exhausted_stop_is_not_premature_but_support_is_open(self):
        checks = response_schema(self.packets['terminal_0041'])['properties']['checks']['properties']
        self.assertEqual(checks['premature_stop']['enum'], ['pass'])
        self.assertIn('unassessable', checks['verdict_supported']['enum'])

    def test_invalid_stop_cannot_be_allowed(self):
        actions = response_schema(self.packets['terminal_0005'])['properties']['proposal']['properties']['action']['enum']
        self.assertNotIn('ALLOW_ACTION', actions)

    def test_source_links_do_not_use_later_returns(self):
        for packet in self.packets.values():
            for binding in source_alignment(packet):
                for prior in binding['prior_returns']:
                    self.assertLess(prior['returned_after_step'], binding['decision_step'])
        for cid in ['call_0001', 'call_0190']:
            self.assertTrue(all(not b['prior_returns'] for b in source_alignment(self.packets[cid])))

    def test_alignment_leaves_inputs_and_raw_retry_status_intact(self):
        packet = copy.deepcopy(self.packets['terminal_0005'])
        before = copy.deepcopy(packet)
        result = source_alignment(packet)
        self.assertEqual(packet, before)
        self.assertTrue(any(b['raw_retry_not_accepted'] for b in result))

    def test_verifier_claims_cover_raw_retry_without_future_return(self):
        data = verification_input(self.packets['terminal_0005'])
        self.assertEqual(len(data['claims']), len(source_alignment(self.packets['terminal_0005'])))
        self.assertTrue(any('门牌号' in c['actor_claim']['observation'] for c in data['claims']))
        for item in data['claims']:
            self.assertTrue(all(p['returned_after_step'] < item['decision_step'] for p in item['prior_returns']))

    def test_verifier_rejects_missing_claim_and_uncited_violation(self):
        packet = self.packets['call_0001']; data = verification_input(packet)
        raw = {'claims': {}, 'synthesis': {'status':'within_role','reference_ids':[],'reason':'未见综合越界'}}
        with self.assertRaisesRegex(ValueError, 'missing'):
            validate_verification(json.dumps(raw), data, packet)
        raw['claims']['C001'] = {'observation':'not_returned_by_source','direction':'within_role','reason':'无来源','reference_ids':[]}
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            validate_verification(json.dumps(raw), data, packet)

    def test_atomic_keeps_object_fragment_separate_and_visual_unknown(self):
        data = atomic_input(self.packets['terminal_0005'])
        self.assertTrue(any(a['text'] == '门牌号附近' for a in data['observation_atoms']))
        self.assertTrue(all(c['source'] != 'visual' for c in data['claims']))
        self.assertEqual(data['visual_text_audit']['status'], 'unassessable')
        for c in data['claims']:
            self.assertTrue(all(p['returned_after_step'] < c['decision_step'] for p in c['prior_returns']))

    def test_no_legal_verdict_is_not_evidence_failure_by_code(self):
        props=typed_schema(self.packets['terminal_0005'])['properties']['check_records']['properties']
        self.assertEqual(props['verdict_supported']['properties']['status']['enum'], ['unassessable'])
        self.assertEqual(props['verdict_inconsistency']['properties']['status']['enum'], ['unassessable'])

    def test_single_check_record_builds_consistent_budget_finding(self):
        packet=self.packets['call_0385']
        schema=typed_schema(packet)
        records={k:{'status':'pass','reason':'未见此项问题','reference_ids':['E0194']}
                 for k in schema['properties']['check_records']['properties']}
        records['unnecessary_continuation']={'status':'fail','reason':'预算耗尽仍请求调用','reference_ids':['E0194','E0186']}
        records['call_justified']={'status':'fail','reason':'当前调用不可执行','reference_ids':['E0194','E0186']}
        result={'check_records':records,'proposal':{'action':'BLOCK_CALL','reason':'预算已耗尽','feedback':'请停止继续调用','reference_ids':['E0194'],'gap':None}}
        simple,parsed=parse_typed(json.dumps(result,ensure_ascii=False),packet)
        self.assertEqual(len(simple['findings']),1)
        self.assertEqual(simple['checks']['unnecessary_continuation'],'fail')
        self.assertFalse(parsed['executed'])

    def test_explicit_role_direction_survives_hedging_and_rename(self):
        packet=copy.deepcopy(self.packets['terminal_0002'])
        renamed=json.loads(json.dumps(packet,ensure_ascii=False).replace('global_forensic_analyzer','neutral_tool_17'))
        gate=direction_gate(renamed)
        self.assertEqual(len(gate['violations']),1)
        self.assertEqual(gate['violations'][0]['source'],'neutral_tool_17')
        refs=gate['violations'][0]['reference_ids']
        from experiments.faithbench_monitor_v0.pilot_v2.protocol import evidence_catalog
        values=[evidence_catalog(renamed)[eid]['quote'] for eid in refs]
        self.assertIn('fake',values)
        self.assertIn('representation_deviation',values)

    def test_unknown_evidence_type_is_not_classified_by_tool_name(self):
        packet=copy.deepcopy(self.packets['terminal_0002'])
        for evidence in packet['runtime_snapshot']['evidence_ledger']:
            if evidence['source']=='global_forensic_analyzer':evidence['observation']['evidence_type']='unregistered_signal'
        self.assertFalse(direction_gate(packet)['violations'])
        self.assertFalse(direction_gate(self.packets['terminal_0061'])['violations'])

    def test_contract_fail_cannot_allow_and_action_gap_are_coupled(self):
        schema=hybrid_schema(self.packets['terminal_0002'])
        self.assertNotIn('attribution_error',schema['properties']['check_records']['required'])
        actions=[]
        for branch in schema['properties']['proposal']['anyOf']:
            action=branch['properties']['action']['enum'][0];actions.append(action)
            self.assertEqual(branch['properties']['gap']['type'],'object' if action=='REQUEST_EVIDENCE' else 'null')
        self.assertNotIn('ALLOW_ACTION',actions)


if __name__ == '__main__':
    unittest.main()
