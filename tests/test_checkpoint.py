from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.checkpoint import (
    ACTION_PROMPTS,
    FINAL_PROMPT,
    PRELIMINARY_PROMPT,
    build_branch_messages,
    parse_final,
    parse_preliminary,
)


class CheckpointTests(unittest.TestCase):
    def test_chinese_judgments_are_parseable(self) -> None:
        preliminary = parse_preliminary(
            "初步判断：fake\n置信度：0.7\n"
            "证据摘要：高频纹理重复，频谱工具显示异常峰值\n"
            "不确定性：压缩也可能产生类似峰值"
        )
        final = parse_final(
            "结论：real\n解释：纹理与拍摄噪声一致\n"
            "不确定性：缺少原始文件\n置信度：0.6"
        )
        self.assertEqual(preliminary.label, "fake")
        self.assertEqual(preliminary.explanation, "高频纹理重复，频谱工具显示异常峰值")
        self.assertEqual(final.label, "real")
        self.assertEqual(final.uncertainty, "缺少原始文件")

    def test_all_arms_continue_the_same_prefix(self) -> None:
        prefix = [
            {"role": "system", "content": "用中文分析图像"},
            {"role": "assistant", "content": "初步判断：fake"},
        ]
        branches = {arm: build_branch_messages(prefix, arm) for arm in ACTION_PROMPTS}
        self.assertEqual(len(prefix), 2)
        for messages in branches.values():
            self.assertEqual(messages[:2], prefix)
            self.assertIsNot(messages[0], prefix[0])
            self.assertIn(FINAL_PROMPT, messages[-1]["content"][0]["text"])
        self.assertEqual(branches["A0"][-1]["content"][0]["text"], FINAL_PROMPT)
        self.assertIn("核验", branches["A1"][-1]["content"][0]["text"])
        self.assertIn("另一种解释", branches["A2"][-1]["content"][0]["text"])
        self.assertIn("证据摘要", PRELIMINARY_PROMPT)


if __name__ == "__main__":
    unittest.main()
