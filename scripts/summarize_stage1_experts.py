#!/usr/bin/env python3
"""Summarize uncalibrated Stage 1 expert scores at their shipped thresholds."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def auc(items: list[tuple[float, bool]]) -> float:
    ordered = sorted(items, key=lambda item: item[0])
    positives = sum(label for _, label in ordered)
    negatives = len(ordered) - positives
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-dir", type=Path, required=True)
    parser.add_argument("--aide-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if json.loads(args.aide_scores.with_suffix(".meta.json").read_text()).get("input_order") != "dct4_then_original":
        raise ValueError("AIDE scores must use the official four-DCT-then-original input order")

    def read(path: Path) -> dict[str, dict[str, object]]:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        result = {row["sample_id"]: row for row in rows}
        if len(result) != len(rows):
            raise ValueError(f"duplicate sample_id in {path}")
        return result

    fsd = read(args.scores_dir / "fsd.jsonl")
    aide = read(args.aide_scores)
    if fsd.keys() != aide.keys():
        raise ValueError("FSD and AIDE sample ids differ")

    rows = []
    for sample_id, f in fsd.items():
        a = aide[sample_id]
        if any(f[key] != a[key] for key in ("image_sha256", "label", "split", "generator", "source_group")):
            raise ValueError(f"experts disagree on manifest row: {sample_id}")
        rows.append((f, a))

    summary: dict[str, object] = {"images": len(rows), "splits": {}}
    for split in ("calibration", "screening"):
        data = [(f, a) for f, a in rows if f["split"] == split]
        report: dict[str, object] = {"images": len(data), "source_groups": len({f["source_group"] for f, _ in data}), "experts": {}}
        predictions = {
            "fsd": lambda f, a: bool(f["is_fake"]),
            "aide": lambda f, a: float(a["fake_probability"]) > 0.5,
        }
        scores = {
            "fsd": lambda f, a: -float(f["z_score"]),
            "aide": lambda f, a: float(a["fake_probability"]),
        }
        for expert in ("fsd", "aide"):
            pred = predictions[expert]
            truth_fake = lambda f, a: f["label"] == "fake"
            real = [(f, a) for f, a in data if f["label"] == "real"]
            fake = [(f, a) for f, a in data if f["label"] == "fake"]
            specificity = sum(not pred(f, a) for f, a in real) / len(real)
            fake_recall = sum(pred(f, a) for f, a in fake) / len(fake)
            by_generator = {}
            for generator in ("raise", "flux", "sd3_5"):
                subset = [(f, a) for f, a in data if f["generator"] == generator]
                by_generator[generator] = {
                    "n": len(subset),
                    "correct_rate": sum((not pred(f, a)) if generator == "raise" else pred(f, a) for f, a in subset) / len(subset),
                }
            latency_field = "score_seconds"
            latencies = [(f if expert == "fsd" else a)[latency_field] for f, a in data]
            result = {
                "default_threshold_balanced_accuracy": (specificity + fake_recall) / 2,
                "real_specificity": specificity,
                "pooled_fake_recall": fake_recall,
                "auc_fake_direction": auc([(scores[expert](f, a), truth_fake(f, a)) for f, a in data]),
                "latency_mean_seconds": statistics.mean(latencies),
                "latency_median_seconds": statistics.median(latencies),
                "by_generator": by_generator,
            }
            if expert == "aide":
                result["prepare_median_seconds"] = statistics.median(a["prepare_seconds"] for _, a in data)
            report["experts"][expert] = result

        complementarity = {}
        for generator, label in (("raise", "real"), ("flux", "fake"), ("sd3_5", "fake")):
            subset = [(f, a) for f, a in data if f["generator"] == generator]
            f_ok = lambda f, a: bool(f["is_fake"]) == (label == "fake")
            a_ok = lambda f, a: (float(a["fake_probability"]) > 0.5) == (label == "fake")
            complementarity[generator] = {
                "fsd_only_correct": sum(f_ok(f, a) and not a_ok(f, a) for f, a in subset),
                "aide_only_correct": sum(a_ok(f, a) and not f_ok(f, a) for f, a in subset),
                "both_wrong": sum(not f_ok(f, a) and not a_ok(f, a) for f, a in subset),
            }
        report["error_complementarity_at_default_thresholds"] = complementarity
        summary["splits"][split] = report

    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
