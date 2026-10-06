#!/usr/bin/env python3
"""Fit class-balanced one-dimensional logistic calibration on Stage 1 calibration groups."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from summarize_stage1_experts import auc


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1 + exp_value)


def fit_logistic(samples: list[tuple[float, bool]]) -> dict[str, float]:
    positive_count = sum(label for _, label in samples)
    negative_count = len(samples) - positive_count
    weights = [0.5 / positive_count if label else 0.5 / negative_count for _, label in samples]
    center = sum(weight * value for weight, (value, _) in zip(weights, samples))
    scale = math.sqrt(sum(weight * (value - center) ** 2 for weight, (value, _) in zip(weights, samples)))
    x = [(value - center) / scale for value, _ in samples]
    y = [float(label) for _, label in samples]
    intercept, slope = 0.0, 1.0
    coefficient_penalty = 1e-3

    for _ in range(20000):
        probabilities = [sigmoid(intercept + slope * value) for value in x]
        residuals = [weight * (probability - label) for weight, probability, label in zip(weights, probabilities, y)]
        grad_a = sum(residuals) + coefficient_penalty * intercept
        grad_b = sum(residual * value for residual, value in zip(residuals, x)) + coefficient_penalty * slope
        intercept -= grad_a
        slope -= grad_b
        if max(abs(grad_a), abs(grad_b)) < 1e-10:
            break

    return {"center": center, "scale": scale, "intercept": intercept, "slope": slope, "coefficient_penalty": coefficient_penalty}


def predict(parameters: dict[str, float], value: float) -> float:
    standardized = (value - parameters["center"]) / parameters["scale"]
    return sigmoid(parameters["intercept"] + parameters["slope"] * standardized)


def summarize(rows: list[dict[str, object]], probability_key: str) -> dict[str, object]:
    truth = [row["label"] == "fake" for row in rows]
    probabilities = [float(row[probability_key]) for row in rows]
    predictions = [value >= 0.5 for value in probabilities]
    real_indices = [i for i, label in enumerate(truth) if not label]
    fake_indices = [i for i, label in enumerate(truth) if label]
    specificity = sum(not predictions[i] for i in real_indices) / len(real_indices)
    fake_recall = sum(predictions[i] for i in fake_indices) / len(fake_indices)
    report: dict[str, object] = {
        "images": len(rows),
        "source_groups": len({row["source_group"] for row in rows}),
        "balanced_accuracy": (specificity + fake_recall) / 2,
        "real_specificity": specificity,
        "pooled_fake_recall": fake_recall,
        "auc_fake_direction": auc(list(zip(probabilities, truth))),
        "brier_score": sum((probability - label) ** 2 for probability, label in zip(probabilities, truth)) / len(rows),
        "by_generator": {},
    }
    for generator in ("raise", "flux", "sd3_5"):
        selected = [i for i, row in enumerate(rows) if row["generator"] == generator]
        correct = sum(predictions[i] == truth[i] for i in selected)
        report["by_generator"][generator] = {"n": len(selected), "correct_rate": correct / len(selected)}
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-dir", type=Path, required=True)
    parser.add_argument("--aide-scores", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    fsd_path = args.scores_dir / "fsd.jsonl"
    aide_path = args.aide_scores
    if json.loads(aide_path.with_suffix(".meta.json").read_text()).get("input_order") != "dct4_then_original":
        raise ValueError("AIDE scores must use the official four-DCT-then-original input order")
    fsd_rows = [json.loads(line) for line in fsd_path.read_text().splitlines()]
    aide_rows = [json.loads(line) for line in aide_path.read_text().splitlines()]
    fsd = {row["sample_id"]: row for row in fsd_rows}
    aide = {row["sample_id"]: row for row in aide_rows}
    if len(fsd) != 600 or len(aide) != 600 or fsd.keys() != aide.keys():
        raise ValueError("expected 600 aligned records per expert")

    rows = []
    for sample_id, f in fsd.items():
        a = aide[sample_id]
        if f["split"] != a["split"] or f["label"] != a["label"] or f["image_sha256"] != a["image_sha256"]:
            raise ValueError(f"expert records disagree: {sample_id}")
        rows.append({
            "sample_id": sample_id,
            "source_group": f["source_group"],
            "split": f["split"],
            "generator": f["generator"],
            "label": f["label"],
            "fsd_score": -float(f["z_score"]),
            "aide_score": float(a["logits"][1]) - float(a["logits"][0]),
        })

    calibration = [row for row in rows if row["split"] == "calibration"]
    models = {
        "fsd": fit_logistic([(row["fsd_score"], row["label"] == "fake") for row in calibration]),
        "aide": fit_logistic([(row["aide_score"], row["label"] == "fake") for row in calibration]),
    }
    for row in rows:
        row["fsd_p_fake"] = predict(models["fsd"], row["fsd_score"])
        row["aide_p_fake"] = predict(models["aide"], row["aide_score"])

    report = {
        "method": "one-dimensional ridge logistic calibration; class-balanced weights; fit on calibration only",
        "coefficient_penalty": 1e-3,
        "class_prior": {"real_weight": 0.5, "fake_weight": 0.5},
        "inputs": {
            "fsd": "-z_score (higher means more fake)",
            "aide": "logits[1] - logits[0]",
        },
        "scores_sha256": {
            "fsd": hashlib.sha256(fsd_path.read_bytes()).hexdigest(),
            "aide": hashlib.sha256(aide_path.read_bytes()).hexdigest(),
        },
        "models": models,
        "splits": {},
    }
    calibrated_path = args.output_dir / "calibrated_scores.jsonl"
    output = args.output_dir / "calibration_report.json"
    if calibrated_path.exists() or output.exists():
        raise FileExistsError(f"calibration output already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    calibrated_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    for split in ("calibration", "screening"):
        selected = [row for row in rows if row["split"] == split]
        report["splits"][split] = {
            "fsd": summarize(selected, "fsd_p_fake"),
            "aide": summarize(selected, "aide_p_fake"),
        }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
