"""Compare a second frozen run with the primary Evidence v1 outputs."""

import json
from pathlib import Path

import numpy as np


ROOT = Path("/root/autodl-tmp/probe-evidence-v1")
PRIMARY = ROOT / "output"
REPEAT = ROOT / "output_repeat"
TOL = 1e-6


def main():
    max_feature_difference = 0.0
    feature_files = 0
    for split in ("eval", "reference"):
        first_dir = PRIMARY / "work" / split
        second_dir = REPEAT / "work" / split
        first_files = {x.name: x for x in first_dir.glob("*.npz")}
        second_files = {x.name: x for x in second_dir.glob("*.npz")}
        if set(first_files) != set(second_files):
            raise ValueError(f"feature file manifests differ for {split}")
        for name in sorted(first_files):
            with np.load(first_files[name]) as a, np.load(second_files[name]) as b:
                if not np.array_equal(a["boxes"], b["boxes"]) or not np.array_equal(a["grid"], b["grid"]):
                    raise ValueError(f"patch layout differs: {split}/{name}")
                difference = float(np.max(np.abs(a["features"] - b["features"])))
                max_feature_difference = max(max_feature_difference, difference)
                if not np.allclose(a["features"], b["features"], atol=TOL, rtol=TOL):
                    raise ValueError(f"features exceed tolerance: {split}/{name} max_abs={difference}")
                feature_files += 1

    first_audit = [json.loads(x) for x in (PRIMARY / "audit/eval_classifier_internal_outputs.jsonl").read_text().splitlines()]
    second_audit = [json.loads(x) for x in (REPEAT / "audit/eval_classifier_internal_outputs.jsonl").read_text().splitlines()]
    if [x["sample_id"] for x in first_audit] != [x["sample_id"] for x in second_audit]:
        raise ValueError("audit sample order differs")
    max_probability_difference = max(abs(a["image_probability"] - b["image_probability"])
                                     for a, b in zip(first_audit, second_audit))
    first_summary = [json.loads(x) for x in (PRIMARY / "evidence/image_statistics.jsonl").read_text().splitlines()]
    second_summary = [json.loads(x) for x in (REPEAT / "evidence/image_statistics.jsonl").read_text().splitlines()]
    if first_summary != second_summary:
        raise ValueError("Evidence Card statistics differ")
    first_cards = {x.name: json.loads(x.read_text()) for x in (PRIMARY / "evidence/cards").glob("*.json")}
    second_cards = {x.name: json.loads(x.read_text()) for x in (REPEAT / "evidence/cards").glob("*.json")}
    if set(first_cards) != set(second_cards):
        raise ValueError("Evidence Card manifests differ")
    for name in first_cards:
        first_top = first_cards[name]["most_atypical_regions"]
        second_top = second_cards[name]["most_atypical_regions"]
        if [x["patch_id"] for x in first_top] != [x["patch_id"] for x in second_top]:
            raise ValueError(f"top region order differs: {name}")
        if any(abs(a["deviation_percentile"] - b["deviation_percentile"]) > TOL
               for a, b in zip(first_top, second_top)):
            raise ValueError(f"top region percentiles differ: {name}")
    first_records = [json.loads(x) for x in (PRIMARY / "evidence/patch_records.jsonl").read_text().splitlines()]
    second_records = [json.loads(x) for x in (REPEAT / "evidence/patch_records.jsonl").read_text().splitlines()]
    if len(first_records) != len(second_records):
        raise ValueError("patch record count differs")
    if any((a["sample_id"], a["patch_id"]) != (b["sample_id"], b["patch_id"])
           or abs(a["reference_deviation_percentile"] - b["reference_deviation_percentile"]) > TOL
           for a, b in zip(first_records, second_records)):
        raise ValueError("patch region ranking or percentiles differ")
    if max_probability_difference >= 1e-5:
        raise ValueError("repeated classifier outputs exceed parity tolerance")
    report = {
        "pass": True, "feature_files_compared": feature_files,
        "max_feature_abs_difference": max_feature_difference,
        "feature_tolerance_atol_rtol": TOL,
        "max_classifier_probability_abs_difference": max_probability_difference,
        "region_order_identical": True,
        "top_three_region_rankings_identical": True,
        "patch_percentiles_within_tolerance": True,
        "image_statistics_identical": True,
    }
    destination = PRIMARY / "analysis/reproducibility_report.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    (PRIMARY / "analysis/reproducibility_report.md").write_text(
        "# Evidence v1 reproducibility\n\n"
        f"- Result: PASS\n- Feature files compared: {feature_files}\n"
        f"- Maximum feature absolute difference: {max_feature_difference:.9g} "
        f"(atol/rtol {TOL})\n"
        f"- Maximum classifier probability difference: {max_probability_difference:.9g}\n"
        "- Region order: identical\n- Patch percentiles: within tolerance\n"
        "- Evidence image statistics: identical\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
