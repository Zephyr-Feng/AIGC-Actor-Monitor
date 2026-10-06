#!/usr/bin/env python3
"""Freeze SAFE's real-only threshold, then evaluate the untouched screening split."""

from __future__ import annotations

import argparse
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


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def checked_scores(manifest: list[dict], scores: list[dict], split: str) -> list[tuple[dict, float]]:
    expected = {row["sample_id"]: row for row in manifest if row["split"] == split}
    if len(scores) != len(expected) or len({row["sample_id"] for row in scores}) != len(expected):
        raise ValueError(f"Incomplete or duplicate {split} scores")
    joined = []
    for score in scores:
        sample_id = score["sample_id"]
        if sample_id not in expected:
            raise ValueError(f"Unexpected {split} sample: {sample_id}")
        record = expected[sample_id]
        if any(score[key] != record[key] for key in ("source_group", "generator", "label", "split")) or score["image_sha256"] != record["sha256"]:
            raise ValueError(f"Score/manifest mismatch: {sample_id}")
        value = float(score["fake_probability"])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid score: {sample_id}")
        joined.append((record, value))
    return joined


def auc(real_scores: list[float], fake_scores: list[float]) -> float:
    return sum(1 if fake > real else 0.5 if fake == real else 0 for real in real_scores for fake in fake_scores) / (len(real_scores) * len(fake_scores))


def metrics(joined: list[tuple[dict, float]], threshold: float) -> dict:
    real = [(row, value) for row, value in joined if row["label"] == "real"]
    fake = [(row, value) for row, value in joined if row["label"] == "fake"]
    specificity = sum(value < threshold for _, value in real) / len(real)
    recall = sum(value >= threshold for _, value in fake) / len(fake)
    out = {
        "real_correct": sum(value < threshold for _, value in real),
        "real_false_positive": sum(value >= threshold for _, value in real),
        "specificity": specificity,
        "fake_correct": sum(value >= threshold for _, value in fake),
        "fake_recall": recall,
        "balanced_accuracy": (specificity + recall) / 2,
        "auc": auc([value for _, value in real], [value for _, value in fake]),
    }
    out["generators"] = {}
    for generator in ("flux", "sd3_5"):
        subset = [value for row, value in fake if row["generator"] == generator]
        out["generators"][generator] = {
            "correct": sum(value >= threshold for value in subset),
            "recall": sum(value >= threshold for value in subset) / len(subset),
            "auc": auc([value for _, value in real], subset),
        }
    out["orientations"] = {}
    for orientation in ("landscape", "portrait"):
        r = [value for row, value in real if row["orientation"] == orientation]
        f = [value for row, value in fake if row["orientation"] == orientation]
        out["orientations"][orientation] = {
            "real_total": len(r), "real_correct": sum(value < threshold for value in r),
            "specificity": sum(value < threshold for value in r) / len(r),
            "auc": auc(r, f),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--calibration-scores", type=Path, required=True)
    parser.add_argument("--threshold", type=Path, required=True)
    parser.add_argument("--screening-scores", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    manifest = rows(args.manifest)
    if len(manifest) != 400:
        raise ValueError("Expected frozen 400-image manifest")
    calibration = checked_scores(manifest, rows(args.calibration_scores), "calibration")
    if len(calibration) != 100 or any(row["generator"] != "raise" for row, _ in calibration):
        raise ValueError("Calibration must contain 100 RAISE real images only")
    ordered = sorted(value for _, value in calibration)
    threshold = math.nextafter(ordered[79], math.inf)
    freeze = {
        "rule": "80th sorted calibration real fake score, then nextafter toward +inf; fake iff score >= threshold",
        "target_specificity": 0.8,
        "calibration_real_correct": sum(value < threshold for value in ordered),
        "threshold": threshold,
        "manifest_sha256": sha256(args.manifest),
        "calibration_scores_sha256": sha256(args.calibration_scores),
    }
    if args.screening_scores is None:
        if args.threshold.exists():
            raise FileExistsError(args.threshold)
        args.threshold.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(freeze, sort_keys=True))
        return
    if args.report is None:
        raise ValueError("--report is required with --screening-scores")
    stored = json.loads(args.threshold.read_text(encoding="utf-8"))
    if stored != freeze:
        raise ValueError("Frozen threshold differs from current calibration inputs")
    if args.report.exists():
        raise FileExistsError(args.report)
    screening = checked_scores(manifest, rows(args.screening_scores), "screening")
    if len(screening) != 300:
        raise ValueError("Expected 300 screening scores")
    current = metrics(screening, threshold)
    gate = {
        "real_80_of_100": current["real_correct"] >= 80,
        "flux_70_of_100": current["generators"]["flux"]["correct"] >= 70,
        "sd3_5_70_of_100": current["generators"]["sd3_5"]["correct"] >= 70,
        "orientation_warning": any(item["specificity"] < 0.70 for item in current["orientations"].values()),
    }
    report = {
        "manifest_sha256": sha256(args.manifest),
        "calibration_scores_sha256": sha256(args.calibration_scores),
        "threshold_sha256": sha256(args.threshold),
        "screening_scores_sha256": sha256(args.screening_scores),
        "threshold": threshold,
        "default_0_5": metrics(screening, 0.5),
        "frozen_threshold": current,
        "gate": gate,
        "stage1_viable": all(gate[key] for key in ("real_80_of_100", "flux_70_of_100", "sd3_5_70_of_100")) and not gate["orientation_warning"],
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
