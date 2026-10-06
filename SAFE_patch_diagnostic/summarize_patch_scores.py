#!/usr/bin/env python3
"""Summarize fixed-threshold SAFE patch scores and baseline comparisons."""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path


POSITIONS = ("top_left", "top_right", "bottom_left", "bottom_right", "center")
THRESHOLD = 0.9561132788658143


def rows_from_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def read_baseline(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    threshold_line = next(line for line in lines if line.startswith("# frozen_fake_threshold="))
    threshold = float(threshold_line.split("=", 1)[1].split(";", 1)[0])
    records = list(csv.DictReader(line for line in lines if line and not line.startswith("#")))
    if threshold != THRESHOLD or len(records) != 300:
        raise ValueError("Frozen baseline threshold/list mismatch")
    return {row["image_id"]: {
        "label": row["label"],
        "generator": row["generator"],
        "score": float(row["baseline_fake_probability"]),
        "sample_id": row["sample_id"],
    } for row in records}


def auc(records, labels):
    real = [score for image_id, score in records if labels[image_id]["label"] == "real"]
    fake = [score for image_id, score in records if labels[image_id]["label"] == "fake"]
    if len(real) != 100 or len(fake) != 200:
        raise ValueError(f"Expected 100 real and 200 fake, got {len(real)} and {len(fake)}")
    return sum(1 if f > r else 0.5 if f == r else 0 for r in real for f in fake) / (len(real) * len(fake))


def metrics(records, labels):
    if len(records) != 300:
        raise ValueError(f"Expected 300 scores, got {len(records)}")
    if len({image_id for image_id, _ in records}) != 300:
        raise ValueError("Expected one score per each of the 300 frozen images")
    tn = sum(labels[image_id]["label"] == "real" and score < THRESHOLD for image_id, score in records)
    fp = sum(labels[image_id]["label"] == "real" and score >= THRESHOLD for image_id, score in records)
    tp = sum(labels[image_id]["label"] == "fake" and score >= THRESHOLD for image_id, score in records)
    fn = sum(labels[image_id]["label"] == "fake" and score < THRESHOLD for image_id, score in records)
    by_generator = {}
    for generator in ("flux", "sd3_5"):
        ids = [image_id for image_id, _ in records if labels[image_id]["generator"] == generator]
        if len(ids) != 100:
            raise ValueError(f"Expected 100 {generator} images, got {len(ids)}")
        scores = dict(records)
        by_generator[generator] = sum(scores[i] >= THRESHOLD for i in ids) / 100
    return {
        "auc": auc(records, labels),
        "accuracy": (tn + tp) / 300,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / 200,
        "flux_recall": by_generator["flux"],
        "sd3_5_recall": by_generator["sd3_5"],
        "real_fp": fp / 100,
        "confusion": {"tn": tn, "fp": fp, "tp": tp, "fn": fn},
    }


def fmt(value):
    return f"{value:.4f}"


def main():
    exp = Path(__file__).resolve().parent
    baseline = read_baseline(exp / "baseline_file_list.txt")
    scores = rows_from_csv(exp / "patch_output" / "scores.csv")
    by_position = {position: [] for position in POSITIONS}
    by_image = defaultdict(dict)
    seen = set()
    for row in scores:
        stem = Path(row["image"]).stem
        position = row["position"]
        suffix = f"_{position}"
        if position not in POSITIONS or not stem.endswith(suffix):
            raise ValueError(f"Filename/position mismatch: {row['image']} / {position}")
        image_id = stem[:-len(suffix)]
        key = (image_id, position)
        if key in seen or image_id not in baseline or position not in by_position:
            raise ValueError(f"Unexpected or duplicate score row: {key}")
        if row["label"] != baseline[image_id]["label"] or row["position"] != position:
            raise ValueError(f"Score/list mismatch: {key}")
        score = float(row["score"])
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(f"Invalid fake probability for {key}: {score}")
        seen.add(key)
        by_position[position].append((image_id, score))
        by_image[image_id][position] = score
    expected = {(image_id, position) for image_id in baseline for position in POSITIONS}
    if seen != expected or len(scores) != 1500:
        raise ValueError(f"Expected exactly 1,500 unique scores; got {len(scores)}")

    baseline_result = metrics([(image_id, rec["score"]) for image_id, rec in baseline.items()], baseline)
    position_metrics = {p: metrics(by_position[p], baseline) for p in POSITIONS}
    center = position_metrics["center"]
    aggregates = {}
    for method in ("max", "mean"):
        records = []
        for image_id, rec in baseline.items():
            values = list(by_image[image_id].values())
            score = max(values) if method == "max" else sum(values) / len(values)
            records.append((image_id, score))
        aggregates[method] = metrics(records, baseline)
    delta_auc = aggregates["max"]["auc"] - center["auc"]
    position_range = max(m["auc"] for m in position_metrics.values()) - min(m["auc"] for m in position_metrics.values())
    if delta_auc >= 0.10:
        case = "A"
        interpretation = "Patch coverage substantially improves SAFE performance. This suggests forensic evidence is spatially localized and the original center crop loses useful evidence."
    elif position_range >= 0.03 or delta_auc >= 0.03:
        case = "B"
        interpretation = "SAFE sensitivity depends on spatial location. Different image regions contain different amounts of forensic evidence."
    else:
        case = "C"
        interpretation = "Patch coverage does not materially improve SAFE performance. The failure is unlikely to be caused only by missing local evidence. Target-domain shift or detector mismatch should be investigated."

    lines = [
        "SAFE Patch Coverage Diagnostic — Metrics",
        f"Frozen fake threshold: {THRESHOLD:.16f} (fake iff score >= threshold)",
        "Score direction: softmax(logits)[1] = fake probability",
        "",
        "Baseline (original image, SAFE CenterCrop(256))",
        f"AUC={fmt(baseline_result['auc'])}; Accuracy={fmt(baseline_result['accuracy'])}; Precision={fmt(baseline_result['precision'])}; Recall={fmt(baseline_result['recall'])}; FLUX Recall={fmt(baseline_result['flux_recall'])}; SD3.5 Recall={fmt(baseline_result['sd3_5_recall'])}; Real FP={fmt(baseline_result['real_fp'])}",
        f"Confusion counts: TN={baseline_result['confusion']['tn']}, FP={baseline_result['confusion']['fp']}, TP={baseline_result['confusion']['tp']}, FN={baseline_result['confusion']['fn']}",
        "",
        "Position-level results (same frozen threshold)",
        "position,AUC,Accuracy,FLUX Recall,SD3.5 Recall,Real FP",
    ]
    for p in POSITIONS:
        m = position_metrics[p]
        lines.append(f"{p},{fmt(m['auc'])},{fmt(m['accuracy'])},{fmt(m['flux_recall'])},{fmt(m['sd3_5_recall'])},{fmt(m['real_fp'])}")
    lines += [
        "",
        "Image-level aggregation (same frozen threshold)",
        "method,AUC,Accuracy,Precision,Recall,FLUX Recall,SD3.5 Recall,Real FP",
        f"center_only,{fmt(center['auc'])},{fmt(center['accuracy'])},{fmt(center['precision'])},{fmt(center['recall'])},{fmt(center['flux_recall'])},{fmt(center['sd3_5_recall'])},{fmt(center['real_fp'])}",
        f"max_patch,{fmt(aggregates['max']['auc'])},{fmt(aggregates['max']['accuracy'])},{fmt(aggregates['max']['precision'])},{fmt(aggregates['max']['recall'])},{fmt(aggregates['max']['flux_recall'])},{fmt(aggregates['max']['sd3_5_recall'])},{fmt(aggregates['max']['real_fp'])}",
        f"mean_patch,{fmt(aggregates['mean']['auc'])},{fmt(aggregates['mean']['accuracy'])},{fmt(aggregates['mean']['precision'])},{fmt(aggregates['mean']['recall'])},{fmt(aggregates['mean']['flux_recall'])},{fmt(aggregates['mean']['sd3_5_recall'])},{fmt(aggregates['mean']['real_fp'])}",
        "",
        f"max_patch_minus_center_auc={delta_auc:+.4f}",
        f"position_auc_range={position_range:.4f}",
        "Interpretation rule: Case A if max-patch AUC gain >=0.10; Case B if the position AUC range >=0.03 or max-patch gain is 0.03–<0.10; otherwise Case C. The 0.03 cutoff operationalizes 'clearly differs' and reuses the prior SAFE diagnostic's partial-effect boundary.",
        f"Selected Case {case}: {interpretation}",
    ]
    (exp / "patch_output" / "metrics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"baseline":baseline_result,"position":position_metrics,"center":center,"max_patch":aggregates['max'],"mean_patch":aggregates['mean'],"max_patch_minus_center_auc":delta_auc,"position_auc_range":position_range,"case":case},ensure_ascii=False,sort_keys=True))


if __name__ == "__main__":
    main()
