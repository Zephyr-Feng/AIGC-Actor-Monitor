from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.tool_text import format_formal_tool_results, format_tool_results


class ToolTextTests(unittest.TestCase):
    def test_text_uses_observed_value_without_label_or_calibration(self) -> None:
        text = format_tool_results(
            [{
                "tool": "freq_spectrum",
                "ok": True,
                "values": {"high_freq_energy_ratio": 0.123},
                "calibrated": {"direction": "fake"},
            }],
            {"high_freq_energy_ratio": [0.1, 0.2]},
        )
        self.assertIn("高频能量占比", text)
        self.assertIn("0.123000", text)
        self.assertIn("真图参考区间", text)
        self.assertNotIn("high_freq_energy_ratio", text)
        self.assertNotIn("direction", text)
        self.assertNotIn("fake", text)

    def test_formal_text_keeps_only_selected_families_and_limits_reference_claim(self) -> None:
        text = format_formal_tool_results(
            [
                {"tool": "freq_spectrum", "ok": True,
                 "values": {"high_freq_energy_ratio": 0.1}},
                {"tool": "compression_dct", "ok": True,
                 "values": {"dct_coeff_kurtosis": 75.0}},
            ],
            {"dct_coeff_kurtosis": [70.0, 100.0]},
        )
        self.assertIn("DCT 系数峰度", text)
        self.assertNotIn("高频能量占比", text)
        self.assertIn("落在区间内不能证明是真图", text)


if __name__ == "__main__":
    unittest.main()
