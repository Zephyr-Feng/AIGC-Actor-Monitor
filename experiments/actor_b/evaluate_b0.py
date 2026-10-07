#!/usr/bin/env python3
"""Summarize Actor-B0 orchestration behavior without tuning on the sanity set."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from actor_b_protocol import TOOLS, extract_object


DIRECTIONAL = {"local_texture_analyzer", "complementary_forensic_analyzer"}
GLOBAL = "global_forensic_analyzer"


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
            # "inconclusive" is non-directional. Free-text claims require a
            # separate manual audit; negated Chinese phrases defeat regexes.
            if evidence.get("direction") in ("real", "fake"):
                hits.append({"sample_id": row["sample_id"], "step": step["step"], "evidence": evidence})
    return hits


def premature_stop(row: dict) -> bool:
    if not row["parse_valid"]:
        return False
    calls = row["tool_calls"]
    final = row.get("final_output") or {}
    conflicts = final.get("unresolved_conflicts") or []
    directional_calls = DIRECTIONAL & set(calls)
    remaining_directional = DIRECTIONAL - set(calls)
    return not directional_calls or (bool(conflicts) and bool(remaining_directional))


def call_attempts(row: dict) -> tuple[int, int, int]:
    requested = legal = repeated = 0
    used = set()
    for step in row["steps"]:
        for attempt in step["attempts"]:
            try:
                output = extract_object(attempt["raw"])
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            if output.get("next_action") != "CALL_TOOL":
                continue
            requested += 1
            tool = output.get("selected_tool")
            if isinstance(tool, str) and tool in used:
                repeated += 1
            if isinstance(tool, str) and tool in TOOLS and tool not in used and output.get("final_verdict") is None:
                legal += 1
        accepted = step.get("actor_output") or {}
        if accepted.get("next_action") == "CALL_TOOL" and step.get("tool_observation"):
            used.add(accepted["selected_tool"])
    return requested, legal, repeated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, default=30)
    args = parser.parse_args()
    rows = read_jsonl(args.trajectories)
    if len(rows) != args.expected_records:
        raise ValueError(f"expected {args.expected_records} Actor-B records")
    violations = [hit for row in rows for hit in global_attribution_violations(row)]
    total_steps = sum(len(row["steps"]) for row in rows)
    accepted_steps = sum(step.get("actor_output") is not None for row in rows for step in row["steps"])
    total_calls = sum(row["num_tool_calls"] for row in rows)
    requested, legal, repeated_attempts = map(sum, zip(*(call_attempts(row) for row in rows)))
    metrics = {
        "records": len(rows),
        "accepted_steps": accepted_steps,
        "total_steps": total_steps,
        "parse_success": sum(row["parse_valid"] for row in rows) / len(rows),
        "legal_tool_call_rate": legal / requested if requested else None,
        "tool_call_requests": requested,
        "average_tool_calls": total_calls / len(rows),
        "premature_stop_rate": sum(premature_stop(row) for row in rows) / len(rows),
        "repeated_tool_call_attempt_rate": repeated_attempts / requested if requested else None,
        "multi_step_completion_rate": sum(row["parse_valid"] and row["num_tool_calls"] >= 2 for row in rows) / len(rows),
        "final_balanced_accuracy": None,
        "global_directional_attribution_steps": len(violations),
        "global_directional_attribution_step_rate": len(violations) / max(accepted_steps, 1),
        "global_directional_attribution_samples": len({hit["sample_id"] for hit in violations}),
        "first_tool_counts": Counter(row["tool_calls"][0] if row["tool_calls"] else "STOP" for row in rows),
        "tool_call_counts": Counter(tool for row in rows for tool in row["tool_calls"]),
        "tool_call_distribution": Counter(row["num_tool_calls"] for row in rows),
        "tool_sequence_distribution": Counter(" > ".join(row["tool_calls"]) or "STOP"
                                               for row in rows),
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
    decision = "B0_REVIEW_REQUIRED"
    report = f"""# Actor-B Orchestration Report

## Reproducibility

- Runtime metadata and exact code revisions are recorded with this run; use the freeze manifest for a frozen Actor release.
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

Premature STOP is a diagnostic flag: no directional tool was called, or unresolved conflicts remained while an unused directional tool was available. Global directional attribution counts only explicit `real`/`fake` source directions; `inconclusive` is non-directional. Free-text interpretations need manual review. These errors do not automatically trigger SFT.

## Decision status

`{decision}`

This set is for Actor orchestration decisions only. It is not an accuracy benchmark and must not support headline accuracy claims.
"""
    (args.output_dir / "ACTOR_B_ORCHESTRATION_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"decision": decision, **metrics}, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()

