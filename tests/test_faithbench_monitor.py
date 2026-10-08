import copy
import json
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "experiments/faithbench_monitor_v0"
sys.path.insert(0, str(BASE))
from monitor_protocol import CHECKS, make_packet, parse_review, render_request


def call_row():
    return {"step": 2, "raw_attempt": 0, "actor_request": {"next_action": "CALL_TOOL"},
            "current_raw": "调用", "previous_raw_retries": [], "selected_tool": "tool_alpha",
            "budget": {"remaining_before": 0}, "exposed_tools": ["tool_alpha"],
            "history": [{"step": 1, "actor_output": {}, "tool_observation": {"signal": "inconclusive"},
                         "attempts": [{"raw": "原始步骤", "seconds": 10}]}],
            "call_outcome": "success", "gt": "fake", "agent_label": "inappropriate"}


TOOLS = {"cards": {"tool_alpha": {"limitations": "不返回真假概率"}}, "rules": "最多4次"}


def response(packet):
    checks = {k: "pass" for k in CHECKS}
    for key in ("stop_justified", "verdict_supported", "premature_stop", "verdict_inconsistency"):
        checks[key] = "not_applicable"
    return {"case_id": packet["case_id"], "decision": "PASS", "checks": checks,
            "findings": [], "uncertainties": []}


class MonitorPreparationTests(unittest.TestCase):
    def setUp(self):
        self.packet = make_packet(call_row(), TOOLS, "call_prefix", "fixture")

    def test_current_outcome_and_external_labels_cannot_change_input(self):
        row = call_row()
        row.update(call_outcome="CANARY_FUTURE_RESULT", gt="CANARY_GT", agent_label="CANARY_REVIEW",
                   effective_final_output={"verdict": "CANARY_PROJECTION"})
        self.assertEqual(self.packet, make_packet(row, TOOLS, "call_prefix", "fixture"))
        request = render_request(self.packet)
        self.assertNotIn("CANARY", request)
        self.assertIn("文字原型", request)

    def test_future_history_is_rejected(self):
        row = call_row()
        row["history"][0]["step"] = row["step"]
        with self.assertRaisesRegex(ValueError, "future"):
            make_packet(row, TOOLS, "call_prefix", "fixture")

    def test_invalid_raw_stop_preserved_without_projection(self):
        row = {"steps": [{"step": 1, "actor_output": None, "attempts": [{"raw": '{"final_verdict":null}'}]}],
               "raw_final_output": None, "raw_parse_valid": False,
               "effective_final_output": {"final_verdict": "fake"}}
        packet = make_packet(row, TOOLS, "terminal", "fixture")
        self.assertFalse(packet["trajectory"]["raw_parse_valid"])
        self.assertEqual(packet["trajectory"]["raw_terminal_text"], '{"final_verdict":null}')
        self.assertNotIn("effective_final_output", json.dumps(packet))

    def test_aliases_not_restored_to_canonical_names(self):
        self.assertIn("tool_alpha", self.packet["tool_cards"])
        self.assertEqual(self.packet["current_action"]["selected_tool"], "tool_alpha")

    def test_valid_cited_failure_and_fabricated_quote_rejection(self):
        review = response(self.packet)
        review["checks"]["unnecessary_continuation"] = "fail"
        review["checks"]["call_justified"] = "fail"
        review["decision"] = "FAIL"
        review["findings"] = [{"failure_type": "unnecessary_continuation", "assessment": "violated",
                               "explanation": "预算已耗尽仍请求工具。", "evidence_refs": [
                                   {"pointer": "/budget/remaining_before", "quote": "0"}]}]
        self.assertEqual(parse_review(json.dumps(review), self.packet)["decision"], "FAIL")
        review["findings"][0]["evidence_refs"][0]["quote"] = "4"
        with self.assertRaisesRegex(ValueError, "not in source"):
            parse_review(json.dumps(review), self.packet)

    def test_missing_and_annotation_references_rejected(self):
        review = response(self.packet)
        review["checks"]["attribution_error"] = "unassessable"
        review["decision"] = "UNASSESSABLE"
        review["uncertainties"] = ["缺少像素。"]
        finding = {"failure_type": "attribution_error", "assessment": "unassessable",
                   "explanation": "需要核验。", "evidence_refs": [{"pointer": "/annotations/label", "quote": "fake"}]}
        review["findings"] = [finding]
        for pointer in ("/annotations/label", "/trajectory/steps/2/tool_observation/signal"):
            finding["evidence_refs"][0]["pointer"] = pointer
            with self.assertRaises(ValueError):
                parse_review(json.dumps(review), self.packet)

    def test_call_cannot_pass_future_stop_and_uncertainty_cannot_be_pass(self):
        review = response(self.packet)
        review["checks"]["stop_justified"] = "pass"
        with self.assertRaisesRegex(ValueError, "future STOP"):
            parse_review(json.dumps(review), self.packet)
        review = response(self.packet)
        review["checks"]["evidence_insufficiency"] = "unassessable"
        with self.assertRaisesRegex(ValueError, "decision/check"):
            parse_review(json.dumps(review), self.packet)
        review.update(decision="UNASSESSABLE", uncertainties=["视觉自述缺少图像核验。"])
        self.assertEqual(parse_review(json.dumps(review), self.packet)["decision"], "UNASSESSABLE")

    def test_failure_requires_finding_and_chinese_explanation(self):
        review = response(self.packet)
        review["checks"]["unnecessary_continuation"] = "fail"
        review["decision"] = "FAIL"
        with self.assertRaisesRegex(ValueError, "lacks cited"):
            parse_review(json.dumps(review), self.packet)
        review["findings"] = [{"failure_type": "unnecessary_continuation", "assessment": "violated",
                               "explanation": "No budget", "evidence_refs": [
                                   {"pointer": "/budget/remaining_before", "quote": "0"}]}]
        with self.assertRaisesRegex(ValueError, "Chinese"):
            parse_review(json.dumps(review), self.packet)


if __name__ == "__main__":
    unittest.main()
