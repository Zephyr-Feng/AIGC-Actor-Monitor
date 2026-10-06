from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import ARMS, read_jsonl, validate_p0
from actor_monitor.schema import Outcome


def synthetic_ledgers(n: int = 10) -> tuple[list[dict], list[dict], list[dict]]:
    manifest, prefixes, outcomes = [], [], []
    for index in range(n):
        episode_id = f"synthetic-{index}|seed0"
        prefix_hash = f"synthetic-prefix-{index}"
        manifest.append({
            "sample_id": f"synthetic-{index}",
            "source_group_id": f"synthetic-source-{index}",
            "label": "real" if index % 2 == 0 else "fake",
            "image_sha256": f"synthetic-image-{index}",
            "split": "P0",
        })
        prefixes.append({
            "episode_id": episode_id,
            "sample_id": f"synthetic-{index}",
            "source_group_id": f"synthetic-source-{index}",
            "checkpoint_id": "G_late",
            "reached": True,
            "prefix_hash": prefix_hash,
            "image_sha256": f"synthetic-image-{index}",
            "messages_sha256": f"synthetic-messages-{index}",
            "tool_outputs_sha256": f"synthetic-tools-{index}",
            "actor_hash": "synthetic-actor",
            "prompt_hash": "synthetic-prompt",
            "tool_hash": "synthetic-tool-version",
            "channel_hash": "synthetic-channel",
            "decoding_seed": 0,
        })
        for arm in sorted(ARMS):
            outcomes.append({
                "episode_id": episode_id,
                "arm": arm,
                "prefix_hash": prefix_hash,
                "image_sha256": f"synthetic-image-{index}",
                "messages_sha256": f"synthetic-messages-{index}",
                "tool_outputs_sha256": f"synthetic-tools-{index}",
                "actor_hash": "synthetic-actor",
                "prompt_hash": "synthetic-prompt",
                "tool_hash": "synthetic-tool-version",
                "channel_hash": "synthetic-channel",
                "decoding_seed": 0,
                "arm_version": "synthetic-v0",
                "answer": manifest[-1]["label"],
                "correct": True,
                "abstained": False,
                "compute_cost": 0.0,
            })
    return manifest, prefixes, outcomes


class P0ContractTests(unittest.TestCase):
    def test_ten_episode_synthetic_smoke(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers()
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.jsonl"
            prefix_path = Path(directory) / "prefixes.jsonl"
            outcome_path = Path(directory) / "outcomes.jsonl"
            manifest_path.write_text("".join(json.dumps(row) + "\n" for row in manifest), encoding="utf-8")
            prefix_path.write_text("".join(json.dumps(row) + "\n" for row in prefixes), encoding="utf-8")
            outcome_path.write_text("".join(json.dumps(row) + "\n" for row in outcomes), encoding="utf-8")
            report = validate_p0(read_jsonl(manifest_path), read_jsonl(prefix_path), read_jsonl(outcome_path))
        self.assertEqual(report["n_initial_episodes"], 10)
        self.assertEqual(report["n_outcomes"], 30)
        self.assertEqual(report["status"], "structurally_valid")

    def test_missing_arm_is_rejected(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(1)
        outcomes = [row for row in outcomes if row["arm"] != "A2"]
        with self.assertRaisesRegex(ValueError, "incomplete arm set"):
            validate_p0(manifest, prefixes, outcomes)

    def test_mismatched_prefix_is_rejected(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(1)
        outcomes[0]["prefix_hash"] = "other"
        with self.assertRaisesRegex(ValueError, "prefix hash mismatch"):
            validate_p0(manifest, prefixes, outcomes)

    def test_branch_received_different_messages_is_rejected(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(1)
        outcomes[0]["messages_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "pre-branch messages_sha256 mismatch"):
            validate_p0(manifest, prefixes, outcomes)

    def test_label_in_prefix_is_rejected(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(1)
        prefixes[0]["label"] = "fake"
        with self.assertRaisesRegex(ValueError, "future or label keys"):
            validate_p0(manifest, prefixes, outcomes)

    def test_tool_predicted_label_is_not_ground_truth(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(1)
        prefixes[0]["tool_outputs"] = [{"predicted_label": "fake", "label": "fake"}]
        self.assertEqual(validate_p0(manifest, prefixes, outcomes)["n_reached"], 1)

    def test_wrong_correctness_is_rejected(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(1)
        outcomes[0]["correct"] = False
        with self.assertRaisesRegex(ValueError, "disagrees with manifest label"):
            validate_p0(manifest, prefixes, outcomes)

    def test_source_group_cannot_cross_splits(self) -> None:
        manifest, prefixes, outcomes = synthetic_ledgers(2)
        manifest[1]["source_group_id"] = manifest[0]["source_group_id"]
        manifest[1]["split"] = "T-ID"
        with self.assertRaisesRegex(ValueError, "crosses splits"):
            validate_p0(manifest, prefixes, outcomes)

    def test_unreached_checkpoint_requires_reason(self) -> None:
        manifest, prefixes, _ = synthetic_ledgers(1)
        prefixes[0]["reached"] = False
        with self.assertRaisesRegex(ValueError, "needs a reason"):
            validate_p0(manifest, prefixes, [])
        prefixes[0]["reason"] = "early_final_answer"
        report = validate_p0(manifest, prefixes, [])
        self.assertEqual(report["n_unreached"], 1)

    def test_string_false_and_negative_cost_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON booleans"):
            Outcome.from_dict({"episode_id": "e", "arm": "A0", "correct": "false"})
        with self.assertRaisesRegex(ValueError, "non-negative"):
            Outcome.from_dict({"episode_id": "e", "arm": "A0", "correct": True, "compute_cost": -1})


if __name__ == "__main__":
    unittest.main()
