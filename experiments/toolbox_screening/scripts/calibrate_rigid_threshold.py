#!/usr/bin/env python3
"""Freeze a RIGID similarity threshold using only a separate calibration split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration-manifest", type=Path, required=True)
    parser.add_argument("--calibration-scores", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    calibration_rows = [json.loads(line) for line in args.calibration_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    test_rows = [json.loads(line) for line in args.test_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    calibration_by_id = {row["sample_id"]: row for row in calibration_rows}
    if len(calibration_by_id) != len(calibration_rows):
        raise ValueError("Calibration manifest contains duplicate sample IDs")
    calibration_groups = {row["source_group"] for row in calibration_rows}
    test_groups = {row.get("source_group", row.get("source_group_id")) for row in test_rows}
    if calibration_groups & test_groups:
        raise ValueError("Calibration and frozen test source groups overlap")
    if not calibration_groups or len(calibration_rows) != 3 * len(calibration_groups):
        raise ValueError("Calibration manifest must contain exactly three generator images per source group")

    scores = []
    labels = []
    seen_ids = set()
    with args.calibration_scores.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["sample_id"] in seen_ids:
                raise ValueError(f"Duplicate calibration score: {row['sample_id']}")
            if row["sample_id"] not in calibration_by_id:
                raise ValueError(f"Unknown calibration score ID: {row['sample_id']}")
            expected = calibration_by_id[row["sample_id"]]
            if (row.get("source_group") != expected["source_group"]
                    or row.get("generator") != expected["generator"]
                    or int(row["ground_truth"]) != int(expected["label_id"])):
                raise ValueError(f"Calibration score identity/label mismatch: {row['sample_id']}")
            seen_ids.add(row["sample_id"])
            score = float(row["similarity_score"])
            if not math.isfinite(score):
                raise ValueError(f"Non-finite calibration similarity: {row['sample_id']}")
            scores.append(score)
            labels.append(int(row["ground_truth"]))
    if len(scores) != len(calibration_rows) or len(seen_ids) != len(calibration_rows):
        raise ValueError("Calibration score count does not match the calibration manifest")
    if seen_ids != set(calibration_by_id):
        raise ValueError("Calibration score IDs do not match the calibration manifest")
    if set(labels) != {0, 1}:
        raise ValueError("Calibration data must contain both labels")

    values = sorted(set(scores))
    candidates = [values[0] - 1.0]
    candidates += [(left + right) / 2.0 for left, right in zip(values, values[1:])]
    candidates += [values[-1] + 1.0]

    def balanced_accuracy(threshold: float) -> float:
        tn = fp = fn = tp = 0
        for score, label in zip(scores, labels):
            prediction = int(score < threshold)
            if label == 1 and prediction == 1:
                tp += 1
            elif label == 1:
                fn += 1
            elif prediction == 1:
                fp += 1
            else:
                tn += 1
        return 0.5 * (tp / (tp + fn) + tn / (tn + fp))

    scored = [(balanced_accuracy(threshold), threshold) for threshold in candidates]
    best = max(score for score, _ in scored)
    maximizers = [threshold for score, threshold in scored if abs(score - best) < 1e-12]
    finite_maximizers = [threshold for threshold in maximizers if values[0] <= threshold <= values[-1]]
    threshold = sorted(finite_maximizers)[len(finite_maximizers) // 2] if finite_maximizers else maximizers[0]

    payload = {
        "tool": "RIGID",
        "threshold_similarity": threshold,
        "decision": "fake iff similarity_score < threshold_similarity",
        "selection_method": "maximum image-level balanced accuracy on the separate calibration set",
        "tie_break": "median of finite maximizing midpoint candidates",
        "calibration_balanced_accuracy": best,
        "calibration_groups": len(calibration_groups),
        "calibration_images": len(scores),
        "calibration_manifest_sha256": sha256(args.calibration_manifest),
        "calibration_scores_sha256": sha256(args.calibration_scores),
        "test_manifest_sha256_recorded_for_disjointness_only": sha256(args.test_manifest),
        "overlap_with_test_groups": [],
        "test_labels_used": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
