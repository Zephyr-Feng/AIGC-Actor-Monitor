import copy
import json
import unittest
from experiments.faithbench_monitor_v0.pilot_v2.protocol import applicable_checks, evidence_catalog, parse_response, render_request
from tests.test_monitor_pilot import call, terminal, step


def response(packet, action="ALLOW_ACTION"):
    catalog = evidence_catalog(packet)
    eid = next(eid for eid, ref in catalog.items() if ref["pointer"] == "/rules")
    return {"checks": {key: "pass" for key in applicable_checks(packet)}, "findings": [], "uncertainties": [],
            "proposal": {"action": action, "reason": "依据当前证据。", "feedback": None,
                         "reference_ids": [eid], "gap": None}}


class MonitorPilotV2Tests(unittest.TestCase):
    def test_original_leaves_preserved_and_derived_ledger_not_citable(self):
        packet = terminal([step(1)])
        before = copy.deepcopy(packet)
        catalog = evidence_catalog(packet)
        self.assertFalse(any(ref["pointer"].startswith("/runtime_snapshot") for ref in catalog.values()))
        self.assertTrue(any(ref["quote"] == "格式失败" for ref in catalog.values()))
        self.assertIn("格式失败", render_request(packet))
        self.assertEqual(before, packet)

    def test_code_fixes_scope_and_decision_without_faking_findings(self):
        packet = call()
        value = response(packet)
        result = parse_response(json.dumps(value, ensure_ascii=False), packet)
        self.assertEqual(result["review"]["checks"]["stop_justified"], "not_applicable")
        self.assertEqual(result["review"]["decision"], "PASS")
        value["checks"]["stop_justified"] = "pass"
        with self.assertRaisesRegex(ValueError, "applicable"):
            parse_response(json.dumps(value), packet)

    def test_unknown_evidence_id_is_rejected_not_repaired(self):
        packet = terminal()
        value = response(packet)
        value["proposal"]["reference_ids"] = ["E9999"]
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            parse_response(json.dumps(value), packet)

    def test_budget_and_mode_block_impossible_proposals(self):
        packets = [call(), terminal([step(i, status="blocked_first_probe_contract_error") for i in range(1, 5)])]
        for packet in packets:
            value = response(packet, "REQUEST_EVIDENCE")
            with self.assertRaisesRegex(ValueError, "forbidden"):
                parse_response(json.dumps(value), packet)

    def test_semantic_fail_without_cited_finding_still_rejected(self):
        packet = terminal()
        value = response(packet, "REVISE_REASONING")
        value["checks"]["attribution_error"] = "fail"
        with self.assertRaisesRegex(ValueError, "lacks cited"):
            parse_response(json.dumps(value), packet)

    def test_existing_valid_quote_does_not_make_unsupported_stop_legal(self):
        packet = terminal()
        value = response(packet)
        value["checks"]["evidence_insufficiency"] = "unassessable"
        value["uncertainties"] = ["缺少视觉核验。"]
        with self.assertRaisesRegex(ValueError, "unsupported or invalid"):
            parse_response(json.dumps(value, ensure_ascii=False), packet)


if __name__ == "__main__":
    unittest.main()
