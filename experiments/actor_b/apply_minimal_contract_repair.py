#!/usr/bin/env python3
"""Keep legal original STOP outputs and repair only invalid verdict fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from actor_b_protocol import parse_action
from contract_replay import CANDIDATES, verdict_span
from run_b0 import canonical_hash, read_jsonl, sha256, write_json


def derive(original_path: Path, scored_path: Path) -> list[dict]:
    original_rows = read_jsonl(original_path)
    scored_rows = read_jsonl(scored_path)
    by_id = {row["sample_id"]: row for row in original_rows}
    if len(by_id) != 60 or len(scored_rows) != 60:
        raise ValueError("expected exactly 60 original and scored records")
    if {row["sample_id"] for row in scored_rows} != set(by_id):
        raise ValueError("scored replay IDs differ from the original trajectories")

    derived = []
    for scored in scored_rows:
        row = by_id[scored["sample_id"]]
        if scored["original_trajectories_sha256"] != sha256(original_path):
            raise ValueError("scored replay uses a different original trajectory file")
        if scored["pre_stop_steps_sha256"] != canonical_hash(row["steps"][:-1]):
            raise ValueError("pre-STOP history differs from the original")

        raw = row["steps"][-1]["attempts"][-1]["raw"]
        if scored["raw_unconstrained_output"] != raw:
            raise ValueError("saved raw STOP output differs from the original")
        parsed_raw, _, _ = verdict_span(raw)
        if parsed_raw.get("next_action") != "STOP":
            raise ValueError("last original action is not STOP")

        if row["parse_valid"]:
            if parsed_raw.get("final_verdict") not in CANDIDATES:
                raise ValueError("originally valid STOP does not have a legal verdict")
            selected_output = raw
            selection_policy = "preserve_original_legal_verdict"
        else:
            selected_output = scored["contract_constrained_output"]
            selection_policy = "model_forced_choice_for_invalid_verdict_only"

        parsed = parse_action(selected_output, set(row["tool_calls"]))
        if parsed["next_action"] != "STOP" or parsed["final_verdict"] not in CANDIDATES:
            raise ValueError("derived STOP output is not legal")
        constrained_obj = json.loads(selected_output)
        if {key: value for key, value in constrained_obj.items() if key != "final_verdict"} != {
            key: value for key, value in parsed_raw.items() if key != "final_verdict"
        }:
            raise ValueError("a non-verdict STOP field changed")

        derived_row = dict(scored)
        derived_row["contract_constrained_output"] = selected_output
        derived_row["contract_verdict"] = parsed["final_verdict"]
        derived_row["every_stop_forced_choice_verdict"] = scored["contract_verdict"]
        derived_row["selection_policy"] = selection_policy
        derived_row["verdict_preserved"] = (
            row["parse_valid"] and parsed["final_verdict"] == row["final_verdict"]
        )
        derived.append(derived_row)
    return derived


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-trajectories", type=Path, required=True)
    parser.add_argument("--scored-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = derive(args.original_trajectories, args.scored_replay)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    replay_path = args.output_dir / "replay.jsonl"
    replay_path.write_bytes(b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    ))
    original = read_jsonl(args.original_trajectories)
    write_json(args.output_dir / "runtime.json", {
        "method": "preserve original legal real/fake STOP verdicts; apply saved same-model forced choice only to invalid STOP verdicts",
        "records": len(rows),
        "model_forced_choice_records": sum(
            row["selection_policy"] == "model_forced_choice_for_invalid_verdict_only"
            for row in rows
        ),
        "preserved_legal_records": sum(
            row["selection_policy"] == "preserve_original_legal_verdict"
            for row in rows
        ),
        "original_trajectories_sha256": sha256(args.original_trajectories),
        "scored_replay_sha256": sha256(args.scored_replay),
        "derived_replay_sha256": sha256(replay_path),
        "original_valid": sum(row["parse_valid"] for row in original),
        "decoder_sha256": sha256(Path(__file__)),
    })
    print(json.dumps(json.loads((args.output_dir / "runtime.json").read_text(encoding="utf-8")),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
