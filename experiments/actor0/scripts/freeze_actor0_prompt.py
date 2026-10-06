#!/usr/bin/env python3
"""Freeze prompt/cards/generation only after stable development parsing."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def hash_prompt(config_dir: Path) -> str:
    material = {
        "system_prompt": (config_dir / "system_prompt.txt").read_text(encoding="utf-8").strip(),
        "tool_cards": json.loads((config_dir / "tool_cards.json").read_text(encoding="utf-8")),
        "baseline_prompts": json.loads((config_dir / "baseline_prompts.json").read_text(encoding="utf-8")),
        "generation": json.loads((config_dir / "generation_config.json").read_text(encoding="utf-8")),
    }
    encoded = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-trajectories", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, default=Path(__file__).resolve().parents[1] / "config")
    parser.add_argument("--expected", type=int, default=180)
    parser.add_argument("--minimum-parse-rate", type=float, default=0.95)
    args = parser.parse_args()
    rows = read_jsonl(args.dev_trajectories)
    if len(rows) != args.expected or len({row["sample_id"] for row in rows}) != args.expected:
        raise ValueError(f"expected {args.expected} unique development trajectories; got {len(rows)}")
    turns = [step for row in rows for step in row.get("steps", [])]
    parsed_turns = [step for step in turns if step.get("actor_output") is not None and not step.get("parse_error")]
    trajectory_rate = sum(bool(row.get("final_output")) and row.get("final_verdict") in ("real", "fake") for row in rows) / len(rows)
    step_rate = len(parsed_turns) / max(len(turns), 1)
    stable_trajectory_rate = sum(
        bool(row.get("final_output"))
        and row.get("final_verdict") in ("real", "fake")
        and all(step.get("actor_output") is not None and not step.get("parse_error") for step in row.get("steps", []))
        for row in rows
    ) / len(rows)
    result = {
        "development_trajectories": len(rows), "actor_turns": len(turns),
        "valid_turn_parse_rate": step_rate, "final_verdict_parse_rate": trajectory_rate,
        "fully_parseable_trajectory_rate": stable_trajectory_rate,
        "minimum_required_rate": args.minimum_parse_rate,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if min(step_rate, trajectory_rate, stable_trajectory_rate) < args.minimum_parse_rate:
        raise SystemExit("Prompt not frozen: development parsing has not reached the required threshold")
    prompt_sha = hash_prompt(args.config_dir)
    freeze_path = args.config_dir / "prompt_sha256.txt"
    payload = (
        prompt_sha + "  actor0-v1\n"
        + json.dumps({**result, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                      "development_manifest_sha256": hashlib.sha256(
                          (args.config_dir.parent / "data" / "actor0_dev_manifest.jsonl").read_bytes()
                      ).hexdigest()}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    if freeze_path.exists():
        if freeze_path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"existing prompt freeze differs; refusing overwrite: {freeze_path}")
    else:
        freeze_path.write_text(payload, encoding="utf-8", newline="\n")
    print(f"FROZEN {prompt_sha}")


if __name__ == "__main__":
    main()
