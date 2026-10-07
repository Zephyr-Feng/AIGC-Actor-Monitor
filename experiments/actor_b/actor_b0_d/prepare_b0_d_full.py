#!/usr/bin/env python3
"""Materialize the frozen B0-C trajectory as B0-D's FULL condition."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = ROOT / "experiments/actor_b/heldout_confirmation/outputs/trajectories.jsonl"
DEFAULT_POLICY = ROOT / "experiments/actor_b/contract_constrained/outputs/minimal_policy/replay.jsonl"
DEFAULT_OUT = Path(__file__).resolve().parent / "full"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--minimal-policy-replay", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    original = read_jsonl(args.trajectories)
    policy_rows = read_jsonl(args.minimal_policy_replay)
    if len(original) != 60 or len(policy_rows) != 60:
        raise ValueError("FULL reuses the complete frozen B0-C 60-sample trajectory")
    if [row["sample_id"] for row in original] != [row["sample_id"] for row in policy_rows]:
        raise ValueError("minimal-policy replay order differs from B0-C")
    original_sha = sha256(args.trajectories)
    policy_sha = sha256(args.minimal_policy_replay)

    output = []
    projected = 0
    for raw, policy in zip(original, policy_rows):
        if policy["original_trajectories_sha256"] != original_sha:
            raise ValueError("minimal-policy replay references a different B0-C trajectory")
        if policy["pre_stop_steps_sha256"] != hashlib.sha256(
            json.dumps(raw["steps"][:-1], ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
        ).hexdigest():
            raise ValueError("a B0-C pre-STOP step changed")
        if policy["raw_unconstrained_output"] != raw["steps"][-1]["attempts"][-1]["raw"]:
            raise ValueError("minimal-policy raw STOP differs from frozen B0-C")
        if policy["selection_policy"] == "model_forced_choice_for_invalid_verdict_only":
            if raw["parse_valid"]:
                raise ValueError("B0-C policy projects only invalid original verdicts")
            projected += 1
        elif policy["selection_policy"] == "preserve_original_legal_verdict":
            if not raw["parse_valid"]:
                raise ValueError("an invalid original verdict was marked preserved")
        else:
            raise ValueError("unknown minimal STOP policy")

        effective_raw = policy["contract_constrained_output"]
        effective = json.loads(effective_raw)
        if effective.get("next_action") != "STOP" or effective.get("final_verdict") not in ("real", "fake"):
            raise ValueError("FULL effective STOP output is not legal")
        row = dict(raw)
        row["condition"] = "FULL"
        row["raw_parse_valid"] = raw["parse_valid"]
        row["raw_final_output"] = raw.get("final_output")
        row["minimal_stop_policy"] = {
            "selection_policy": policy["selection_policy"],
            "raw_unconstrained_output": policy["raw_unconstrained_output"],
            "effective_output": effective_raw,
            "contract_verdict": policy["contract_verdict"],
            "verdict_log_likelihood": policy["verdict_log_likelihood"],
            "exact_tie_preserved_original": policy["exact_tie_preserved_original"],
        }
        row["effective_final_output"] = effective
        row["effective_parse_valid"] = True
        row["effective_final_verdict"] = effective["final_verdict"]
        row["effective_final_correct"] = effective["final_verdict"] == raw["ground_truth"]
        output.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = args.output_dir / "trajectories.jsonl"
    trajectory_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output),
        encoding="utf-8",
    )
    runtime = {
        "condition": "FULL",
        "records": len(output),
        "source": "reused frozen Actor-B0-C held-out trajectories; no rerun",
        "original_trajectories_sha256": original_sha,
        "minimal_policy_replay_sha256": policy_sha,
        "effective_trajectories_sha256": sha256(trajectory_path),
        "minimal_projection_records": projected,
        "preserved_legal_records": len(output) - projected,
    }
    (args.output_dir / "runtime.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
