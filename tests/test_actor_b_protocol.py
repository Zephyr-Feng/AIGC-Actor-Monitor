import sys
import unittest
from pathlib import Path


ACTOR_B = Path(__file__).resolve().parents[1] / "experiments" / "actor_b"
sys.path.insert(0, str(ACTOR_B))

from actor_b_protocol import parse_action  # noqa: E402


def base(action="CALL_TOOL", tool="global_forensic_analyzer", verdict=None, confidence=None):
    return {
        "current_evidence": [],
        "unresolved_conflicts": [],
        "evidence_gap": "缺少工具证据",
        "next_action": action,
        "selected_tool": tool,
        "action_reason": "获取独立证据",
        "final_verdict": verdict,
        "final_confidence": confidence,
    }


class ActorBProtocolTests(unittest.TestCase):
    def test_call_contract(self):
        self.assertEqual(parse_action(__import__("json").dumps(base()))["next_action"], "CALL_TOOL")

    def test_stop_contract(self):
        value = base("STOP", None, "fake", "moderate")
        self.assertEqual(parse_action(__import__("json").dumps(value))["final_verdict"], "fake")

    def test_reject_repeat(self):
        with self.assertRaisesRegex(ValueError, "already been called"):
            parse_action(__import__("json").dumps(base()), {"global_forensic_analyzer"})

    def test_reject_uncertain_stop(self):
        with self.assertRaisesRegex(ValueError, "real or fake"):
            parse_action(__import__("json").dumps(base("STOP", None, "uncertain", "low")))

    def test_evidence_shape(self):
        value = base()
        value["current_evidence"] = [{
            "source": "global_forensic_analyzer",
            "observation": "偏离百分位较高",
            "interpretation": "非方向观察",
            "direction": "none",
        }]
        self.assertEqual(len(parse_action(__import__("json").dumps(value))["current_evidence"]), 1)


if __name__ == "__main__":
    unittest.main()

