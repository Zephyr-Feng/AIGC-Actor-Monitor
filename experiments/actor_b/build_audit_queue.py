#!/usr/bin/env python3
"""Render accepted Actor steps and observed tool signals for human audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.trajectories.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    queue = []
    for row in rows:
        observed = {}
        for step in row["steps"]:
            actor = step.get("actor_output")
            if actor is not None:
                queue.append({
                    "sample_id": row["sample_id"],
                    "step": step["step"],
                    "next_action": actor["next_action"],
                    "selected_tool": actor["selected_tool"],
                    "tool_signals_available": dict(observed),
                    "current_evidence": actor["current_evidence"],
                    "unresolved_conflicts": actor["unresolved_conflicts"],
                    "evidence_gap": actor["evidence_gap"],
                    "action_reason": actor["action_reason"],
                    "final_verdict": actor["final_verdict"],
                })
            observation = step.get("tool_observation")
            if observation:
                observed[observation["tool"]] = {
                    "signal": observation.get("signal"),
                    "score": observation.get("score"),
                    "strength": observation.get("strength"),
                    "limitations": observation.get("limitations"),
                }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
                                   for item in queue), encoding="utf-8")
    print(f"{len(rows)} trajectories, {len(queue)} accepted steps for human review")


if __name__ == "__main__":
    main()
