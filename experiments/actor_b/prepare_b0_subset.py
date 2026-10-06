#!/usr/bin/env python3
"""Select a fixed 30-image Actor-B0 sanity subset from frozen Actor dev data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def direction(tool: dict) -> str | None:
    signal = tool.get("signal")
    if signal in ("fake", "synthetic_like"):
        return "fake"
    if signal in ("real", "real_like"):
        return "real"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-generator", type=int, default=10)
    args = parser.parse_args()

    rows = read_jsonl(args.manifest)
    tools = {row["sample_id"]: row for row in read_jsonl(args.tool_results)}
    candidates = []
    for row in rows:
        record = tools[row["sample_id"]]
        by_name = {item["tool"]: item for item in record["tools"]}
        directions = [direction(by_name[name]) for name in
                      ("local_texture_analyzer", "complementary_forensic_analyzer")]
        directions = [item for item in directions if item]
        candidates.append({
            "row": row,
            "record": record,
            "conflict": len(set(directions)) > 1,
        })

    selected, used_groups = [], set()
    for generator in ("raise", "flux", "sd3_5"):
        pool = [item for item in candidates if item["row"]["generator"] == generator]
        chosen = []
        conflict_target = args.per_generator // 2
        for conflict, target in ((True, conflict_target), (False, args.per_generator - conflict_target)):
            available = sorted((item for item in pool if item["conflict"] is conflict),
                               key=lambda item: item["row"]["sample_id"])
            count = 0
            for item in available:
                group = item["row"]["source_group"]
                if group in used_groups:
                    continue
                chosen.append(item)
                used_groups.add(group)
                count += 1
                if count == target:
                    break
            if count != target:
                raise ValueError(f"not enough conflict={conflict} cases for {generator}")
        if len(chosen) != args.per_generator:
            raise ValueError(f"not enough disjoint source groups for {generator}")
        selected.extend(chosen)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_out = args.output_dir / "b0_sanity_manifest.jsonl"
    tools_out = args.output_dir / "b0_nonprobe_tools.jsonl"
    manifest_out.write_text("".join(json.dumps(item["row"], ensure_ascii=False, sort_keys=True) + "\n"
                                    for item in selected), encoding="utf-8")
    nonprobe = []
    for item in selected:
        record = dict(item["record"])
        record["tools"] = [tool for tool in record["tools"] if tool["tool"] != "global_forensic_analyzer"]
        record.pop("tool_score_sources", None)
        record.pop("internal_implementations", None)
        nonprobe.append(record)
    tools_out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                 for row in nonprobe), encoding="utf-8")

    summary = {
        "selection": "30 Actor-0 development images; unique source groups; 5 conflict and 5 agreement cases per generator",
        "images": len(selected),
        "source_groups": len(used_groups),
        "generator_counts": Counter(item["row"]["generator"] for item in selected),
        "label_counts": Counter(item["row"]["label"] for item in selected),
        "directional_conflict_count": sum(item["conflict"] for item in selected),
        "source_manifest_sha256": sha256(args.manifest),
        "source_tool_results_sha256": sha256(args.tool_results),
        "manifest_sha256": sha256(manifest_out),
        "nonprobe_tools_sha256": sha256(tools_out),
        "note": "PROBE classifier observations were removed. Frozen Evidence-only cards must be generated separately.",
    }
    (args.output_dir / "selection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()

