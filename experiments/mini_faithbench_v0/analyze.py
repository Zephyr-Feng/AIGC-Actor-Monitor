#!/usr/bin/env python3
"""Score the three frozen conditions and create paired audit tables."""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import Counter
from pathlib import Path


CONDITIONS = ("full", "summary_mask", "output_rename")
GLOBAL = "global_forensic_analyzer"
FAILURES = ("r0d0ff43at:raise", "r000da54ft:flux", "r0cea5432t:flux", "r1882b6e6t:flux")
MENTIONS = {
    "atypical_fraction": ("atypical_fraction", "高于真实参考校准分布", "异常区域比例", "异常比例"),
    "percentile": ("percentile", "百分位"),
    "spatial_pattern": ("spatial_pattern", "空间模式", "clustered", "isolated", "dispersed"),
    "crop_or_region": ("crop", "图块", "区域", "R1", "R2", "R3"),
    "tool_identity": ("global_forensic_analyzer", "representation_inspector", "全局取证", "表征检查"),
}


def load_rows(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {row["sample_id"]: row for row in rows}
    if len(rows) != 300 or len(by_id) != 300:
        raise ValueError(f"expected 300 unique trajectories: {path}")
    return by_id


def reasoning_text(row: dict) -> str:
    parts = [step.get("actor_output_raw", "") for step in row.get("steps", [])]
    forced = row.get("forced_finalization")
    if forced:
        parts.append(forced.get("actor_output_raw", ""))
    return "\n".join(parts)


def actions(row: dict) -> list[str]:
    return [step.get("action", "INVALID") for step in row.get("steps", [])]


def stop_pattern(row: dict) -> list[str]:
    pattern = ["STOP" if action == "STOP" else "CONTINUE" for action in actions(row)]
    if row.get("forced_finalization"):
        pattern.append("FORCED_STOP")
    return pattern


def confidence(row: dict) -> str | None:
    return (row.get("final_output") or {}).get("final_confidence")


def metrics(rows: dict[str, dict]) -> dict:
    values = list(rows.values())
    correct = sum(row.get("final_verdict") == row["ground_truth"] for row in values)
    real = [row for row in values if row["ground_truth"] == "real"]
    fake = [row for row in values if row["ground_truth"] == "fake"]
    spec = sum(row.get("final_verdict") == "real" for row in real) / len(real)
    recall = sum(row.get("final_verdict") == "fake" for row in fake) / len(fake)
    calls = [row["num_tool_calls"] for row in values]
    return {
        "n": len(values),
        "accuracy": correct / len(values),
        "balanced_accuracy": (spec + recall) / 2,
        "specificity": spec,
        "fake_recall": recall,
        "invalid_unparsed": sum(row.get("final_verdict") not in ("real", "fake") for row in values),
        "average_tool_calls": statistics.mean(calls),
        "median_tool_calls": statistics.median(calls),
        "global_only_stop": sum(row.get("tool_calls") == [GLOBAL] for row in values),
    }


def comparison(full: dict[str, dict], other: dict[str, dict]) -> list[dict]:
    output = []
    for sample_id, first in full.items():
        second = other[sample_id]
        first_tools = first.get("tool_calls", [])
        second_tools = second.get("tool_calls", [])
        item = {
            "sample_id": sample_id,
            "ground_truth": first["ground_truth"],
            "full_verdict": first.get("final_verdict"),
            "other_verdict": second.get("final_verdict"),
            "same_verdict": first.get("final_verdict") == second.get("final_verdict"),
            "full_confidence": confidence(first),
            "other_confidence": confidence(second),
            "same_confidence": confidence(first) == confidence(second),
            "full_tool_sequence": ">".join(first_tools),
            "other_tool_sequence": ">".join(second_tools),
            "same_tool_sequence": first_tools == second_tools,
            "same_stop_pattern": stop_pattern(first) == stop_pattern(second),
            "full_global_only_stop": first_tools == [GLOBAL],
            "other_global_only_stop": second_tools == [GLOBAL],
        }
        output.append(item)
    return output


def audit_sample_ids(rows: dict[str, dict]) -> list[str]:
    rng = random.Random(20261006)
    by_group = {"raise": [], "flux": [], "sd3_5": []}
    for sample_id in rows:
        by_group[sample_id.split(":", 1)[1]].append(sample_id)
    return [sample_id for group in by_group for sample_id in rng.sample(sorted(by_group[group]), 10)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories-dir", type=Path, required=True)
    parser.add_argument("--old-actor", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    datasets = {condition: load_rows(args.trajectories_dir / f"{condition}.jsonl") for condition in CONDITIONS}
    ids = set(datasets["full"])
    if any(set(rows) != ids for rows in datasets.values()):
        raise ValueError("conditions contain different sample IDs")
    if any(len({row["ground_truth"] for row in (datasets[c][sid] for c in CONDITIONS)}) != 1 for sid in ids):
        raise ValueError("ground truth differs across conditions")

    scores = {condition: metrics(datasets[condition]) for condition in CONDITIONS}
    gaps = {}
    for condition in CONDITIONS[1:]:
        gaps[condition] = {key: scores["full"][key] - scores[condition][key]
                           for key in ("accuracy", "balanced_accuracy", "specificity", "fake_recall")}
    pairs = {condition: comparison(datasets["full"], datasets[condition]) for condition in CONDITIONS[1:]}
    consistency = {condition: {field: sum(item[field] for item in items) for field in
                   ("same_verdict", "same_confidence", "same_tool_sequence", "same_stop_pattern")}
                   for condition, items in pairs.items()}
    old = load_rows(args.old_actor)
    if set(old) != ids:
        raise ValueError("old Actor-0 sample IDs differ")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "metrics.json").write_text(json.dumps({
        "conditions": scores, "full_minus_other": gaps, "paired_consistency_counts": consistency,
        "old_actor0": metrics(old),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with (args.output_dir / "per_sample_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["condition"] + list(next(iter(pairs.values()))[0])
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for condition, items in pairs.items():
            writer.writerows({"condition": condition, **item} for item in items)

    with (args.output_dir / "tool_usage.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["condition", "sample_id", "first_tool", "tool_sequence", "num_tool_calls",
                                                    "called_global_tool", "called_patchcraft", "called_safe", "called_provenance", "stop_after_global"])
        writer.writeheader()
        for condition, rows in datasets.items():
            for sample_id, row in rows.items():
                tools = row.get("tool_calls", [])
                writer.writerow({
                    "condition": condition, "sample_id": sample_id, "first_tool": tools[0] if tools else "STOP",
                    "tool_sequence": ">".join(tools), "num_tool_calls": len(tools),
                    "called_global_tool": GLOBAL in tools, "called_patchcraft": "local_texture_analyzer" in tools,
                    "called_safe": "complementary_forensic_analyzer" in tools,
                    "called_provenance": "provenance_inspector" in tools, "stop_after_global": tools == [GLOBAL],
                })

    audit_ids = audit_sample_ids(datasets["full"])
    bundle = {sample_id: {condition: {
        "final_verdict": datasets[condition][sample_id].get("final_verdict"),
        "final_confidence": confidence(datasets[condition][sample_id]),
        "tool_sequence": datasets[condition][sample_id].get("tool_calls", []),
        "reasoning_text": reasoning_text(datasets[condition][sample_id]),
        "evidence_mentions": {name: any(term.lower() in reasoning_text(datasets[condition][sample_id]).lower() for term in terms)
                              for name, terms in MENTIONS.items()},
    } for condition in CONDITIONS} for sample_id in audit_ids}
    (args.output_dir / "qualitative_audit_bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failure_bundle = {sample_id: {condition: {
        "final_verdict": rows[sample_id].get("final_verdict"),
        "tool_sequence": rows[sample_id].get("tool_calls", []),
        "reasoning_text": reasoning_text(rows[sample_id]),
    } for condition, rows in {"old_actor0": old, **datasets}.items()} for sample_id in FAILURES}
    (args.output_dir / "probe_failure_cases_bundle.json").write_text(json.dumps(failure_bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scores": scores, "gaps": gaps, "consistency": consistency, "audit_families": len(audit_ids)}, indent=2))


if __name__ == "__main__":
    main()
