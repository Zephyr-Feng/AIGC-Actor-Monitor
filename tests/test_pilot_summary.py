from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from summarize_pilot import summarize


class PilotSummaryTests(unittest.TestCase):
    def test_tool_contrast_and_arm_selection_room(self) -> None:
        labels = {"s1": "real", "s2": "fake", "s3": "real"}
        manifest = [
            {"sample_id": sid, "label": label, "image_sha256": sid}
            for sid, label in labels.items()
        ]
        prefixes = [
            {"sample_id": sid, "image_sha256": sid, "prefix_sha256": f"prefix-{sid}"}
            for sid in labels
        ]
        predictions = {
            "s1": {"A0": "fake", "A1": "real", "A2": "fake"},
            "s2": {"A0": "fake", "A1": "real", "A2": "fake"},
            "s3": {"A0": "fake", "A1": "fake", "A2": "real"},
        }
        branches = [
            {"sample_id": sid, "arm": arm, "image_sha256": sid,
             "prefix_sha256": f"prefix-{sid}", "final": {"parsed": {"label": label}}}
            for sid, by_arm in predictions.items() for arm, label in by_arm.items()
        ]
        vision = [
            {"sample_id": sid, "image_sha256": sid,
             "final": {"parsed": {"label": label}}}
            for sid, label in {"s1": "real", "s2": "real", "s3": "fake"}.items()
        ]
        report = summarize(manifest, prefixes, branches, vision)
        self.assertEqual(report["tool_correction_sample_ids"], ["s2"])
        self.assertEqual(report["tool_damage_sample_ids"], ["s1"])
        self.assertEqual(report["correction_sample_ids"], {"A1": ["s1"], "A2": ["s3"]})
        self.assertEqual(report["damage_sample_ids"], {"A1": ["s2"], "A2": []})
        self.assertEqual(report["oracle_selection_room"], 1)


if __name__ == "__main__":
    unittest.main()
