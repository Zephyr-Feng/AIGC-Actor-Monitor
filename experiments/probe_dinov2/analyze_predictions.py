#!/usr/bin/env python3
"""Join frozen-manifest scores and write the predeclared descriptive analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    result = {row["sample_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate sample_id in {path}")
    return result


def ranks_auc(labels: list[int], scores: list[float]) -> float:
    pos = sum(labels)
    neg = len(labels) - pos
    if not pos or not neg:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    rank_sum = 0.0
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and scores[order[end]] == scores[order[cursor]]:
            end += 1
        rank = ((cursor + 1) + end) / 2.0
        rank_sum += rank * sum(labels[order[k]] for k in range(cursor, end))
        cursor = end
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def average_precision(labels: list[int], scores: list[float]) -> float:
    positives = sum(labels)
    if not positives:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    tp = fp = 0
    ap = 0.0
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and scores[order[end]] == scores[order[cursor]]:
            end += 1
        group_pos = sum(labels[order[k]] for k in range(cursor, end))
        tp += group_pos
        fp += (end - cursor) - group_pos
        ap += (group_pos / positives) * (tp / (tp + fp))
        cursor = end
    return min(1.0, ap)


def metrics(rows: list[dict], score_key: str, pred_key: str) -> dict:
    y = [int(r["label"] == "fake") for r in rows]
    scores = [float(r[score_key]) for r in rows]
    pred = [int(r[pred_key]) for r in rows]
    tp = sum(a == 1 and b == 1 for a, b in zip(y, pred))
    tn = sum(a == 0 and b == 0 for a, b in zip(y, pred))
    fp = sum(a == 0 and b == 1 for a, b in zip(y, pred))
    fn = sum(a == 1 and b == 0 for a, b in zip(y, pred))
    recall = tp / (tp + fn) if tp + fn else float("nan")
    specificity = tn / (tn + fp) if tn + fp else float("nan")
    return {
        "n": len(rows), "n_real": len(rows) - sum(y), "n_fake": sum(y),
        "accuracy": (tp + tn) / len(rows),
        "balanced_accuracy": (recall + specificity) / 2,
        "roc_auc": ranks_auc(y, scores), "average_precision": average_precision(y, scores),
        "specificity": specificity, "fake_recall": recall,
        "false_positive_rate": fp / (tn + fp) if tn + fp else float("nan"),
        "false_negative_rate": fn / (tp + fn) if tp + fn else float("nan"),
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    e = math.exp(x)
    return e / (1 + e)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--fsd", type=Path, required=True)
    parser.add_argument("--aide", type=Path, required=True)
    parser.add_argument("--safe", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--safe-threshold", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines()]
    ids = [r["sample_id"] for r in manifest]
    if len(ids) != 300 or len(set(ids)) != 300:
        raise ValueError("expected 300 unique manifest rows")
    probe_rows = list(csv.DictReader(args.probe.open("r", encoding="utf-8-sig", newline="")))
    collections = {
        "PROBE": {r["sample_id"]: r for r in probe_rows},
        "FSD": load_jsonl(args.fsd),
        "AIDE": load_jsonl(args.aide),
        "SAFE": load_jsonl(args.safe),
    }
    for name, values in collections.items():
        if set(values) != set(ids):
            raise ValueError(f"{name} score ids do not exactly match the frozen manifest")

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    safe_threshold = float(json.loads(args.safe_threshold.read_text(encoding="utf-8"))["threshold"])
    parameters = calibration["models"]

    joined = []
    for source in manifest:
        sid = source["sample_id"]
        p, f, a, s = (collections[name][sid] for name in ("PROBE", "FSD", "AIDE", "SAFE"))
        y = source["label"]
        if any(str(item.get("label")) != y for item in (f, a, s)) or int(p["label"]) != int(y == "fake"):
            raise ValueError(f"label mismatch for {sid}")
        fcfg, acfg = parameters["fsd"], parameters["aide"]
        fz = -float(f["z_score"])
        amargin = float(a["logits"][1]) - float(a["logits"][0])
        pf = sigmoid(float(fcfg["intercept"]) + float(fcfg["slope"]) * ((fz - float(fcfg["center"])) / float(fcfg["scale"])))
        pa = sigmoid(float(acfg["intercept"]) + float(acfg["slope"]) * ((amargin - float(acfg["center"])) / float(acfg["scale"])))
        probe_score = float(p["score"])
        safe_score = float(s["fake_probability"])
        values = {
            "sample_id": sid, "source_group": source["source_group"], "generator": source["generator"], "label": y,
            "probe_score": probe_score, "probe_pred": int(p["prediction"]),
            "fsd_score": pf, "fsd_pred": int(pf >= 0.5), "fsd_default_score": fz,
            "fsd_default_pred": int(bool(f["is_fake"])),
            "aide_score": pa, "aide_pred": int(pa >= 0.5),
            "aide_default_score": float(a["fake_probability"]), "aide_default_pred": int(float(a["fake_probability"]) >= 0.5),
            "safe_score": safe_score, "safe_pred": int(safe_score >= safe_threshold), "safe_default_pred": int(safe_score >= 0.5),
        }
        joined.append(values)

    experts = {
        "PROBE": ("probe_score", "probe_pred"),
        "FSD_calibrated": ("fsd_score", "fsd_pred"),
        "AIDE_calibrated": ("aide_score", "aide_pred"),
        "SAFE_frozen": ("safe_score", "safe_pred"),
        "FSD_default": ("fsd_default_score", "fsd_default_pred"),
        "AIDE_default": ("aide_default_score", "aide_default_pred"),
        "SAFE_default": ("safe_score", "safe_default_pred"),
    }
    overall = {name: metrics(joined, score, pred) for name, (score, pred) in experts.items()}
    per_generator = []
    for fake_family in ("flux", "sd3_5"):
        subset = [r for r in joined if r["generator"] in ("raise", fake_family)]
        for name, (score, pred) in experts.items():
            per_generator.append({"comparison": f"raise_vs_{fake_family}", "expert": name, **metrics(subset, score, pred)})

    primary = {name: experts[name] for name in ("PROBE", "FSD_calibrated", "AIDE_calibrated", "SAFE_frozen")}
    errors = {name: [int(r[pred] != int(r["label"] == "fake")) for r in joined] for name, (_, pred) in primary.items()}
    overlap = []
    for i, ei in errors.items():
        for j, ej in errors.items():
            both = sum(a and b for a, b in zip(ei, ej))
            union = sum(a or b for a, b in zip(ei, ej))
            n_wrong = sum(ei)
            j_correct_when_i_wrong = sum(a and not b for a, b in zip(ei, ej))
            overlap.append({
                "expert_i": i, "expert_j": j, "both_wrong": both,
                "jaccard_error": both / union if union else float("nan"),
                "i_wrong_count": n_wrong,
                "p_j_correct_given_i_wrong": j_correct_when_i_wrong / n_wrong if n_wrong else float("nan"),
                "j_correct_i_wrong_count": j_correct_when_i_wrong,
            })

    y = [int(r["label"] == "fake") for r in joined]
    oracle = {}
    for group in (("FSD_calibrated", "AIDE_calibrated", "SAFE_frozen"), tuple(primary)):
        key = "three_prior_experts" if len(group) == 3 else "four_experts"
        oracle[key] = {"any_expert_correct": sum(any(not errors[e][k] for e in group) for k in range(len(y))), "n": len(y)}
        oracle[key]["accuracy"] = oracle[key]["any_expert_correct"] / len(y)
    majority = []
    for k, row in enumerate(joined):
        votes = sum(row[pred] for _, pred in primary.values())
        pred = int(votes > 2 or (votes == 2 and row["probe_pred"] == 1))
        majority.append({**row, "majority_pred": pred})
    majority_cm = metrics(majority, "probe_score", "majority_pred")
    majority_stats = {key: majority_cm[key] for key in (
        "n", "n_real", "n_fake", "accuracy", "balanced_accuracy", "specificity", "fake_recall",
        "false_positive_rate", "false_negative_rate", "tn", "fp", "fn", "tp",
    )}

    probe_scores = sorted({r["probe_score"] for r in joined})
    candidates = [0.0] + probe_scores + [1.0 + 1e-12]
    best = {"threshold": None, "balanced_accuracy": -1.0}
    for threshold in candidates:
        pred = [int(r["probe_score"] >= threshold) for r in joined]
        current = metrics([{**r, "oracle_pred": q} for r, q in zip(joined, pred)], "probe_score", "oracle_pred")
        if current["balanced_accuracy"] > best["balanced_accuracy"]:
            best = {"threshold": threshold, **current}

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "aligned_predictions.csv", majority)
    write_csv(args.out / "metrics_by_generator.csv", per_generator)
    write_csv(args.out / "error_overlap.csv", overlap)
    result = {
        "manifest_sha256": __import__("hashlib").sha256(args.manifest.read_bytes()).hexdigest(),
        "sample_count": len(joined), "independent_sampling_unit": "source_group (100 groups; descriptive metrics)",
        "primary_thresholds": {"PROBE": ">0.5 (official)", "FSD": "p_fake >= 0.5 (frozen prior calibration)", "AIDE": "p_fake >= 0.5 (frozen prior calibration)", "SAFE": safe_threshold},
        "overall_metrics": overall,
        "oracle_diagnostic": oracle,
        "four_expert_majority_tie_to_PROBE": majority_stats,
        "probe_test_set_oracle_threshold_diagnostic_only": best,
        "majority_votes": {"2:2 tie rule": "use PROBE", "counts_by_class": {"real": sum(r["majority_pred"] == 0 for r in majority), "fake": sum(r["majority_pred"] == 1 for r in majority)}},
    }
    (args.out / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    print(json.dumps({"n": len(joined), "overall": overall, "out": str(args.out)}, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
