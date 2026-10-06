"""Describe the frozen SAFE triage scores without fitting a threshold."""

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def auc(real_scores: list[float], fake_scores: list[float]) -> float:
    comparisons = sum(
        (fake > real) + 0.5 * (fake == real)
        for real in real_scores
        for fake in fake_scores
    )
    return comparisons / (len(real_scores) * len(fake_scores))


def metrics(rows: list[dict]) -> dict:
    real = [row["fake_probability"] for row in rows if row["generator"] == "raise"]
    fake = [row["fake_probability"] for row in rows if row["generator"] != "raise"]
    real_correct = sum(score < 0.5 for score in real)
    fake_correct = sum(score >= 0.5 for score in fake)
    result = {
        "real_n": len(real),
        "fake_n": len(fake),
        "auc": auc(real, fake),
        "real_specificity_at_0_5": real_correct / len(real),
        "real_correct": real_correct,
        "fake_recall_at_0_5": fake_correct / len(fake),
        "fake_correct": fake_correct,
        "balanced_accuracy_at_0_5": (real_correct / len(real) + fake_correct / len(fake)) / 2,
        "real_score_median": statistics.median(real),
        "fake_score_median": statistics.median(fake),
    }
    result["generator"] = {}
    for generator in ("flux", "sd3_5"):
        scores = [row["fake_probability"] for row in rows if row["generator"] == generator]
        correct = sum(score >= 0.5 for score in scores)
        result["generator"][generator] = {
            "n": len(scores),
            "auc_vs_raise": auc(real, scores),
            "recall_at_0_5": correct / len(scores),
            "correct": correct,
            "score_median": statistics.median(scores),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = [json.loads(line) for line in manifest_bytes.splitlines()]
    scores = [json.loads(line) for line in args.scores.read_bytes().splitlines()]
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    if metadata["manifest_sha256"] != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError("score metadata and selection manifest differ")
    manifest_by_id = {row["sample_id"]: row for row in manifest}
    score_by_id = {row["sample_id"]: row for row in scores}
    if len(manifest) != len(scores) or len(score_by_id) != len(scores) or set(manifest_by_id) != set(score_by_id):
        raise ValueError("scores do not match the frozen selection")
    for sample_id, row in score_by_id.items():
        original = manifest_by_id[sample_id]
        if row["image_sha256"] != original["sha256"] or row["label"] != original["label"]:
            raise ValueError(f"score row differs from manifest: {sample_id}")
        if not math.isfinite(row["fake_probability"]) or not 0 <= row["fake_probability"] <= 1:
            raise ValueError(f"invalid SAFE score: {sample_id}")

    orientation_by_group = {
        row["source_group"]: "landscape" if row["width"] > row["height"] else "portrait"
        for row in manifest
        if row["generator"] == "raise"
    }
    overall = metrics(scores)
    by_orientation = {
        orientation: metrics([row for row in scores if orientation_by_group[row["source_group"]] == orientation])
        for orientation in ("landscape", "portrait")
    }
    summary = {
        "purpose": "exploratory triage only; not independent expert admission",
        "sample_count": len(scores),
        "source_group_count": len(orientation_by_group),
        "original_split_group_counts": dict(Counter(row["split"] for row in manifest if row["generator"] == "raise")),
        "manifest_sha256": metadata["manifest_sha256"],
        "scores_sha256": hashlib.sha256(args.scores.read_bytes()).hexdigest(),
        "runtime_seconds_median": {
            "preprocess": statistics.median(row["preprocess_seconds"] for row in scores),
            "forward": statistics.median(row["forward_seconds"] for row in scores),
            "combined": statistics.median(row["preprocess_seconds"] + row["forward_seconds"] for row in scores),
        },
        "overall": overall,
        "by_raise_orientation": by_orientation,
        "interpretation_limit": "30 reused source groups, orientation derived from paired real source, original dimensions differ by class; no threshold fitting or independent admission",
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
