from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_t0_actor import initial_messages


class T0ActorPromptTests(unittest.TestCase):
    def test_tool_and_no_tool_conditions_identify_available_evidence(self) -> None:
        image = object()
        without = initial_messages(image, None)
        with_tools = initial_messages(image, "频谱一致性得分：0.99")
        self.assertIs(without[1]["content"][0]["image"], image)
        self.assertIs(with_tools[1]["content"][0]["image"], image)
        self.assertIn("没有提供任何取证工具结果", without[1]["content"][1]["text"])
        self.assertIn("频谱一致性得分：0.99", with_tools[1]["content"][1]["text"])
        self.assertNotIn("频谱一致性得分：0.99", without[1]["content"][1]["text"])


if __name__ == "__main__":
    unittest.main()
