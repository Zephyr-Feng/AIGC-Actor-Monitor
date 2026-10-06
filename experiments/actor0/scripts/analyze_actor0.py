#!/usr/bin/env python3
"""Compute Actor-0 final and tool-use diagnostics without changing the frozen run."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import statistics
from collections import Counter
from pathlib import Path


TOOLS = [
    "global_forensic_analyzer", "local_texture_analyzer",
    "complementary_forensic_analyzer", "provenance_inspector",
]
SHORT = {
    "global_forensic_analyzer": "GLOBAL", "local_texture_analyzer": "LOCAL",
    "complementary_forensic_analyzer": "COMPLEMENTARY", "provenance_inspector": "PROVENANCE",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def label_direction(signal: str | None) -> str | None:
    if signal in ("real", "real_like"):
        return "real"
    if signal in ("fake", "synthetic_like"):
        return "fake"
    return None


def verdict(record: dict) -> str | None:
    value = record.get("final_verdict")
    if value in ("real", "fake"):
        return value
    parsed = record.get("parsed_output")
    if isinstance(parsed, dict) and parsed.get("final_verdict") in ("real", "fake"):
        return parsed["final_verdict"]
    final = record.get("final_output")
    if isinstance(final, dict) and final.get("final_verdict") in ("real", "fake"):
        return final["final_verdict"]
    return None


def final_metrics(records: list[dict], labels: dict[str, str], generators: dict[str, str]) -> dict:
    def calc(sample_ids: list[str]) -> dict:
        total = len(sample_ids)
        real = [sample_id for sample_id in sample_ids if labels[sample_id] == "real"]
        fake = [sample_id for sample_id in sample_ids if labels[sample_id] == "fake"]
        by_id = {row["sample_id"]: row for row in records}
        correct = sum(verdict(by_id[sid]) == labels[sid] for sid in sample_ids)
        true_real = sum(verdict(by_id[sid]) == "real" for sid in real)
        true_fake = sum(verdict(by_id[sid]) == "fake" for sid in fake)
        specificity = true_real / len(real) if real else None
        fake_recall = true_fake / len(fake) if fake else None
        balanced = (specificity + fake_recall) / 2 if specificity is not None and fake_recall is not None else None
        invalid = sum(verdict(by_id[sid]) is None for sid in sample_ids)
        return {
            "n": total, "n_real": len(real), "n_fake": len(fake),
            "accuracy": correct / total if total else None,
            "balanced_accuracy": balanced,
            "specificity": specificity,
            "fake_recall": fake_recall,
            "invalid_or_unparsed": invalid,
            "correct": correct,
        }

    all_ids = sorted(labels)
    result = {"overall": calc(all_ids)}
    for generator in ("flux", "sd3_5"):
        selected = [sid for sid in all_ids if labels[sid] == "real" or generators[sid] == generator]
        result[f"raise_vs_{generator}"] = calc(selected)
    return result


def observed_tools(record: dict) -> dict[str, dict]:
    if record.get("condition") == "forced_all":
        return {item["tool"]: item for item in record.get("tool_observations", [])}
    observed = {}
    for step in record.get("steps", []):
        item = step.get("tool_observation")
        if isinstance(item, dict) and item.get("tool") in TOOLS:
            observed[item["tool"]] = item
    return observed


def calls(record: dict) -> list[str]:
    result = []
    for step in record.get("steps", []):
        action = step.get("action", "")
        matched = re.fullmatch(r"CALL\(([^)]+)\)", action)
        if matched and matched.group(1) in TOOLS and matched.group(1) not in result:
            result.append(matched.group(1))
    return result


def direction_map(record: dict) -> dict[str, str]:
    return {name: direction for name, item in observed_tools(record).items()
            if (direction := label_direction(item.get("signal"))) is not None}


def has_conflict(record: dict) -> bool:
    return len(set(direction_map(record).values())) > 1


def first_conflict_action(record: dict) -> str | None:
    seen: dict[str, str] = {}
    steps = record.get("steps", [])
    for index, step in enumerate(steps):
        observation = step.get("tool_observation")
        if isinstance(observation, dict) and observation.get("tool") in TOOLS:
            direction = label_direction(observation.get("signal"))
            if direction:
                seen[observation["tool"]] = direction
        if len(set(seen.values())) > 1:
            for later in steps[index + 1:]:
                if later.get("action") and later.get("action") != "INVALID":
                    return later["action"]
            return "FORCED_STOP" if record.get("forced_termination") else None
    return None


def narrative(record: dict) -> list[str]:
    texts: list[str] = []
    for step in record.get("steps", []):
        output = step.get("actor_output")
        if not isinstance(output, dict):
            continue
        texts.extend(x for x in output.get("evidence_summary", []) if isinstance(x, str))
        texts.extend(x for x in output.get("unresolved_conflicts", []) if isinstance(x, str))
    final = record.get("final_output")
    if isinstance(final, dict):
        for field in ("supporting_evidence", "contradictory_evidence", "remaining_uncertainty", "stop_reason"):
            value = final.get(field)
            if isinstance(value, list):
                texts.extend(x for x in value if isinstance(x, str))
            elif isinstance(value, str):
                texts.append(value)
    return texts


FAKE_SUPPORT = re.compile(r"(?:支持|证明|说明|表明|指向|倾向)(?:了|为|是)?[^。；;]{0,12}(?:fake|假图|合成|AI.?生成|伪造)|(?:fake|假图|合成|AI.?生成|伪造)[^。；;]{0,12}(?:证据|倾向|来源)", re.I)
REAL_SUPPORT = re.compile(r"(?:支持|证明|说明|表明|指向|倾向)(?:了|为|是)?[^。；;]{0,12}(?:real|真实|拍摄|自然图像)|(?:real|真实|拍摄)[^。；;]{0,12}(?:证据|倾向|来源)", re.I)
META_TERMS = re.compile(r"元数据|C2PA|来源信息|来源凭据|provenance_inspector", re.I)
NEGATION = re.compile(r"不支持|不能|不可|不应|不说明|不代表|不能说明|未能证明|并非|不是|不足以|无法据此|不是证据|不构成", re.I)


def interpretation_audit(record: dict) -> tuple[int, list[str]]:
    observed = observed_tools(record)
    texts = narrative(record)
    checked, errors = 0, []
    for tool, item in observed.items():
        expected = item.get("signal")
        expected_dir = label_direction(expected)
        for text in texts:
            if tool.casefold() not in text.casefold():
                continue
            signal_match = re.search(r"signal\s*=\s*(real_like|synthetic_like|real|fake|inconclusive)", text, re.I)
            explicit_signal = signal_match.group(1).lower() if signal_match else None
            mentions_tool = tool.casefold() in text.casefold()
            checked += 1
            explicit_dir = label_direction(explicit_signal)
            mismatch = explicit_signal is not None and explicit_signal != expected
            if expected_dir == "real" and FAKE_SUPPORT.search(text) and not NEGATION.search(text):
                mismatch = True
            if expected_dir == "fake" and REAL_SUPPORT.search(text) and not NEGATION.search(text):
                mismatch = True
            if expected == "inconclusive" and expected_dir is None and FAKE_SUPPORT.search(text) and not NEGATION.search(text):
                mismatch = True
            if mismatch:
                errors.append(tool)
    return checked, sorted(set(errors))


def metadata_misuse(record: dict) -> bool:
    observations = observed_tools(record)
    if observations.get("provenance_inspector", {}).get("signal") != "inconclusive":
        return False
    for text in narrative(record):
        if META_TERMS.search(text) and FAKE_SUPPORT.search(text) and not NEGATION.search(text):
            return True
    return False


def all_strong_consistent(record: dict) -> bool:
    directions = []
    for item in observed_tools(record).values():
        direction = label_direction(item.get("signal"))
        if direction and item.get("strength") == "high":
            directions.append(direction)
    return len(directions) >= 2 and len(set(directions)) == 1 and not has_conflict(record)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--image-only", type=Path, required=True)
    parser.add_argument("--forced-all", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "analysis")
    parser.add_argument("--qualitative-n", type=int, default=50)
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    labels = {row["sample_id"]: row["label"] for row in manifest}
    generators = {row["sample_id"]: row["generator"] for row in manifest}
    if len(labels) != len(manifest) or len(manifest) != 300:
        raise ValueError("evaluation manifest must have 300 unique images")
    tool_rows = {row["sample_id"]: row for row in read_jsonl(args.tool_results)}
    image_only = {row["sample_id"]: row for row in read_jsonl(args.image_only)}
    forced_all = {row["sample_id"]: row for row in read_jsonl(args.forced_all)}
    actor = {row["sample_id"]: row for row in read_jsonl(args.actor)}
    expected = set(labels)
    for name, rows in (("tool output", tool_rows), ("image-only", image_only), ("forced-all", forced_all), ("Actor-0", actor)):
        if set(rows) != expected:
            raise ValueError(f"{name} records do not match frozen evaluation IDs (missing={len(expected-set(rows))}, extra={len(set(rows)-expected)})")

    probe_records = []
    for sample_id, record in tool_rows.items():
        global_tool = next(item for item in record["tools"] if item["tool"] == "global_forensic_analyzer")
        probe_records.append({"sample_id": sample_id, "final_verdict": label_direction(global_tool["signal"])})
    image_records = list(image_only.values())
    all_records = list(forced_all.values())
    actor_records = list(actor.values())
    systems = {
        "B0_image_only": image_records, "B1_PROBE_only": probe_records,
        "B2_forced_all_tools": all_records, "B3_actor0_autonomous": actor_records,
    }
    metrics = {
        "evaluation_manifest_count": len(manifest),
        "systems": {name: final_metrics(rows, labels, generators) for name, rows in systems.items()},
        "metric_definition": "Invalid or unparsed final outputs count as incorrect for accuracy; class recall denominators include all examples of that class.",
        "source_group_count": len({row["source_group"] for row in manifest}),
        "evaluation_manifest_sha256": __import__("hashlib").sha256(args.manifest.read_bytes()).hexdigest(),
    }
    write_json(args.output_dir / "final_metrics.json", metrics)

    actor_by_id = actor
    actor_calls = {sid: calls(row) for sid, row in actor_by_id.items()}
    actor_n = len(actor_by_id)
    total_steps = sum(len(row.get("steps", [])) for row in actor_records)
    invalid_tool_actions = sum(
        bool(step.get("invalid_action")) or bool(step.get("invalid_tool_request"))
        for row in actor_records for step in row.get("steps", [])
    )
    malformed = sum(
        bool(step.get("parse_error")) for row in actor_records for step in row.get("steps", [])
    )
    call_requests = sum(
        str(step.get("action", "")).startswith("CALL(") or bool(step.get("invalid_tool_request"))
        for row in actor_records for step in row.get("steps", [])
    )
    call_counts = [len(actor_calls[sid]) for sid in actor_calls]
    usage = {
        "n": actor_n,
        "average_tool_calls": statistics.mean(call_counts) if call_counts else 0.0,
        "median_tool_calls": statistics.median(call_counts) if call_counts else 0.0,
        "zero_tool_stop_rate": sum(len(count) == 0 and not actor_by_id[sid].get("forced_termination") for sid, count in actor_calls.items()) / actor_n,
        "one_tool_stop_rate": sum(len(count) == 1 and not actor_by_id[sid].get("forced_termination") for sid, count in actor_calls.items()) / actor_n,
        "all_tools_call_rate": sum(count == 4 for count in call_counts) / actor_n,
        "forced_termination_rate": sum(bool(row.get("forced_termination")) for row in actor_records) / actor_n,
        "invalid_tool_call_count": invalid_tool_actions,
        "invalid_tool_call_rate": invalid_tool_actions / max(call_requests, 1),
        "malformed_actor_output_count": malformed,
        "malformed_actor_output_rate": malformed / max(total_steps, 1),
        "actor_step_schema_parse_rate": 1.0 - malformed / max(total_steps, 1),
        "tool_call_rates": {name: sum(name in actor_calls[sid] for sid in actor_calls) / actor_n for name in TOOLS},
        "global_only_stop_rate": sum(actor_calls[sid] == [TOOLS[0]] and not actor_by_id[sid].get("forced_termination") for sid in actor_calls) / actor_n,
        "definition": "Call rates use all evaluation images as denominator; invalid_tool_call_rate is invalid/redundant tool requests divided by parsed valid or invalid tool requests.",
    }
    high_stop_den, high_stop_num, low_continue_den, low_continue_num = 0, 0, 0, 0
    sequences = Counter()
    conflict_rows, monitor_rows, probe_failure_rows = [], [], []
    checked_interpretations = interpretation_errors = 0
    misuse_ids = set()
    for sid, record in actor_by_id.items():
        tool_calls = actor_calls[sid]
        final = record.get("final_output") or {}
        end_action = "FORCED_STOP" if record.get("forced_termination") else "STOP"
        sequence = " -> ".join([SHORT[name] for name in tool_calls] + [end_action])
        sequences[sequence] += 1
        observed = observed_tools(record)
        conflict = has_conflict(record)
        next_after_conflict = first_conflict_action(record) if conflict else None
        continued = bool(next_after_conflict and str(next_after_conflict).startswith("CALL("))
        unresolved = bool(final.get("unresolved_conflicts")) if isinstance(final.get("unresolved_conflicts"), list) else False
        checked, errors = interpretation_audit(record)
        checked_interpretations += checked
        interpretation_errors += len(errors)
        misuse = metadata_misuse(record)
        if misuse:
            misuse_ids.add(sid)
        global_observation = observed.get(TOOLS[0])
        if global_observation:
            strength_value = global_observation.get("strength")
            global_step_index = next((i for i, step in enumerate(record.get("steps", []))
                                      if step.get("tool_observation", {}).get("tool") == TOOLS[0]), None)
            next_action = None
            if global_step_index is not None:
                for later in record.get("steps", [])[global_step_index + 1:]:
                    if later.get("action") and later.get("action") != "INVALID":
                        next_action = later.get("action")
                        break
            if strength_value == "high":
                high_stop_den += 1
                high_stop_num += next_action == "STOP"
            elif strength_value in ("moderate", "low"):
                low_continue_den += 1
                low_continue_num += bool(next_action and str(next_action).startswith("CALL("))
        candidate = {
            "sample_id": sid,
            "final_correct": int(bool(record.get("final_correct"))),
            "num_tools": len(tool_calls),
            "single_evidence_stop": int(len(tool_calls) == 1 and not record.get("forced_termination")),
            "conflict_stop": int(conflict and unresolved),
            "tool_misinterpretation": int(bool(errors)),
            "potential_oversearch": int(len(tool_calls) == 4 and all_strong_consistent(record)),
            "potential_premature_stop": int(
                not record.get("final_correct") and any(name not in tool_calls for name in
                    ("local_texture_analyzer", "complementary_forensic_analyzer"))
            ),
            "global_wrong": 0,
            "global_wrong_recovered": 0,
        }
        probe = next(item for item in tool_rows[sid]["tools"] if item["tool"] == TOOLS[0])
        probe_wrong = label_direction(probe["signal"]) != labels[sid]
        candidate["global_wrong"] = int(probe_wrong)
        candidate["global_wrong_recovered"] = int(probe_wrong and bool(record.get("final_correct")))
        monitor_rows.append(candidate)
        conflict_rows.append({
            "sample_id": sid, "has_conflict": int(conflict),
            "conflicting_signals": " | ".join(f"{tool}={item['signal']}" for tool, item in observed.items()
                                                  if label_direction(item.get("signal")) is not None),
            "continue_after_conflict": int(continued), "next_action_after_first_conflict": next_after_conflict or "",
            "stop_with_unresolved_conflict": int(bool(conflict and unresolved)),
            "actor_acknowledged_conflict": int(unresolved), "num_tools": len(tool_calls),
            "tool_calls": " | ".join(tool_calls), "final_verdict": verdict(record) or "",
            "ground_truth": labels[sid], "final_correct": int(bool(record.get("final_correct"))),
        })
        if probe_wrong:
            probe_failure_rows.append({
                "sample_id": sid, "ground_truth": labels[sid], "probe_signal": probe["signal"],
                "probe_score": probe["score"], "probe_strength": probe["strength"],
                "actor_tool_calls": " | ".join(tool_calls),
                "additional_tools_after_global": " | ".join(name for name in tool_calls if name != TOOLS[0]),
                "actor_final_verdict": verdict(record) or "", "actor_correct": int(bool(record.get("final_correct"))),
                "recovered_by_additional_tools": int(bool(record.get("final_correct")) and any(name != TOOLS[0] for name in tool_calls)),
                "stopped_early_after_global": int(tool_calls == [TOOLS[0]] and not record.get("forced_termination")),
                "global_signal_echoed_as_support": int(TOOLS[0] in " ".join(narrative(record)) and label_direction(probe["signal"]) != labels[sid]),
            })

    conflict_n = sum(row["has_conflict"] for row in conflict_rows)
    inconclusive_provenance_calls = sum(
        observed_tools(row).get("provenance_inspector", {}).get("signal") == "inconclusive"
        for row in actor_records
    )
    usage.update({
        "high_strength_global_observations": high_stop_den,
        "p_stop_after_global_given_high_strength": high_stop_num / high_stop_den if high_stop_den else None,
        "moderate_or_low_strength_global_observations": low_continue_den,
        "p_continue_after_global_given_moderate_or_low_strength": low_continue_num / low_continue_den if low_continue_den else None,
        "conflict_cases": conflict_n,
        "continue_after_conflict_rate": sum(row["continue_after_conflict"] for row in conflict_rows) / conflict_n if conflict_n else None,
        "stop_with_unresolved_conflict_rate": sum(row["stop_with_unresolved_conflict"] for row in conflict_rows) / conflict_n if conflict_n else None,
        "tool_interpretation_error_count": sum(row["tool_misinterpretation"] for row in monitor_rows),
        "tool_interpretation_checked_mentions": checked_interpretations,
        "tool_interpretation_error_rate": interpretation_errors / checked_interpretations if checked_interpretations else None,
        "metadata_absence_misuse_count": len(misuse_ids),
        "metadata_absence_inconclusive_cases": inconclusive_provenance_calls,
        "metadata_absence_misuse_rate": len(misuse_ids) / inconclusive_provenance_calls if inconclusive_provenance_calls else None,
        "potential_oversearch_count": sum(row["potential_oversearch"] for row in monitor_rows),
        "single_evidence_stop_count": sum(row["single_evidence_stop"] for row in monitor_rows),
        "conflict_stop_count": sum(row["conflict_stop"] for row in monitor_rows),
        "potential_premature_stop_count": sum(row["potential_premature_stop"] for row in monitor_rows),
        "global_wrong_actor_correct": sum(bool(row.get("actor_correct")) for row in probe_failure_rows),
        "global_wrong_actor_wrong": sum(not bool(row.get("actor_correct")) for row in probe_failure_rows),
        "global_wrong_recovered_by_additional_tools": sum(bool(row.get("recovered_by_additional_tools")) for row in probe_failure_rows),
        "global_wrong_stopped_early": sum(bool(row.get("stopped_early_after_global")) for row in probe_failure_rows),
    })
    write_json(args.output_dir / "tool_usage_metrics.json", usage)
    write_csv(args.output_dir / "tool_sequences.csv", [
        {"rank": index, "sequence": sequence, "count": count, "rate": count / actor_n}
        for index, (sequence, count) in enumerate(sequences.most_common(20), 1)
    ], ["rank", "sequence", "count", "rate"])
    write_csv(args.output_dir / "conflict_analysis.csv", conflict_rows)
    write_csv(args.output_dir / "probe_failure_analysis.csv", probe_failure_rows)
    write_csv(args.output_dir / "monitor_candidate_cases.csv", monitor_rows, [
        "sample_id", "final_correct", "num_tools", "single_evidence_stop", "conflict_stop",
        "tool_misinterpretation", "potential_oversearch", "potential_premature_stop",
        "global_wrong", "global_wrong_recovered",
    ])

    qualitative_n = min(args.qualitative_n, actor_n)
    rng = random.Random(20261002)
    records_by_id = actor_by_id
    categories = [
        ("wrong_cases", [sid for sid in expected if not records_by_id[sid].get("final_correct")], 10),
        ("conflict_cases", [row["sample_id"] for row in conflict_rows if row["has_conflict"]], 10),
        ("single_tool_stop", [sid for sid in expected if len(actor_calls[sid]) == 1 and not records_by_id[sid].get("forced_termination")], 6),
        ("all_tool_cases", [sid for sid in expected if len(actor_calls[sid]) == 4], 6),
        ("global_tool_failure", [row["sample_id"] for row in probe_failure_rows], 10),
        ("correct_easy_cases", [sid for sid in expected if records_by_id[sid].get("final_correct") and not has_conflict(records_by_id[sid])], 12),
    ]
    selected: dict[str, list[str]] = {}
    for category, candidates, quota in categories:
        pool = [sid for sid in sorted(candidates) if sid not in selected]
        rng.shuffle(pool)
        for sid in pool[:quota]:
            selected.setdefault(sid, []).append(category)
    if len(selected) < qualitative_n:
        remaining = sorted(sid for sid in expected if sid not in selected)
        rng.shuffle(remaining)
        for sid in remaining[:qualitative_n - len(selected)]:
            selected[sid] = ["fixed_seed_fill"]
    audit_rows = []
    for sid, reasons in list(selected.items())[:qualitative_n]:
        row = records_by_id[sid]
        audit_rows.append({
            "sample_id": sid, "selection_strata": " | ".join(reasons),
            "ground_truth": labels[sid], "actor_verdict": verdict(row) or "",
            "final_correct": int(bool(row.get("final_correct"))), "num_tools": len(actor_calls[sid]),
            "tool_calls": " | ".join(actor_calls[sid]), "has_conflict": int(has_conflict(row)),
            "probe_wrong": int(label_direction(next(item for item in tool_rows[sid]["tools"] if item["tool"] == TOOLS[0])["signal"]) != labels[sid]),
            "tool_selection_reasonable": "pending_manual_review",
            "evidence_summary_faithful": "pending_manual_review",
            "evidence_gap_valid": "pending_manual_review",
            "conflict_recognized": "pending_manual_review",
            "stop_reason_consistent": "pending_manual_review",
            "review_status": "pending_manual_review",
        })
    write_csv(args.output_dir / "qualitative_audit.csv", audit_rows)

    per_system_rows = []
    for name, rows in systems.items():
        for sample in rows:
            per_system_rows.append({
                "system": name, "sample_id": sample["sample_id"], "ground_truth": labels[sample["sample_id"]],
                "generator": generators[sample["sample_id"]], "final_verdict": verdict(sample) or "",
                "correct": int(verdict(sample) == labels[sample["sample_id"]]),
                "parse_error": sample.get("parse_error", ""),
            })
    write_csv(args.output_dir / "system_predictions.csv", per_system_rows)
    print(json.dumps({"final_metrics": metrics["systems"], "tool_usage": usage,
                      "qualitative_cases": len(audit_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
