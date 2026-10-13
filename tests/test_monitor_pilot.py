import copy
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "experiments/faithbench_monitor_v0"
sys.path.insert(0, str(BASE / "pilot_v1"))
sys.path.insert(0, str(BASE))
from monitor_protocol import CHECKS, make_packet
from pilot_protocol import enrich_packet, parse_pilot_response, runtime_snapshot


TOOLS = {"cards": {
    "tool_alpha": {"evidence_type": "非方向偏离", "limitations": "不返回真假概率"},
    "tool_beta": {"evidence_type": "局部纹理", "limitations": "可能误报"}},
    "rules": "最多4次，成功工具不能重复调用。"}


def step(number, tool="tool_alpha", status="success"):
    return {"step": number, "actor_output": {"next_action": "CALL_TOOL", "selected_tool": tool},
            "tool_observation": {"signal": "inconclusive"}, "call_status": status,
            "attempts": [{"raw": "格式失败"}, {"raw": "接受调用"}]}


def terminal(history=()):
    stop = {"next_action": "STOP", "selected_tool": None, "final_verdict": "fake"}
    row = {"steps": list(history) + [{"step": len(history)+1, "actor_output": stop,
                                    "attempts": [{"raw": json.dumps(stop)}]}],
           "raw_final_output": stop, "raw_parse_valid": True}
    return enrich_packet(make_packet(row, TOOLS, "terminal", "fixture"))


def call(history=(), tool="tool_alpha"):
    used = min(len(history), 4)
    row = {"step": len(history)+1, "raw_attempt": 0,
           "actor_request": {"next_action": "CALL_TOOL", "selected_tool": tool},
           "current_raw": "请求工具", "previous_raw_retries": [], "selected_tool": tool,
           "budget": {"max": 4, "used_before": used, "remaining_before": 4-used},
           "exposed_tools": list(TOOLS["cards"]), "history": list(history),
           "call_outcome": "CANARY_FUTURE", "gt": "CANARY_GT"}
    return enrich_packet(make_packet(row, TOOLS, "call_prefix", "fixture"))


def response(packet, action="ALLOW_ACTION", failure=None):
    checks = {k: "pass" for k in CHECKS}
    if packet["review_mode"] == "terminal":
        checks["call_justified"] = "not_applicable"
    else:
        for k in ("stop_justified", "verdict_supported", "premature_stop", "verdict_inconsistency"):
            checks[k] = "not_applicable"
    refs = [{"pointer": "/rules", "quote": "最多4次"}]
    findings = []
    if failure:
        checks[failure] = "fail"
        findings = [{"failure_type": failure, "assessment": "violated",
                     "explanation": "具体问题待修正。", "evidence_refs": refs}]
    return {"review": {"case_id": packet["case_id"], "decision": "FAIL" if failure else "PASS",
                       "checks": checks, "findings": findings, "uncertainties": []},
            "proposal": {"action": action, "reason": "依据当前记录。", "feedback": "请修正当前字段。",
                         "evidence_refs": copy.deepcopy(refs), "gap": None}}


def parse(value, packet):
    return parse_pilot_response(json.dumps(value, ensure_ascii=False), packet)


class MonitorPilotTests(unittest.TestCase):
    def test_blocked_call_charged_but_format_retries_not_charged(self):
        blocked = step(1, status="blocked_first_probe_contract_error")
        blocked["tool_observation"] = {"contract_error": "首步禁止"}
        state = terminal([blocked])["runtime_snapshot"]
        self.assertEqual(state["budget"]["used_before"], 1)
        self.assertEqual(state["evidence_ledger"], [])
        self.assertIn("tool_alpha", state["available_tools"])

    def test_full_missing_status_uses_actual_observation_and_retains_alias(self):
        old = step(1)
        del old["call_status"]
        state = terminal([old])["runtime_snapshot"]
        self.assertEqual(state["successful_tools"], ["tool_alpha"])
        self.assertEqual(state["available_tools"], ["tool_beta"])
        self.assertEqual(state["evidence_ledger"][0]["observation_ref"], "/trajectory/steps/0/tool_observation")

    def test_same_step_return_cannot_support_decision(self):
        packet = terminal()
        packet["trajectory"]["steps"][-1]["tool_observation"] = {"signal": "CANARY_CURRENT"}
        self.assertEqual(runtime_snapshot(packet)["evidence_ledger"], [])

    def test_call_projection_and_future_outcome_are_not_visible(self):
        self.assertNotIn("CANARY", json.dumps(call()))

    def test_recorded_call_budget_disagreement_rejected(self):
        packet = call()
        packet["budget"]["used_before"] = 1
        with self.assertRaisesRegex(ValueError, "budget differs"):
            runtime_snapshot(packet)

    def test_delay_first_constraint_expires_after_blocked_attempt(self):
        global_tool = "global_forensic_analyzer"
        packet = call()
        packet["exposed_tools"].append(global_tool)
        packet["rules"] += "仅第一个accepted CALL请求global时被阻止一次。"
        self.assertNotIn(global_tool, runtime_snapshot(packet)["available_tools"])
        packet["trajectory"]["steps"] = [step(1, global_tool, "blocked_first_probe_contract_error")]
        packet["current_action"]["step"] = 2
        packet["budget"] = {"max": 4, "used_before": 1, "remaining_before": 3}
        self.assertIn(global_tool, runtime_snapshot(packet)["available_tools"])

    def test_unsupported_audit_cannot_allow_stop_even_with_pass_judgments(self):
        packet = terminal()
        value = response(packet, failure="attribution_error")
        with self.assertRaisesRegex(ValueError, "unsupported or invalid"):
            parse(value, packet)
        packet["trajectory"]["raw_parse_valid"] = False
        with self.assertRaises(ValueError):
            parse(response(packet), packet)

    def test_exhaustion_allows_repair_or_limited_end_without_changing_fail(self):
        history = [step(i, status="blocked_first_probe_contract_error") for i in range(1, 5)]
        packet = terminal(history)
        for action in ("REVISE_REASONING", "END_LIMITED"):
            result = parse(response(packet, action, "attribution_error"), packet)
            self.assertEqual(result["review"]["decision"], "FAIL")
            self.assertFalse(result["executed"])
        value = response(packet, "REQUEST_EVIDENCE", "premature_stop")
        with self.assertRaisesRegex(ValueError, "actionable premature STOP"):
            parse(value, packet)

    def test_evidence_request_needs_available_tool_and_capability_quote(self):
        packet = terminal([step(1)])
        value = response(packet, "REQUEST_EVIDENCE", "premature_stop")
        value["proposal"]["gap"] = {"description": "缺少局部证据。", "evidence_type": "局部纹理",
                                    "candidate_tools": ["tool_beta"]}
        with self.assertRaisesRegex(ValueError, "capability reference"):
            parse(value, packet)
        value["proposal"]["evidence_refs"].append({"pointer": "/tool_cards/tool_beta/evidence_type", "quote": "局部纹理"})
        self.assertFalse(parse(value, packet)["executed"])
        value["proposal"]["gap"]["candidate_tools"] = ["tool_alpha"]
        with self.assertRaisesRegex(ValueError, "available candidate"):
            parse(value, packet)

    def test_allow_call_rejects_exhaustion_and_repeated_success(self):
        for packet in (call([step(1)]), call([step(i, status="blocked_first_probe_contract_error") for i in range(1, 5)])):
            with self.assertRaisesRegex(ValueError, "unavailable CALL"):
                parse(response(packet), packet)
        self.assertFalse(parse(response(call()), call())["executed"])

    def test_derived_summary_cannot_be_cited_as_original_evidence(self):
        packet = terminal()
        value = response(packet)
        value["proposal"]["evidence_refs"] = [{"pointer": "/runtime_snapshot/budget/remaining_before", "quote": "4"}]
        with self.assertRaisesRegex(ValueError, "outside visible"):
            parse(value, packet)

    def test_unassessable_does_not_become_allow_stop(self):
        packet = terminal()
        value = response(packet, "UNASSESSABLE")
        value["review"]["checks"]["evidence_insufficiency"] = "unassessable"
        value["review"].update(decision="UNASSESSABLE", uncertainties=["缺少像素核验。"])
        self.assertEqual(parse(value, packet)["proposal"]["action"], "UNASSESSABLE")
        value["proposal"]["action"] = "ALLOW_ACTION"
        with self.assertRaises(ValueError):
            parse(value, packet)


if __name__ == "__main__":
    unittest.main()
