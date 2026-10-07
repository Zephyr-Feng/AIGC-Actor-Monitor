#!/usr/bin/env python3
"""Freeze 60 source-disjoint confirmation images from existing Actor-0 eval data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from prepare_b0_subset import direction, read_jsonl, sha256


GENERATORS = ("raise", "flux", "sd3_5")


def has_directional_conflict(record: dict) -> bool:
    by_name = {item["tool"]: item for item in record["tools"]}
    signals = {direction(by_name[name]) for name in
               ("local_texture_analyzer", "complementary_forensic_analyzer")}
    signals.discard(None)
    return len(signals) > 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--b0-manifest", type=Path, required=True)
    parser.add_argument("--mini-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = read_jsonl(args.manifest)
    by_id = {row["sample_id"]: row for row in read_jsonl(args.tool_results)}
    if len(rows) != 300 or len(by_id) != 300 or set(by_id) != {row["sample_id"] for row in rows}:
        raise ValueError("expected aligned frozen Actor-0 eval inputs")
    excluded = {row["source_group"] for path in (args.b0_manifest, args.mini_manifest)
                for row in read_jsonl(path)}
    by_group: dict[str, dict[str, dict]] = {}
    for row in rows:
        by_group.setdefault(row["source_group"], {})[row["generator"]] = row
    eligible = {group: items for group, items in by_group.items()
                if group not in excluded and set(items) == set(GENERATORS)}
    strata = {False: [], True: []}
    for group, items in eligible.items():
        conflict = has_directional_conflict(by_id[items["raise"]["sample_id"]])
        strata[conflict].append(group)
    for conflict in strata:
        strata[conflict].sort(key=lambda group: hashlib.sha256(
            f"actor-b-heldout-20261007:{group}".encode()).hexdigest())
        if len(strata[conflict]) < 10:
            raise ValueError(f"insufficient eligible conflict={conflict} groups")
    chosen = set(strata[False][:10] + strata[True][:10])
    selected = [by_group[group][generator] for group in sorted(chosen) for generator in GENERATORS]
    if len(selected) != 60 or len({row["source_group"] for row in selected}) != 20:
        raise ValueError("held-out selection must contain 20 groups and 60 images")
    nonprobe = []
    conflicts = Counter()
    for row in selected:
        record = dict(by_id[row["sample_id"]])
        conflicts[(row["generator"], has_directional_conflict(record))] += 1
        record["tools"] = [tool for tool in record["tools"]
                           if tool["tool"] != "global_forensic_analyzer"]
        record.pop("tool_score_sources", None)
        record.pop("internal_implementations", None)
        nonprobe.append(record)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_out = args.output_dir / "heldout_manifest.jsonl"
    tools_out = args.output_dir / "heldout_nonprobe_tools.jsonl"
    manifest_out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                    for row in selected), encoding="utf-8")
    tools_out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                 for row in nonprobe), encoding="utf-8")
    summary = {
        "selection": "20 Actor-0 eval source groups: 10 with real-image directional tool conflict, 10 without; all three generator rows per group; deterministic SHA-256 group ranking",
        "source_data": "Existing frozen Actor-0 eval manifest and tool observations; original B-Free and RAISE PNG bytes, no new image generation",
        "known_license": {"b_free": "Informational and nonprofit research use; retain notices and cite authors",
                          "raise": "Scientific non-commercial use; retain RAISE license and notice"},
        "images": len(selected),
        "source_groups": len(chosen),
        "generator_counts": dict(Counter(row["generator"] for row in selected)),
        "label_counts": dict(Counter(row["label"] for row in selected)),
        "directional_conflict_counts": {f"{gen}:{conflict}": conflicts[(gen, conflict)]
                                        for gen in GENERATORS for conflict in (False, True)},
        "excluded_mini_groups": len({row["source_group"] for row in read_jsonl(args.mini_manifest)}),
        "remaining_eval_groups_reserved_for_monitor_test": len(eligible) - len(chosen),
        "source_manifest_sha256": sha256(args.manifest),
        "source_tool_results_sha256": sha256(args.tool_results),
        "manifest_sha256": sha256(manifest_out),
        "nonprobe_tools_sha256": sha256(tools_out),
        "note": "Raw PROBE classifier outputs removed; existing frozen Evidence-only v1 eval cards and crops are reused with callable-name alias only. This stratified confirmation set is not an accuracy benchmark.",
    }
    (args.output_dir / "selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
