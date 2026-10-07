#!/usr/bin/env python3
"""Audit the two-stage STOP field constraint without changing old trajectories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from actor_b_protocol import parse_action
from run_b0 import canonical_hash, read_jsonl, sha256, write_json


def evaluate(original: list[dict], replay: list[dict], controls: set[str], mode: str) -> dict:
    by_id = {row["sample_id"]: row for row in original}
    if len(by_id) != 60 or len(replay) != (20 if mode == "pilot" else 60):
        raise ValueError("unexpected replay size")
    failures = {row["sample_id"] for row in original if not row["parse_valid"]}
    if len(failures) != 5 or len(controls) != 15 or controls & failures:
        raise ValueError("frozen failures and controls differ")
    expected = failures | controls if mode == "pilot" else set(by_id)
    if {row["sample_id"] for row in replay} != expected:
        raise ValueError("replay IDs differ from the fixed evaluation set")
    if len({row["sample_id"] for row in replay}) != len(replay):
        raise ValueError("duplicate replay sample")
    valid, preserved, failed_fixed, sequence_preserved = 0, 0, 0, 0
    for item in replay:
        row = by_id[item["sample_id"]]
        raw = row["steps"][-1]["attempts"][-1]["raw"]
        if item["raw_unconstrained_output"] != raw:
            raise ValueError("raw original STOP output changed")
        if item["pre_stop_steps_sha256"] != canonical_hash(row["steps"][:-1]):
            raise ValueError("pre-STOP trajectory changed")
        before = json.loads(raw)
        after = json.loads(item["contract_constrained_output"])
        if {k: v for k, v in before.items() if k != "final_verdict"} != {
            k: v for k, v in after.items() if k != "final_verdict"
        }:
            raise ValueError("a non-verdict STOP field changed")
        parsed = parse_action(item["contract_constrained_output"], set(row["tool_calls"]))
        if parsed["final_verdict"] != item["contract_verdict"]:
            raise ValueError("constrained verdict differs from parsed output")
        valid += 1
        if item["tool_calls"] == row["tool_calls"]:
            sequence_preserved += 1
        if row["parse_valid"] and item["contract_verdict"] == row["final_verdict"]:
            preserved += 1
        if not row["parse_valid"]:
            failed_fixed += 1
    original_valid_in_replay = sum(by_id[item["sample_id"]]["parse_valid"] for item in replay)
    result = {"mode": mode, "records": len(replay), "parse_success": valid / len(replay),
              "forced_or_missing_final": len(replay) - valid,
              "five_original_failures_fixed": failed_fixed,
              "original_valid_in_replay": original_valid_in_replay,
              "valid_verdict_preservation_count": preserved,
              "valid_verdict_preservation_rate": preserved / original_valid_in_replay,
              "tool_sequence_preservation_count": sequence_preserved,
              "tool_sequence_preservation_rate": sequence_preserved / len(replay),
              "pre_stop_history_preserved": True, "non_verdict_stop_fields_preserved": True}
    if mode == "pilot":
        result["pilot_technical_gate_pass"] = (
            valid == 20 and failed_fixed == 5 and sequence_preserved == 20
        )
    else:
        result["freeze_gate_pass"] = (valid == 60 and preserved == 55 and
                                       sequence_preserved == 60)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--original-trajectories", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    original = read_jsonl(args.original_trajectories)
    replay = read_jsonl(args.replay)
    controls = {row["sample_id"] for row in read_jsonl(args.controls)}
    for item in replay:
        if item["original_trajectories_sha256"] != sha256(args.original_trajectories):
            raise ValueError("replay comes from a different original trajectory file")
    metrics = evaluate(original, replay, controls, args.mode)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "metrics.json", metrics)
    report = f"""# Actor-B0-C {args.mode} STOP contract replay

- Original trajectories SHA-256: `{sha256(args.original_trajectories)}`
- Replay SHA-256: `{sha256(args.replay)}`
- Records: {metrics['records']}
- Legal constrained STOP: {metrics['records'] - metrics['forced_or_missing_final']}/{metrics['records']}
- Originally invalid STOP repaired: {metrics['five_original_failures_fixed']}/5
- Original valid verdict preserved: {metrics['valid_verdict_preservation_count']}/{metrics['original_valid_in_replay']}
- Tool sequence preserved: {metrics['tool_sequence_preservation_count']}/{metrics['records']}
- Pre-STOP steps and all non-verdict STOP fields: exact preservation confirmed.

{'Pilot gate pass: ' + str(metrics['pilot_gate_pass']) if args.mode == 'pilot' else 'Freeze gate pass: ' + str(metrics['freeze_gate_pass'])}

This report checks only the STOP output contract and preservation. It does not judge forensic accuracy or repair evidence attribution.
"""
    (args.output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
