import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments/actor_b/actor_b0_d"))
import evaluate_b0_d as evaluator


class ImmediateStopTests(unittest.TestCase):
    def setUp(self):
        self.probe = "global_forensic_analyzer"
        self.other = "local_texture_analyzer"
        self.row = {
            "tool_calls": [self.probe],
            "effective_final_output": {"next_action": "STOP"},
            "steps": [
                {"actor_output": {"next_action": "CALL_TOOL", "selected_tool": self.probe},
                 "call_status": "success"},
                {"actor_output": {"next_action": "STOP"}},
            ],
        }

    def test_probe_then_stop_counts(self):
        self.assertTrue(evaluator.probe_first_immediate_stop(self.row))

    def test_probe_then_other_tool_then_stop_does_not_count(self):
        row = copy.deepcopy(self.row)
        row["tool_calls"].append(self.other)
        row["steps"].insert(1, {
            "actor_output": {"next_action": "CALL_TOOL", "selected_tool": self.other},
            "call_status": "success",
        })
        self.assertFalse(evaluator.probe_first_immediate_stop(row))

    def test_rejected_post_probe_call_is_not_immediate_stop(self):
        row = copy.deepcopy(self.row)
        row["steps"].insert(1, {
            "actor_output": None,
            "attempts": [{"raw": json.dumps({
                "next_action": "CALL_TOOL", "selected_tool": self.other,
            })}],
            "call_status": "over_budget",
        })
        self.assertFalse(evaluator.probe_first_immediate_stop(row))

    def test_projected_stop_counts_when_no_later_call_requested(self):
        row = copy.deepcopy(self.row)
        row["steps"][-1]["actor_output"] = None
        row["steps"][-1]["attempts"] = [{"raw": json.dumps({
            "next_action": "STOP", "final_verdict": "uncertain",
        })}]
        self.assertTrue(evaluator.probe_first_immediate_stop(row))


if __name__ == "__main__":
    unittest.main()
