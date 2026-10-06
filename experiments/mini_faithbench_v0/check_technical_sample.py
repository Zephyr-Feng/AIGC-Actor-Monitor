#!/usr/bin/env python3
"""Check engineering invariants of the fixed 6x3 preflight, without scoring labels."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CONDITIONS = ("full", "summary_mask", "output_rename")
GLOBAL = "global_forensic_analyzer"
FORBIDDEN = ("classifier_score", "patch_logits", "image_logit", "probability", "prediction", "verdict")
GLOBAL_REFERENCES = (GLOBAL, "global_representation_analyzer", "representation_inspector", "全局表征", "表征偏离", "全局取证", "全局模型")
CLASSIFICATION_SUMMARY = re.compile(
    r"\b(?:signal|score)\s*=|\b(?:real|fake|real_like|fake_like|synthetic_like)\b|"
    r"(?:倾向|判为|判断为)(?:真实|合成|伪造|假)|(?:真实|合成|伪造|假)(?:倾向|概率)",
    re.IGNORECASE,
)


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def semantic_violations(row: dict) -> list[dict]:
    hits = []
    for step in row["steps"]:
        output = step.get("actor_output") or {}
        for field in ("evidence_summary", "supporting_evidence", "contradictory_evidence"):
            for item in output.get(field, []):
                if any(reference.lower() in item.lower() for reference in GLOBAL_REFERENCES) and CLASSIFICATION_SUMMARY.search(item):
                    hits.append({"sample_id": row["sample_id"], "step": step["step"], "field": field, "text": item})
    return hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument("--inputs-dir", type=Path, required=True)
    parser.add_argument("--trajectories-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ids = [row["sample_id"] for row in load(args.sample_manifest)]
    if len(ids) != 6 or len(set(ids)) != 6:
        raise ValueError("sample must have six unique IDs")
    summary = {"sample_ids": ids, "conditions": {}, "all_conditions_same_prompt": False,
               "all_conditions_same_crop_mode": False, "input_leakage_count": 0}
    prompt_hashes, crop_modes = set(), set()
    for condition in CONDITIONS:
        rows = load(args.trajectories_dir / f"{condition}.jsonl")
        if [row["sample_id"] for row in rows] != ids:
            raise ValueError(f"trajectory order mismatch: {condition}")
        inputs = {row["sample_id"]: row for row in load(args.inputs_dir / f"{condition}.jsonl")}
        for sample_id in ids:
            card = next(tool for tool in inputs[sample_id]["tools"] if tool["tool"] in
                        ("global_representation_analyzer", "representation_inspector"))
            card_text = json.dumps(card, ensure_ascii=False).lower()
            summary["input_leakage_count"] += sum(term in card_text for term in FORBIDDEN)
        prompt_hashes.update(row["prompt_sha256"] for row in rows)
        crop_modes.update(row["crop_mode"] for row in rows)
        global_calls = [row for row in rows if GLOBAL in row["tool_calls"]]
        post_global_steps = [step for row in global_calls for step in row["steps"]
                             if step["num_images_in_context"] == 4]
        summary["conditions"][condition] = {
            "trajectories": len(rows),
            "parse_valid": sum(row["parse_valid"] for row in rows),
            "turn_parse_errors": sum(row["turn_parse_errors"] for row in rows),
            "global_calls": len(global_calls),
            "four_image_actor_steps": len(post_global_steps),
            "crop_grid_mismatch": sum(step["num_images_in_context"] != step["image_grid_count"]
                                      for row in rows for step in row["steps"]),
            "called_other_tools_after_global": sum(any(name != GLOBAL for name in row["tool_calls"][row["tool_calls"].index(GLOBAL)+1:])
                                                   for row in global_calls),
            "callable_protocol_errors": sum(bool(step.get("invalid_action")) for row in rows for step in row["steps"]),
            "global_semantic_violations": [hit for row in rows for hit in semantic_violations(row)],
        }
    summary["all_conditions_same_prompt"] = len(prompt_hashes) == 1
    summary["all_conditions_same_crop_mode"] = crop_modes == {"pixels"}
    by_condition = {condition: {row["sample_id"]: row for row in load(args.trajectories_dir / f"{condition}.jsonl")}
                    for condition in CONDITIONS}
    summary["same_crop_pixels_when_called"] = all(
        len({tuple(by_condition[condition][sample_id]["crop_image_sha256"])
             for condition in CONDITIONS if GLOBAL in by_condition[condition][sample_id]["tool_calls"]}) <= 1
        for sample_id in ids
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
