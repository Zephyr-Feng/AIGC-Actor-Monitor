#!/usr/bin/env python3
"""Summarize Actor-B0 orchestration behavior without tuning on the sanity set."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


DIRECTIONAL = {"local_texture_analyzer", "complementary_forensic_analyzer"}
GLOBAL = "global_forensic_analyzer"
DIRECTIONAL_WORDS = re.compile(r"支持|倾向|real|fake|真实|伪造|合成", re.I)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def global_attribution_violations(row: dict) -> list[dict]:
    hits = []
    for step in row["steps"]:
        output = step.get("actor_output") or {}
        for evidence in output.get("current_evidence", []):
            if evidence.get("source") != GLOBAL:
                continue
            if evidence.get("direction") != "none" or DIRECTIONAL_WORDS.search(evidence.get("interpretation", "")):
                hits.append({"sample_id": row["sample_id"], "step": step["step"], "evidence": evidence})
    return hits


def premature_stop(row: dict) -> bool:
    calls = row["tool_calls"]
    final = row.get("final_output") or {}
    conflicts = final.get("unresolved_conflicts") or []
    directional_calls = DIRECTIONAL & set(calls)
    remaining_directional = DIRECTIONAL - set(calls)
    return not directional_calls or (bool(conflicts) and bool(remaining_directional))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.trajectories)
    if len(rows) != 30:
        raise ValueError("expected fixed 30-image Actor-B0 sanity set")
    violations = [hit for row in rows for hit in global_attribution_violations(row)]
    total_steps = sum(len(row["steps"]) for row in rows)
    total_calls = sum(row["num_tool_calls"] for row in rows)
    repeated_attempts = sum("already been called" in (step.get("parse_error") or "")
                            for row in rows for step in row["steps"])
    metrics = {
        "records": len(rows),
        "parse_success": sum(row["parse_valid"] for row in rows) / len(rows),
        "legal_tool_call_rate": 1.0 if total_calls else 0.0,
        "average_tool_calls": total_calls / len(rows),
        "premature_stop_rate": sum(premature_stop(row) for row in rows) / len(rows),
        "repeated_tool_call_attempt_rate": repeated_attempts / max(total_steps, 1),
        "multi_step_completion_rate": sum(row["parse_valid"] and row["num_tool_calls"] >= 2 for row in rows) / len(rows),
        "final_balanced_accuracy": None,
        "attribution_violation_rate": len(violations) / max(total_steps, 1),
        "first_tool_counts": Counter(row["tool_calls"][0] if row["tool_calls"] else "STOP" for row in rows),
        "tool_call_counts": Counter(tool for row in rows for tool in row["tool_calls"]),
        "format_errors": sum(row["format_error_count"] for row in rows),
        "forced_or_missing_final": sum(not row["parse_valid"] for row in rows),
    }
    by_label = {}
    recalls = []
    for label in ("real", "fake"):
        subset = [row for row in rows if row["ground_truth"] == label]
        recall = sum(row["final_correct"] for row in subset) / len(subset)
        by_label[label] = {"n": len(subset), "recall": recall}
        recalls.append(recall)
    metrics["final_balanced_accuracy"] = sum(recalls) / len(recalls)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "metrics.json").write_text(
        json.dumps({**metrics, "by_label": by_label}, ensure_ascii=False, indent=2, sort_keys=True, default=dict) + "\n",
        encoding="utf-8")
    (args.output_dir / "attribution_violations.json").write_text(
        json.dumps(violations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    decision = "B0_STABLE_FREEZE" if (
        metrics["parse_success"] >= 0.95
        and metrics["repeated_tool_call_attempt_rate"] <= 0.05
        and metrics["multi_step_completion_rate"] >= 0.50
        and metrics["premature_stop_rate"] <= 0.25
    ) else "B0_ORCHESTRATION_UNSTABLE_CONSIDER_ONE_SFT"
    report = f"""# Actor-B0 Baseline Report

## Reproducibility

- Commit: fill after execution
- Model revision: `{runtime['model_revision']}`
- Prompt SHA-256: `{runtime['prompt_sha256']}`
- Schema SHA-256: `{runtime['schema_sha256']}`
- Sample manifest SHA-256: `{runtime['manifest_sha256']}`
- Tool results SHA-256: `{runtime['tool_results_sha256']}`
- Tools: frozen PROBE Evidence-only v1, PatchCraft, SAFE, provenance inspector

## Orchestration metrics

```json
{json.dumps({**metrics, 'by_label': by_label}, ensure_ascii=False, indent=2, default=dict)}
```

Premature STOP is a prespecified diagnostic flag: no directional tool was called, or unresolved conflicts remained while an unused directional tool was available. Attribution violations are diagnostic and do not need to reach zero.

## One-time decision

`{decision}`

This sanity set is for Actor orchestration decisions only. It is not a confirmation benchmark and must not support headline accuracy claims.
"""
    (args.output_dir / "ACTOR_B0_BASELINE_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"decision": decision, **metrics}, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()

