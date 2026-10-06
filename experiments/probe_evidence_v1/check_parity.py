"""Stage A gate: compare extracted classifier outputs to frozen Actor-0 PROBE scores."""

import csv
import json
from pathlib import Path

from extract_features import ACTOR, OUT, manifest_rows, safe_stem


def main():
    rows = manifest_rows("eval")
    score_path = ACTOR / "probe_predictions.csv"
    with score_path.open(newline="") as stream:
        baseline = {row["sample_id"]: row for row in csv.DictReader(stream)}
    audit_path = OUT / "audit/eval_classifier_internal_outputs.jsonl"
    audits = [json.loads(line) for line in audit_path.read_text().splitlines()]
    expected_ids = [row["sample_id"] for row in rows]
    actual_ids = [row["sample_id"] for row in audits]
    order_match = actual_ids == expected_ids
    max_difference = 0.0
    prediction_matches = 0
    detail = []
    for row, audit in zip(rows, audits):
        sid = row["sample_id"]
        if sid != audit["sample_id"]:
            break
        previous = baseline[sid]
        difference = abs(audit["image_probability"] - float(previous["score"]))
        max_difference = max(max_difference, difference)
        same_prediction = audit["prediction"] == int(previous["prediction"])
        prediction_matches += int(same_prediction)
        feature_path = OUT / "work/eval" / f"{safe_stem(sid)}.npz"
        detail.append({"sample_id": sid, "patch_count": audit["patch_count"],
                       "probability_abs_error": difference,
                       "prediction_match": same_prediction,
                       "feature_file_exists": feature_path.exists()})
    passed = (len(rows) == len(audits) == len(detail) == 300 and order_match
              and prediction_matches == 300 and max_difference < 1e-5
              and all(x["feature_file_exists"] and x["patch_count"] > 0 for x in detail))
    report = {"pass": passed, "expected": 300, "observed": len(audits),
              "same_order": order_match, "prediction_matches": prediction_matches,
              "max_probability_abs_error": max_difference,
              "patch_count_distribution": {str(n): sum(x["patch_count"] == n for x in detail)
                                           for n in sorted({x["patch_count"] for x in detail})},
              "criterion": "300/300 same order and predictions, max probability error < 1e-5"}
    analysis = OUT / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / "parity_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (analysis / "parity_report.md").write_text(
        "# PROBE Stage A parity\n\n"
        f"- Result: {'PASS' if passed else 'FAIL'}\n"
        f"- Samples: {len(audits)}/300; same order: {order_match}\n"
        f"- Same predictions: {prediction_matches}/300\n"
        f"- Maximum absolute probability error: {max_difference:.9g}\n"
        f"- Patch count distribution: {report['patch_count_distribution']}\n"
        "\nThe frozen PROBE score CSV is the comparison source. "
        "Reference extraction is blocked unless this report passes.\n"
    )
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit("Stage A parity failed; stop before reference bank")


if __name__ == "__main__":
    main()
