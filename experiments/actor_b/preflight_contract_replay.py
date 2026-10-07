#!/usr/bin/env python3
"""CPU-only structural check of the frozen 60 STOP replay inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from actor_b_protocol import parse_action
from contract_replay import reconstruct_stop_context, replace_verdict, verdict_span
from run_b0 import canonical_hash, read_jsonl, sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--tool-cards", type=Path, required=True)
    parser.add_argument("--experiment-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    if sha256(args.manifest) != runtime["manifest_sha256"]:
        raise ValueError("manifest SHA differs from original run")
    if sha256(args.tool_results) != runtime["tool_results_sha256"]:
        raise ValueError("tool results SHA differs from original run")
    prompt = (args.experiment_dir / "prompts/system_prompt.txt").read_text(encoding="utf-8").strip()
    schema = json.loads((args.experiment_dir / "schemas/actor_b_action.schema.json").read_text(encoding="utf-8"))
    generation = json.loads((args.experiment_dir / "config/generation_config.json").read_text(encoding="utf-8"))
    cards = json.loads(args.tool_cards.read_text(encoding="utf-8"))
    if canonical_hash({"system_prompt": prompt, "tool_cards": cards, "schema": schema,
                       "generation": generation}) != runtime["prompt_sha256"]:
        raise ValueError("frozen prompt material changed")
    records, manifest, tools = read_jsonl(args.trajectories), read_jsonl(args.manifest), read_jsonl(args.tool_results)
    if not (len(records) == len(manifest) == len(tools)):
        raise ValueError("record counts disagree")
    if [r["sample_id"] for r in records] != [r["sample_id"] for r in manifest]:
        raise ValueError("manifest order differs")
    by_id = {r["sample_id"]: r for r in tools}
    for row, item in zip(records, manifest):
        if row["image_sha256"] != item["sha256"]:
            raise ValueError("image SHA differs")
        available = {t["tool"]: t for t in by_id[row["sample_id"]]["tools"]}
        for step in row["steps"]:
            observation = step.get("tool_observation")
            if observation and observation != available[observation["tool"]]:
                raise ValueError("tool observation differs from frozen input")
        messages, raw = reconstruct_stop_context(row, "original-image-placeholder", prompt, cards, schema,
                                                 lambda path: ("crop-placeholder", path),
                                                 int(generation["max_tool_calls"]))
        original, _, _ = verdict_span(raw)
        for candidate in ("real", "fake"):
            amended = replace_verdict(raw, candidate)
            parsed = parse_action(amended, set(row["tool_calls"]))
            if parsed["final_verdict"] != candidate:
                raise AssertionError("replacement did not validate")
        if row["parse_valid"] and original["final_verdict"] != row["final_verdict"]:
            raise ValueError("valid original verdict differs")
        if not messages or messages[0]["role"] != "system":
            raise ValueError("STOP context is incomplete")
    result = {"records": len(records), "original_valid": sum(row["parse_valid"] for row in records),
              "original_invalid": sum(not row["parse_valid"] for row in records),
              "all_tool_observations_match": True, "all_stop_contexts_reconstruct": True,
              "both_legal_verdicts_parse_for_all": True,
              "trajectories_sha256": sha256(args.trajectories),
              "manifest_sha256": sha256(args.manifest), "tool_results_sha256": sha256(args.tool_results)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
