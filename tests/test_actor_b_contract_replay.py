import json
import sys
import unittest
from pathlib import Path


ACTOR_B = Path(__file__).resolve().parents[1] / "experiments" / "actor_b"
sys.path.insert(0, str(ACTOR_B))

from actor_b_protocol import parse_action  # noqa: E402
from contract_replay import common_token_prefix, reconstruct_stop_context, replace_verdict, verdict_span  # noqa: E402


def action(next_action, tool, verdict):
    return {"current_evidence": [], "unresolved_conflicts": [], "evidence_gap": "不足",
            "next_action": next_action, "selected_tool": tool, "action_reason": "继续取证",
            "final_verdict": verdict, "final_confidence": "low" if verdict else None}


class ContractReplayTests(unittest.TestCase):
    def test_replacement_changes_only_verdict(self):
        raw = json.dumps(action("STOP", None, "inconclusive"), ensure_ascii=False)
        amended = replace_verdict(raw, "real")
        before, after = json.loads(raw), parse_action(amended)
        self.assertEqual(after["final_verdict"], "real")
        self.assertEqual({k: v for k, v in before.items() if k != "final_verdict"},
                         {k: v for k, v in after.items() if k != "final_verdict"})

    def test_reconstructs_retry_and_tool_history_without_rewriting_reasoning(self):
        invalid = json.dumps(action("STOP", None, None), ensure_ascii=False)
        call = action("CALL_TOOL", "global_forensic_analyzer", None)
        observation = {"tool": "global_forensic_analyzer", "most_atypical_regions": [
            {"region_id": "R1", "crop_path": "r1.png"}]}
        final = json.dumps(action("STOP", None, "inconclusive"), ensure_ascii=False)
        row = {"tool_calls": ["global_forensic_analyzer"], "steps": [
            {"attempts": [{"raw": invalid}, {"raw": json.dumps(call, ensure_ascii=False)}],
             "actor_output": call, "tool_observation": observation},
            {"attempts": [{"raw": final}], "actor_output": None, "tool_observation": None}]}
        messages, raw = reconstruct_stop_context(row, "image", "prompt", {}, {},
                                                 lambda path: "crop:" + path, 4)
        self.assertEqual(raw, final)
        self.assertEqual([m["role"] for m in messages],
                         ["system", "user", "assistant", "user", "assistant", "user"])
        self.assertIn("结构校验失败", messages[3]["content"])
        self.assertEqual(messages[-1]["content"][2]["image"], "crop:r1.png")

    def test_refuses_non_stop_or_ambiguous_field(self):
        with self.assertRaisesRegex(ValueError, "STOP"):
            verdict_span(json.dumps(action("CALL_TOOL", "global_forensic_analyzer", None)))
        with self.assertRaisesRegex(ValueError, "constrained verdict"):
            replace_verdict(json.dumps(action("STOP", None, "inconclusive")), "inconclusive")

    def test_candidate_scoring_uses_last_common_token_boundary(self):
        self.assertEqual(common_token_prefix([1, 2, 3, 4], [1, 2, 5, 6]), 2)


if __name__ == "__main__":
    unittest.main()
