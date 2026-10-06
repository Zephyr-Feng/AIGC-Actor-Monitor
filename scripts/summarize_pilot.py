"""Describe the tool A0 contrast and three-arm pilot selection room."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl  # noqa: E402


def summarize(manifest: list[dict], prefixes: list[dict], branches: list[dict], vision: list[dict]) -> dict:
    labels = {row["sample_id"]: row["label"] for row in manifest}
    prefix_by_id = {row["sample_id"]: row for row in prefixes}
    branch_by_key = {(row["sample_id"], row["arm"]): row for row in branches}
    vision_by_id = {row["sample_id"]: row for row in vision}
    if (len(labels) != len(manifest) or len(prefix_by_id) != len(prefixes)
            or len(branch_by_key) != len(branches) or len(vision_by_id) != len(vision)):
        raise ValueError("duplicate sample or branch")
    arms = ("A0", "A1", "A2")
    expected = {(sample_id, arm) for sample_id in labels for arm in arms}
    if (set(branch_by_key) != expected or set(prefix_by_id) != set(labels)
            or set(vision_by_id) != set(labels)):
        raise ValueError("incomplete or unexpected pilot records")
    for (sample_id, _), branch in branch_by_key.items():
        prefix = prefix_by_id[sample_id]
        if branch["prefix_sha256"] != prefix["prefix_sha256"]:
            raise ValueError(f"{sample_id}: branch prefix mismatch")
        if branch["image_sha256"] != prefix["image_sha256"]:
            raise ValueError(f"{sample_id}: branch image mismatch")
        if prefix["image_sha256"] != next(row["image_sha256"] for row in manifest if row["sample_id"] == sample_id):
            raise ValueError(f"{sample_id}: manifest image mismatch")
        if vision_by_id[sample_id]["image_sha256"] != prefix["image_sha256"]:
            raise ValueError(f"{sample_id}: vision image mismatch")

    invalid = [
        {"sample_id": sample_id, "arm": arm, "error": branch_by_key[(sample_id, arm)]["final"].get("parse_error")}
        for sample_id in labels for arm in arms
        if "parsed" not in branch_by_key[(sample_id, arm)]["final"]
    ]
    complete = [sample_id for sample_id in labels if all(
        "parsed" in branch_by_key[(sample_id, arm)]["final"] for arm in arms
    )]
    correct = {
        sample_id: {arm: branch_by_key[(sample_id, arm)]["final"]["parsed"]["label"] == labels[sample_id]
                    for arm in arms}
        for sample_id in complete
    }
    accuracy = {arm: sum(item[arm] for item in correct.values()) for arm in arms}
    correction = {arm: [sid for sid, item in correct.items() if not item["A0"] and item[arm]]
                  for arm in ("A1", "A2")}
    damage = {arm: [sid for sid, item in correct.items() if item["A0"] and not item[arm]]
              for arm in ("A1", "A2")}
    oracle = sum(any(item.values()) for item in correct.values())
    tool_pairs = [sample_id for sample_id in labels if (
        "parsed" in vision_by_id[sample_id]["final"]
        and "parsed" in branch_by_key[(sample_id, "A0")]["final"]
    )]
    vision_correct = {
        sid: vision_by_id[sid]["final"]["parsed"]["label"] == labels[sid]
        for sid in tool_pairs
    }
    tool_correct = {
        sid: branch_by_key[(sid, "A0")]["final"]["parsed"]["label"] == labels[sid]
        for sid in tool_pairs
    }
    return {
        "n_samples": len(labels), "n_complete_triplets": len(complete),
        "invalid_final_responses": invalid,
        "n_complete_vision_tool_A0_pairs": len(tool_pairs),
        "invalid_vision_final_responses": [
            {"sample_id": sid, "error": vision_by_id[sid]["final"].get("parse_error")}
            for sid in labels if "parsed" not in vision_by_id[sid]["final"]
        ],
        "vision_A0_correct_on_complete_pairs": sum(vision_correct.values()),
        "tool_A0_correct_on_complete_pairs": sum(tool_correct.values()),
        "tool_correction_sample_ids": [sid for sid in tool_pairs if not vision_correct[sid] and tool_correct[sid]],
        "tool_damage_sample_ids": [sid for sid in tool_pairs if vision_correct[sid] and not tool_correct[sid]],
        "correct_by_arm_on_complete_triplets": accuracy,
        "correction_sample_ids": correction, "damage_sample_ids": damage,
        "oracle_correct_on_complete_triplets": oracle,
        "best_fixed_correct_on_complete_triplets": max(accuracy.values()),
        "oracle_selection_room": oracle - max(accuracy.values()),
        "scope": "exploratory paired pilot; incomplete pairs/triplets excluded from respective comparisons",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--prefixes", type=Path, required=True)
    parser.add_argument("--branches", type=Path, required=True)
    parser.add_argument("--vision-baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(
        read_jsonl(args.manifest), read_jsonl(args.prefixes),
        read_jsonl(args.branches), read_jsonl(args.vision_baseline),
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
