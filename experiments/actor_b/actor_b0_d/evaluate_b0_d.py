#!/usr/bin/env python3
"""Evaluate paired B0-D trajectories without using Actor verdicts to define conflict."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
ACTOR_DIR = ROOT / "experiments/actor_b"
if str(ACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(ACTOR_DIR))
from actor_b_protocol import extract_object  # noqa: E402
CONDITIONS = {
    "FULL": "full",
    "PROBE-MASK": "probe_mask",
    "PROBE-DELAY": "probe_delay",
    "TOOL-RENAME": "tool_rename",
}
TOOLS = (
    "global_forensic_analyzer",
    "local_texture_analyzer",
    "complementary_forensic_analyzer",
    "provenance_inspector",
)
ALIASES = {
    "tool_alpha": "global_forensic_analyzer",
    "tool_beta": "local_texture_analyzer",
    "tool_gamma": "complementary_forensic_analyzer",
    "tool_delta": "provenance_inspector",
}
EVIDENCE_TYPES = {
    "global_forensic_analyzer": "representation_deviation",
    "local_texture_analyzer": "local_texture",
    "complementary_forensic_analyzer": "complementary_forensic",
    "provenance_inspector": "provenance_metadata",
    "visual": "visual_inspection",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def canonical_tool(value: Any) -> str | None:
    if value in TOOLS:
        return value
    return ALIASES.get(value) if isinstance(value, str) else None


def direction(tool_row: dict[str, Any]) -> str | None:
    name = tool_row.get("tool")
    signal = tool_row.get("signal")
    if name == "complementary_forensic_analyzer" and signal in ("real", "fake"):
        return signal
    if name == "local_texture_analyzer":
        return {"real_like": "real", "synthetic_like": "fake"}.get(signal)
    return None


def load_conflict_labels(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    result = {}
    for row in rows:
        by_tool = {item["tool"]: item for item in row["tools"]}
        local = by_tool["local_texture_analyzer"]
        complementary = by_tool["complementary_forensic_analyzer"]
        local_direction = direction(local)
        complementary_direction = direction(complementary)
        conflict = (
            local_direction in ("real", "fake")
            and complementary_direction in ("real", "fake")
            and local_direction != complementary_direction
        )
        result[row["sample_id"]] = {
            "frozen_tool_conflict": conflict,
            "local_direction": local_direction,
            "local_strength": local.get("strength"),
            "complementary_direction": complementary_direction,
            "complementary_strength": complementary.get("strength"),
        }
    return result


def final_output(row: dict[str, Any]) -> dict[str, Any] | None:
    output = row.get("effective_final_output")
    if output is None and isinstance(row.get("minimal_stop_policy"), dict):
        raw = row["minimal_stop_policy"].get("effective_output")
        if isinstance(raw, str):
            output = json.loads(raw)
    if output is None:
        output = row.get("final_output")
    return output if isinstance(output, dict) else None


def successful_calls(row: dict[str, Any]) -> list[str]:
    raw = row.get("tool_calls", [])
    return [tool for item in raw if (tool := canonical_tool(item)) is not None]


def call_status_by_step(row: dict[str, Any]) -> dict[int, str]:
    statuses: dict[int, str] = {}
    for index, step in enumerate(row.get("steps", []), start=1):
        explicit = step.get("call_status")
        if explicit:
            statuses[index] = explicit
        elif step.get("tool_observation") is not None:
            statuses[index] = "success"
        elif step.get("runtime_error"):
            statuses[index] = "over_budget"
    return statuses


def action_for_step(step: dict[str, Any]) -> dict[str, Any] | None:
    action = step.get("canonical_action")
    if action is None:
        action = step.get("actor_output")
    return action if isinstance(action, dict) else None


def observed_conflict_position(calls: list[str], frozen: dict[str, Any]) -> int | None:
    """Return the zero-based position when both opposing directional sources were observed."""
    if not frozen["frozen_tool_conflict"]:
        return None
    try:
        return max(calls.index("local_texture_analyzer"),
                   calls.index("complementary_forensic_analyzer"))
    except ValueError:
        return None


def sources_at_stop(output: dict[str, Any] | None) -> list[str]:
    if output is None:
        return []
    sources = []
    for item in output.get("current_evidence", []):
        if isinstance(item, dict) and isinstance(item.get("source"), str):
            source = canonical_tool(item["source"]) or item["source"]
            if source in EVIDENCE_TYPES and source not in sources:
                sources.append(source)
    return sources


def confusion_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row["effective_valid"]]
    real_rows = [row for row in valid if row["gt"] == "real"]
    fake_rows = [row for row in valid if row["gt"] == "fake"]
    correct = sum(row["prediction"] == row["gt"] for row in valid)
    correct_all = sum(row["effective_valid"] and row["prediction"] == row["gt"] for row in rows)
    real_recall = (
        sum(row["prediction"] == "real" for row in real_rows) / len(real_rows)
        if real_rows else None
    )
    fake_recall = (
        sum(row["prediction"] == "fake" for row in fake_rows) / len(fake_rows)
        if fake_rows else None
    )
    return {
        "n": len(rows),
        "raw_final_parse_success": sum(row["raw_valid"] for row in rows),
        "final_parse_success_after_minimal_policy": sum(row["effective_valid"] for row in rows),
        "invalid_trajectory_rate": (len(rows) - sum(row["effective_valid"] for row in rows)) / len(rows),
        "accuracy_all_samples_invalid_as_incorrect": correct_all / len(rows),
        "accuracy_valid_only": correct / len(valid) if valid else None,
        "specificity_for_fake_positive_real_negative": real_recall,
        "fake_recall": fake_recall,
        "balanced_accuracy_valid_only": (
            (real_recall + fake_recall) / 2
            if real_recall is not None and fake_recall is not None else None
        ),
    }


def condition_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row["effective_valid"]]
    one_tool_stop = [row for row in valid if len(row["calls"])]
    one_tool_stop = [row for row in one_tool_stop if len(row["calls"]) == 1]
    probe_only = [row for row in valid if row["calls"] == ["global_forensic_analyzer"]]
    conflict_rows = [row for row in rows if row["frozen_tool_conflict"]]
    observed_conflict = [row for row in conflict_rows if row["actor_observed_conflict"]]
    followed_up = [row for row in conflict_rows if row["conflict_followup"]]
    calls = [tool for row in rows for tool in row["calls"]]
    tool_counts = Counter(calls)
    first_tool_counts = Counter(row["calls"][0] if row["calls"] else "no_tool_call" for row in rows)
    audit = [row for row in rows if row["audit_sample"]]
    weak_conflict_audit = [row for row in audit if row["diagnostic_category"] in
                           ("TOOL_DISAGREEMENT", "WEAK_EVIDENCE")]

    def boolean_audit(rows_to_check: list[dict[str, Any]], field: str) -> dict[str, Any]:
        marked = [row["human_audit"][field] for row in rows_to_check
                  if isinstance(row.get("human_audit"), dict)
                  and isinstance(row["human_audit"].get(field), bool)]
        return {"positive": sum(marked), "reviewed": len(marked),
                "rate": sum(marked) / len(marked) if marked else None}

    def category_audit(field: str) -> dict[str, int]:
        return dict(Counter(row["human_audit"][field] for row in audit
                            if isinstance(row.get("human_audit"), dict)
                            and isinstance(row["human_audit"].get(field), str)
                            and row["human_audit"][field]))

    manual = {
        "premature_stop_weak_and_conflict_subset": boolean_audit(weak_conflict_audit, "premature_stop"),
        "evidence_sufficient": boolean_audit(audit, "evidence_sufficient"),
        "verdict_consistent": boolean_audit(audit, "verdict_consistent"),
        "unsupported_claim": boolean_audit(audit, "unsupported_claim"),
        "reasoning_faithful": boolean_audit(audit, "reasoning_faithful"),
        "tool_selection_quality_categories": category_audit("tool_selection_quality"),
        "conflict_handling_categories": category_audit("conflict_handling"),
        "stop_timing_categories": category_audit("stop_timing"),
    }
    evidence_counts = [len(row["independent_evidence_types_used"]) for row in valid]
    return {
        **confusion_summary(rows),
        "single_tool_stop": {"count": len(one_tool_stop), "denominator": len(valid),
                             "rate": len(one_tool_stop) / len(valid) if valid else None},
        "probe_only_stop": {"count": len(probe_only), "denominator": len(valid),
                            "rate": len(probe_only) / len(valid) if valid else None},
        "probe_first": {"count": sum(row["calls"][:1] == ["global_forensic_analyzer"] for row in rows),
                        "denominator": len(rows),
                        "among_samples_with_a_call_denominator": sum(bool(row["calls"]) for row in rows)},
        "probe_first_immediate_stop": {
            "count": sum(row["calls"][:1] == ["global_forensic_analyzer"] and row["is_stop"]
                         for row in rows),
            "denominator": sum(row["calls"][:1] == ["global_forensic_analyzer"] for row in rows),
        },
        "frozen_conflict_samples": len(conflict_rows),
        "actor_observed_conflict_samples": len(observed_conflict),
        "conflict_followup_rate_all_frozen_conflicts": {
            "count": len(followed_up), "denominator": len(conflict_rows),
            "rate": len(followed_up) / len(conflict_rows) if conflict_rows else None,
        },
        "conflict_followup_rate_conditional_on_observed_conflict": {
            "count": len(followed_up), "denominator": len(observed_conflict),
            "rate": len(followed_up) / len(observed_conflict) if observed_conflict else None,
        },
        "tool_calls": {tool: tool_counts.get(tool, 0) for tool in TOOLS},
        "tool_call_share": {tool: (tool_counts.get(tool, 0) / len(calls) if calls else None)
                            for tool in TOOLS},
        "first_tool_counts": {tool: first_tool_counts.get(tool, 0) for tool in (*TOOLS, "no_tool_call")},
        "first_tool_share": {tool: first_tool_counts.get(tool, 0) / len(rows) if rows else None
                             for tool in (*TOOLS, "no_tool_call")},
        "mean_successful_tool_calls_per_sample": len(calls) / len(rows) if rows else None,
        "delay_contract": {
            "blocked_first_probe_attempts": sum(row["blocked_probe_attempts"] for row in rows),
            "probe_unavailable_attempts": sum(row["unavailable_tool_attempts"] for row in rows),
        },
        "total_successful_tool_calls": len(calls),
        "mean_evidence_sources_at_stop": (
            sum(evidence_counts) / len(evidence_counts) if evidence_counts else None
        ),
        "median_evidence_sources_at_stop": median(evidence_counts) if evidence_counts else None,
        "evidence_source_count_distribution": {
            "one_source_rate": sum(count == 1 for count in evidence_counts) / len(evidence_counts)
            if evidence_counts else None,
            "two_sources_rate": sum(count == 2 for count in evidence_counts) / len(evidence_counts)
            if evidence_counts else None,
            "three_or_more_sources_rate": sum(count >= 3 for count in evidence_counts) / len(evidence_counts)
            if evidence_counts else None,
        },
        "redundancy": {
            "repeated_successful_calls": sum(row["redundant_successful_calls"] for row in rows),
            "successful_tool_calls": len(calls),
            "repeated_successful_call_rate": (
                sum(row["redundant_successful_calls"] for row in rows) / len(calls) if calls else None
            ),
            "duplicate_call_parser_rejections": sum(row["duplicate_call_parser_rejections"] for row in rows),
        },
        "human_audit": manual,
    }


def ensure_human_audit(path: Path, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if path.exists():
        old = read_jsonl(path)
        old_by_key = {(row["sample_id"], row["condition"]): row for row in old}
        if len(old_by_key) != len(old):
            raise ValueError("human audit file contains duplicate sample-condition rows")
    else:
        old_by_key = {}
    template = []
    for sample in samples:
        for condition in CONDITIONS:
            key = (sample["sample_id"], condition)
            previous = old_by_key.get(key, {})
            template.append({
                "sample_id": sample["sample_id"],
                "condition": condition,
                "diagnostic_category": sample["diagnostic_category"],
                "tool_selection_quality": previous.get("tool_selection_quality"),
                "conflict_handling": previous.get("conflict_handling"),
                "stop_timing": previous.get("stop_timing"),
                "evidence_sufficient": previous.get("evidence_sufficient"),
                "premature_stop": previous.get("premature_stop"),
                "premature_stop_reason": previous.get("premature_stop_reason", ""),
                "verdict_consistent": previous.get("verdict_consistent"),
                "unsupported_claim": previous.get("unsupported_claim"),
                "reasoning_faithful": previous.get("reasoning_faithful"),
                "notes": previous.get("notes", ""),
            })
    write_jsonl(path, template)
    return template


def evaluate(args: argparse.Namespace) -> None:
    manifest = read_jsonl(args.manifest)
    if len(manifest) != 60 or len({row["sample_id"] for row in manifest}) != 60:
        raise ValueError("B0-D evaluation requires exactly 60 unique diagnostic samples")
    ids = [row["sample_id"] for row in manifest]
    metadata = {row["sample_id"]: row for row in manifest}
    actor_inputs = read_jsonl(args.actor_manifest)
    if [row["sample_id"] for row in actor_inputs] != ids or any(
        set(row) != {"sample_id", "relative_path", "sha256"} for row in actor_inputs
    ):
        raise ValueError("actor input manifest must align and exclude all evaluation labels")
    actor_inputs_by_id = {row["sample_id"]: row for row in actor_inputs}
    conflicts = load_conflict_labels(args.tool_results)
    if set(conflicts) != set(ids):
        raise ValueError("cached frozen tool outputs do not align with diagnostic samples")

    audit_samples = read_jsonl(args.audit_samples)
    audit_ids = {row["sample_id"] for row in audit_samples}
    if len(audit_ids) < 20:
        raise ValueError("the preselected human audit set must contain at least 20 samples")
    audit_rows = ensure_human_audit(args.output_dir / "human_audit.jsonl", audit_samples)
    audit_by_key = {(row["sample_id"], row["condition"]): row for row in audit_rows}

    all_rows: dict[str, list[dict[str, Any]]] = {}
    per_sample_rows = []
    conflict_rows_out = []
    selection_rows = []
    audit_packet_rows = []
    for condition, input_path in args.condition_files.items():
        trajectories = read_jsonl(input_path)
        if len(trajectories) != 60 or [row["sample_id"] for row in trajectories] != ids:
            raise ValueError(f"{condition} does not match the diagnostic manifest order")
        result_rows = []
        for trajectory in trajectories:
            sample_id = trajectory["sample_id"]
            sample = metadata[sample_id]
            frozen = conflicts[sample_id]
            calls = successful_calls(trajectory)
            final = final_output(trajectory)
            effective_valid = bool(trajectory.get("effective_parse_valid", final is not None))
            raw_valid = bool(trajectory.get("raw_parse_valid", trajectory.get("parse_valid", False)))
            prediction = trajectory.get("effective_final_verdict")
            if prediction is None and final is not None:
                prediction = final.get("final_verdict")
            stop = bool(final and final.get("next_action") == "STOP")
            cited = sources_at_stop(final)
            called_set = set(calls)
            actually_available_citations = [source for source in cited
                                            if source == "visual" or source in called_set]
            evidence_types = sorted({EVIDENCE_TYPES[source] for source in actually_available_citations})
            conflict_position = observed_conflict_position(calls, frozen)
            followup = bool(
                conflict_position is not None
                and any(tool not in ("local_texture_analyzer", "complementary_forensic_analyzer")
                        for tool in calls[conflict_position + 1:])
            )
            statuses = call_status_by_step(trajectory)
            duplicate_rejections = sum(
                "already been called" in str(step.get("parse_error", ""))
                for step in trajectory.get("steps", [])
            )
            repeated_calls = sum(count - 1 for count in Counter(calls).values() if count > 1)
            human = audit_by_key.get((sample_id, condition))
            item = {
                "sample_id": sample_id,
                "condition": condition,
                "gt": sample["gt"],
                "diagnostic_category": sample["diagnostic_category"],
                "effective_valid": effective_valid,
                "raw_valid": raw_valid,
                "prediction": prediction,
                "correct": bool(effective_valid and prediction == sample["gt"]),
                "is_stop": stop,
                "calls": calls,
                "frozen_tool_conflict": frozen["frozen_tool_conflict"],
                "local_direction": frozen["local_direction"],
                "local_strength": frozen["local_strength"],
                "complementary_direction": frozen["complementary_direction"],
                "complementary_strength": frozen["complementary_strength"],
                "actor_observed_conflict": conflict_position is not None,
                "conflict_followup": followup,
                "tools_cited_at_stop": cited,
                "independent_evidence_types_used": evidence_types,
                "evidence_type_count": len(evidence_types),
                "redundant_successful_calls": repeated_calls,
                "duplicate_call_parser_rejections": duplicate_rejections,
                "blocked_probe_attempts": int(trajectory.get("blocked_probe_attempts", 0)),
                "unavailable_tool_attempts": int(trajectory.get("unavailable_tool_attempts", 0)),
                "audit_sample": sample_id in audit_ids,
                "human_audit": human,
            }
            result_rows.append(item)
            if sample_id in audit_ids:
                actor_input = actor_inputs_by_id[sample_id]
                audit_packet_rows.append({
                    "sample_id": sample_id,
                    "condition": condition,
                    "diagnostic_category": sample["diagnostic_category"],
                    "image_relative_path": actor_input["relative_path"],
                    "image_sha256": actor_input["sha256"],
                    "tool_calls": calls,
                    "raw_final_output": trajectory.get("raw_final_output", trajectory.get("final_output")),
                    "effective_final_output": final,
                    "steps": trajectory.get("steps", []),
                })
            per_sample_rows.append({
                "sample_id": sample_id,
                "condition": condition,
                "diagnostic_category": sample["diagnostic_category"],
                "ground_truth": sample["gt"],
                "final_verdict": prediction,
                "raw_final_parse_valid": raw_valid,
                "effective_final_parse_valid": effective_valid,
                "correct": item["correct"],
                "tool_sequence": ">".join(calls),
                "num_successful_tool_calls": len(calls),
                "single_tool_stop": stop and len(calls) == 1,
                "probe_only_stop": stop and calls == ["global_forensic_analyzer"],
                "frozen_tool_conflict": frozen["frozen_tool_conflict"],
                "actor_observed_conflict": item["actor_observed_conflict"],
                "conflict_followup": followup,
                "tools_cited_at_stop": ";".join(cited),
                "independent_evidence_types_used": ";".join(evidence_types),
                "evidence_type_count": len(evidence_types),
                "seconds": trajectory.get("seconds"),
                "audit_sample": sample_id in audit_ids,
            })
            conflict_rows_out.append({
                "sample_id": sample_id,
                "condition": condition,
                "diagnostic_category": sample["diagnostic_category"],
                "frozen_tool_conflict": frozen["frozen_tool_conflict"],
                "local_direction": frozen["local_direction"],
                "local_strength": frozen["local_strength"],
                "complementary_direction": frozen["complementary_direction"],
                "complementary_strength": frozen["complementary_strength"],
                "tool_sequence": ">".join(calls),
                "actor_observed_conflict": item["actor_observed_conflict"],
                "conflict_followup": followup,
                "followup_tool": next((tool for tool in calls[(conflict_position + 1):]
                                       if tool not in ("local_texture_analyzer",
                                                       "complementary_forensic_analyzer")), "")
                                 if conflict_position is not None else "",
                "manual_premature_stop": (
                    human.get("premature_stop") if human is not None else None
                ),
                "manual_premature_stop_reason": (
                    human.get("premature_stop_reason", "") if human is not None else ""
                ),
            })

            prior_successful: list[str] = []
            for step_number, step in enumerate(trajectory.get("steps", []), start=1):
                generated_attempts = step.get("attempts", [])
                raw_actions = []
                for attempt_index, generated in enumerate(generated_attempts):
                    try:
                        raw_action = extract_object(generated.get("raw", ""))
                    except (ValueError, TypeError, json.JSONDecodeError):
                        continue
                    if raw_action.get("next_action") == "CALL_TOOL":
                        raw_actions.append((attempt_index, raw_action))
                if not raw_actions:
                    action = action_for_step(step)
                    if action and action.get("next_action") == "CALL_TOOL":
                        raw_actions = [(None, action)]
                for attempt_index, action in raw_actions:
                    selected_visible = action.get("selected_tool")
                    selected = canonical_tool(selected_visible)
                    status = statuses.get(step_number, "rejected_by_parser_or_condition")
                    if attempt_index is not None and attempt_index < len(generated_attempts) - 1:
                        status = "format_retry"
                    evidence_sources = sorted({
                        (canonical_tool(e.get("source")) or e.get("source"))
                        for e in action.get("current_evidence", [])
                        if isinstance(e, dict) and isinstance(e.get("source"), str)
                    })
                    selection_rows.append({
                        "sample_id": sample_id,
                        "condition": condition,
                        "diagnostic_category": sample["diagnostic_category"],
                        "step": step_number,
                        "raw_attempt": attempt_index,
                        "selected_tool": selected or selected_visible,
                        "call_status": status,
                        "previously_successful_tools": ";".join(prior_successful),
                        "current_evidence_sources": ";".join(evidence_sources),
                        "evidence_gap": action.get("evidence_gap", ""),
                        "action_reason": action.get("action_reason", ""),
                        "review_label": "",
                        "review_notes": "",
                    })
                action = action_for_step(step)
                if action and action.get("next_action") == "CALL_TOOL":
                    selected = canonical_tool(action.get("selected_tool"))
                    if selected and statuses.get(step_number) == "success":
                        prior_successful.append(selected)
        all_rows[condition] = result_rows

    args.output_dir.mkdir(parents=True, exist_ok=True)
    preserve_call_reviews(args.output_dir / "tool_selection_audit.csv", selection_rows)
    write_csv(args.output_dir / "per_sample.csv", per_sample_rows)
    write_csv(args.output_dir / "conflict_analysis.csv", conflict_rows_out)
    write_csv(args.output_dir / "tool_selection_audit.csv", selection_rows)
    write_jsonl(args.output_dir / "audit_packet.jsonl", audit_packet_rows)

    condition_summaries = {condition: condition_metrics(rows) for condition, rows in all_rows.items()}
    full_summary = condition_summaries["FULL"]
    condition_deltas = {}
    for condition, summary in condition_summaries.items():
        if condition == "FULL":
            continue
        call_share_deltas = {
            tool: summary["tool_call_share"][tool] - full_summary["tool_call_share"][tool]
            for tool in TOOLS
            if summary["tool_call_share"][tool] is not None
            and full_summary["tool_call_share"][tool] is not None
        }
        first_share_deltas = {
            tool: summary["first_tool_share"][tool] - full_summary["first_tool_share"][tool]
            for tool in (*TOOLS, "no_tool_call")
        }
        condition_deltas[condition] = {
            "accuracy_all_samples_delta_vs_full": (
                summary["accuracy_all_samples_invalid_as_incorrect"]
                - full_summary["accuracy_all_samples_invalid_as_incorrect"]
            ),
            "final_parse_success_delta_vs_full": (
                summary["final_parse_success_after_minimal_policy"]
                - full_summary["final_parse_success_after_minimal_policy"]
            ),
            "mean_evidence_sources_delta_vs_full": (
                summary["mean_evidence_sources_at_stop"]
                - full_summary["mean_evidence_sources_at_stop"]
                if summary["mean_evidence_sources_at_stop"] is not None
                and full_summary["mean_evidence_sources_at_stop"] is not None else None
            ),
            "tool_call_share_delta_vs_full": call_share_deltas,
            "max_absolute_tool_call_share_shift": max(map(abs, call_share_deltas.values()), default=None),
            "first_tool_share_delta_vs_full": first_share_deltas,
            "max_absolute_first_tool_share_shift": max(map(abs, first_share_deltas.values()), default=None),
        }
    metrics = {
        "conditions": condition_summaries,
        "condition_deltas_vs_full": condition_deltas,
        "paired_conditions": {
            "sample_count": len(ids),
            "source_group_count": len({sample["source_group"] for sample in manifest}),
            "same_order_verified": True,
            "human_audit_images": len(audit_ids),
            "human_audit_rows": len(audit_rows),
            "human_audit_completed_rows": sum(
                all(row.get(field) not in (None, "") for field in (
                    "tool_selection_quality", "conflict_handling", "stop_timing",
                    "evidence_sufficient", "premature_stop", "verdict_consistent",
                    "unsupported_claim", "reasoning_faithful",
                ))
                for row in audit_rows
            ),
            "tool_selection_calls_requiring_manual_review": len(selection_rows),
            "tool_selection_manual_ratings_completed": sum(bool(row["review_label"]) for row in selection_rows),
        },
        "definitions": {
            "conflict": "Frozen local_texture and complementary_forensic outputs map to opposing real/fake directions; no Actor verdict is used.",
            "conflict_followup": "After both opposing directional sources have been observed, a later distinct tool is called.",
            "evidence_sources_at_stop": "Distinct sources cited in final current_evidence, restricted to sources actually called (visual is available from the original image).",
            "specificity": "Real recall when fake is treated as the positive class.",
            "accuracy": "Invalid trajectories count as incorrect in accuracy_all_samples_invalid_as_incorrect.",
            "manual_metrics": "Premature STOP, verdict consistency, unsupported claims, and reasoning faithfulness require completed human audit rows; unreviewed values remain missing.",
        },
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "sample_count": len(ids),
        "condition_counts": {name: len(rows) for name, rows in all_rows.items()},
        "audit_rows": len(audit_rows),
        "call_audit_rows": len(selection_rows),
        "metrics_path": str(args.output_dir / "metrics.json"),
        "decision": "not assigned until the human audit and gate review are complete",
    }, ensure_ascii=False, indent=2))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def preserve_call_reviews(path: Path, rows: list[dict[str, Any]]) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        previous = list(csv.DictReader(stream))
    old_by_key = {
        (row.get("sample_id"), row.get("condition"), row.get("step"), row.get("raw_attempt")): row
        for row in previous
    }
    for row in rows:
        key = (row["sample_id"], row["condition"], str(row["step"]), str(row["raw_attempt"]))
        old = old_by_key.get(key)
        if old:
            row["review_label"] = old.get("review_label", "")
            row["review_notes"] = old.get("review_notes", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/data/diagnostic_manifest.jsonl")
    parser.add_argument("--tool-results", type=Path,
                        default=ROOT / "experiments/actor_b/heldout_confirmation/input/heldout_tool_results.jsonl")
    parser.add_argument("--audit-samples", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/data/manual_audit_samples.jsonl")
    parser.add_argument("--actor-manifest", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/data/actor_input_manifest.jsonl")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/evaluation")
    parser.add_argument("--full", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/full/trajectories.jsonl")
    parser.add_argument("--probe-mask", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/probe_mask/trajectories.jsonl")
    parser.add_argument("--probe-delay", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/probe_delay/trajectories.jsonl")
    parser.add_argument("--tool-rename", type=Path,
                        default=ROOT / "experiments/actor_b/actor_b0_d/tool_rename/trajectories.jsonl")
    args = parser.parse_args()
    args.condition_files = {
        "FULL": args.full,
        "PROBE-MASK": args.probe_mask,
        "PROBE-DELAY": args.probe_delay,
        "TOOL-RENAME": args.tool_rename,
    }
    evaluate(args)


if __name__ == "__main__":
    main()
