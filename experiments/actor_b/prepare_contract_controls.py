#!/usr/bin/env python3
"""Choose fixed successful STOP controls from the original held-out 60."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from run_b0 import read_jsonl, sha256


def features(row: dict) -> set[str]:
    final = row["final_output"]
    verdict, confidence = final["final_verdict"], final["final_confidence"]
    return {f"verdict:{verdict}", f"confidence:{confidence}",
            f"verdict_confidence:{verdict}:{confidence}",
            f"conflict:{bool(final['unresolved_conflicts'])}",
            "sequence:" + ">".join(row["tool_calls"])}


def select_controls(rows: list[dict], count: int) -> list[dict]:
    candidates = [row for row in rows if row["parse_valid"]]
    if len(candidates) < count:
        raise ValueError("too few valid controls")
    chosen, covered = [], set()
    while len(chosen) < count:
        remaining = [row for row in candidates if row not in chosen]
        row = min(remaining, key=lambda item: (
            -len(features(item) - covered),
            hashlib.sha256(("actor-b0-c-control-v1:" + item["sample_id"]).encode()).hexdigest()))
        chosen.append(row)
        covered |= features(row)
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--count", type=int, default=15)
    args = parser.parse_args()
    rows = read_jsonl(args.trajectories)
    if len(rows) != 60 or sum(row["parse_valid"] for row in rows) != 55:
        raise ValueError("expected the original held-out 60 with 55 valid finals")
    chosen = select_controls(rows, args.count)
    records = [{"sample_id": row["sample_id"],
                "original_verdict": row["final_verdict"],
                "original_confidence": row["final_output"]["final_confidence"],
                "tool_sequence": row["tool_calls"],
                "has_unresolved_conflict": bool(row["final_output"]["unresolved_conflicts"])}
               for row in chosen]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(b"".join((json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n").encode()
                                    for item in records))
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    summary = {"selection": "deterministic greedy coverage of verdict, confidence, conflict, tool sequence",
               "source_trajectories_sha256": sha256(args.trajectories), "controls": len(chosen),
               "verdict_counts": dict(Counter(row["final_verdict"] for row in chosen)),
               "confidence_counts": dict(Counter(str(row["final_output"]["final_confidence"]) for row in chosen)),
               "conflict_counts": dict(Counter(str(bool(row["final_output"]["unresolved_conflicts"]))
                                               for row in chosen)),
               "unique_tool_sequences": len({tuple(row["tool_calls"]) for row in chosen}),
               "controls_sha256": sha256(args.output)}
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
