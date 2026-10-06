"""Describe the paired T0 Actor comparison without choosing tools or tuning prompts."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl  # noqa: E402


def summarize(manifest: list[dict], records: list[dict]) -> dict:
    labels = {row["sample_id"]: row["label"] for row in manifest}
    by_sample: dict[str, dict[str, dict]] = {}
    for row in records:
        conditions = by_sample.setdefault(row["sample_id"], {})
        if row["condition"] in conditions:
            raise ValueError(f"duplicate condition for {row['sample_id']}")
        conditions[row["condition"]] = row
    if by_sample.keys() != labels.keys() or any(
        set(conditions) != {"vision_only", "with_tools"}
        for conditions in by_sample.values()
    ):
        raise ValueError("T0 comparison must contain both conditions for every image")

    report = {"kind": "T0-discovery-only", "n_images": len(labels), "conditions": {}}
    for condition in ("vision_only", "with_tools"):
        items = [by_sample[sample_id][condition] for sample_id in labels]
        parsed = [item for item in items if "final" in item]
        report["conditions"][condition] = {
            "n_final_parsed": len(parsed),
            "n_correct": sum(item["final"]["label"] == labels[item["sample_id"]] for item in parsed),
            "n_preliminary_parsed": sum("preliminary" in item for item in items),
            "median_generation_s": round(statistics.median(
                item["preliminary_s"] + item["final_s"] for item in items
            ), 3),
        }

    changes = Counter()
    for sample_id, conditions in by_sample.items():
        vision = conditions["vision_only"].get("final")
        tools = conditions["with_tools"].get("final")
        if vision is None or tools is None:
            changes["unpaired_parse_failure"] += 1
            continue
        vision_correct = vision["label"] == labels[sample_id]
        tool_correct = tools["label"] == labels[sample_id]
        if not vision_correct and tool_correct:
            changes["corrected_by_tools"] += 1
        elif vision_correct and not tool_correct:
            changes["harmed_by_tools"] += 1
        else:
            changes["same_correctness"] += 1
    report["paired_changes"] = dict(changes)
    report["interpretation_limit"] = (
        "24-image discovery check only; tool ranges are descriptive and historical "
        "source/compression differences may remain after common re-encoding."
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--actor-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(read_jsonl(args.manifest), read_jsonl(args.actor_results))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
