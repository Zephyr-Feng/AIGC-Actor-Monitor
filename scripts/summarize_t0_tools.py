"""Descriptive audit of T0 raw tool results; no model selection or significance test."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl  # noqa: E402
from agent.tools import FAMILIES  # noqa: E402


def summarize(manifest: list[dict], tool_rows: list[dict], refs: dict | None = None) -> dict:
    samples = {row["sample_id"]: row for row in manifest}
    results = {row["sample_id"]: row for row in tool_rows}
    if samples.keys() != results.keys():
        raise ValueError("manifest and tool result sample IDs differ")

    by_group: dict[str, dict[str, str]] = defaultdict(dict)
    for row in manifest:
        by_group[row["source_group_id"]][row["label"]] = row["sample_id"]
    if any(set(labels) != {"real", "fake"} for labels in by_group.values()):
        raise ValueError("each T0 group must contain one real and one fake image")

    indexed = {
        sample_id: {item["tool"]: item for item in row["results"]}
        for sample_id, row in results.items()
    }
    report = {"n_images": len(manifest), "n_pairs": len(by_group), "tools": {}}
    for family, spec in FAMILIES.items():
        items = [indexed[sample_id][family] for sample_id in samples]
        missing = Counter()
        for item in items:
            for feature in spec["features"]:
                if feature not in item["values"]:
                    missing[feature] += 1
        paired_directions = {}
        outside_reference = {}
        for feature in spec["features"]:
            directions = Counter()
            for labels in by_group.values():
                real = indexed[labels["real"]][family]["values"].get(feature)
                fake = indexed[labels["fake"]][family]["values"].get(feature)
                if real is None or fake is None:
                    continue
                if not math.isfinite(real) or not math.isfinite(fake):
                    continue
                directions["fake_higher" if fake > real else "real_higher" if real > fake else "tie"] += 1
            paired_directions[feature] = dict(directions)
            if refs and feature in refs:
                low, high = refs[feature]
                outside = Counter()
                for sample_id, sample in samples.items():
                    value = indexed[sample_id][family]["values"].get(feature)
                    if value is not None and (value < low or value > high):
                        outside[sample["label"]] += 1
                outside_reference[feature] = dict(outside)
        report["tools"][family] = {
            "ok": sum(item["ok"] for item in items),
            "total": len(items),
            "missing_features": dict(missing),
            "median_elapsed_ms": round(statistics.median(item["elapsed_ms"] for item in items), 2),
            "paired_directions": paired_directions,
            "outside_reference": outside_reference,
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--references", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    refs = json.loads(args.references.read_text(encoding="utf-8"))["ranges"] if args.references else None
    report = summarize(read_jsonl(args.manifest), read_jsonl(args.tools), refs)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
