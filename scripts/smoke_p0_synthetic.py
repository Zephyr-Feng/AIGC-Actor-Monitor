"""Write an explicitly synthetic ten-image P0 ledger and validate it.

This exercises file handoff only. It does not call an Actor or use real images.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import ARMS, read_jsonl, validate_p0  # noqa: E402


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)

    manifest: list[dict] = []
    prefixes: list[dict] = []
    outcomes: list[dict] = []
    for index in range(10):
        sample_id = f"synthetic-image-{index:02d}"
        episode_id = f"{sample_id}|seed0"
        label = "real" if index % 2 == 0 else "fake"
        image_sha256 = digest(f"placeholder image {index}")
        prefix = {
            "episode_id": episode_id,
            "sample_id": sample_id,
            "source_group_id": sample_id,
            "checkpoint_id": "G_late",
            "reached": True,
            "prefix_hash": digest(f"placeholder prefix {index}"),
            "image_sha256": image_sha256,
            "messages_sha256": digest(f"placeholder messages {index}"),
            "tool_outputs_sha256": digest(f"placeholder tools {index}"),
            "actor_hash": digest("synthetic actor"),
            "prompt_hash": digest("synthetic prompt"),
            "tool_hash": digest("synthetic tool version"),
            "channel_hash": digest("synthetic channel"),
            "decoding_seed": 0,
            "synthetic": True,
        }
        manifest.append({
            "sample_id": sample_id,
            "source_group_id": sample_id,
            "label": label,
            "image_sha256": image_sha256,
            "split": "P0-synthetic",
            "synthetic": True,
        })
        prefixes.append(prefix)
        for arm in sorted(ARMS):
            outcomes.append({
                "episode_id": episode_id,
                "arm": arm,
                "prefix_hash": prefix["prefix_hash"],
                "arm_version": "synthetic-v0",
                "answer": label,
                "correct": True,
                "abstained": False,
                "compute_cost": 0.0,
                "synthetic": True,
                **{field: prefix[field] for field in (
                    "image_sha256", "messages_sha256", "tool_outputs_sha256",
                    "actor_hash", "prompt_hash", "tool_hash", "channel_hash",
                    "decoding_seed",
                )},
            })

    write_jsonl(output / "manifest.jsonl", manifest)
    write_jsonl(output / "prefixes.jsonl", prefixes)
    write_jsonl(output / "outcomes.jsonl", outcomes)
    (output / "SYNTHETIC_DO_NOT_USE_FOR_RESEARCH.txt").write_text(
        "Synthetic file-contract check only. No images, model inference, or experimental results.\n",
        encoding="utf-8",
    )
    report = validate_p0(
        read_jsonl(output / "manifest.jsonl"),
        read_jsonl(output / "prefixes.jsonl"),
        read_jsonl(output / "outcomes.jsonl"),
    )
    (output / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
