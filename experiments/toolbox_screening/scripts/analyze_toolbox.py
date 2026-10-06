#!/usr/bin/env python3
"""Align frozen-set predictions and produce the prespecified toolbox analyses."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


GENERATORS = ("raise", "flux", "sd3_5")
DETECTORS = ("PROBE", "PatchCraft", "RIGID")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def as_int(value: str | int | None, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer in {field}: {value!r}") from exc


def as_float(value: str | float | None, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid float in {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite value in {field}: {value!r}")
    return result


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def metric_block(rows: list[dict], score_key: str, pred_key: str) -> dict:
    n = len(rows)
    positives = sum(int(row["label"]) for row in rows)
    negatives = n - positives
    tp = sum(int(row[pred_key]) == 1 and int(row["label"]) == 1 for row in rows)
    tn = sum(int(row[pred_key]) == 0 and int(row["label"]) == 0 for row in rows)
    fp = sum(int(row[pred_key]) == 1 and int(row["label"]) == 0 for row in rows)
    fn = sum(int(row[pred_key]) == 0 and int(row["label"]) == 1 for row in rows)
    sensitivity = tp / positives if positives else None
    specificity = tn / negatives if negatives else None

    # Mann-Whitney AUC with average ranks for ties.
    ordered = sorted(((float(row[score_key]), int(row["label"])) for row in rows), key=lambda item: item[0])
    positive_rank_sum = 0.0
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        average_rank = ((i + 1) + j) / 2.0
        positive_rank_sum += average_rank * sum(label for _, label in ordered[i:j])
        i = j
    auc = ((positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
           if positives and negatives else None)

    # Non-interpolated average precision; equal scores enter at one threshold.
    ranked = sorted(((float(row[score_key]), int(row["label"])) for row in rows), key=lambda item: item[0], reverse=True)
    ap = 0.0
    seen = 0
    found = 0
    i = 0
    while i < len(ranked):
        j = i + 1
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        new_positives = sum(label for _, label in ranked[i:j])
        found += new_positives
        seen += j - i
        ap += (found / seen) * new_positives / positives if positives else 0.0
        i = j
    ap = min(1.0, max(0.0, ap))

    accuracy = (tp + tn) / n if n else None
    bacc = ((sensitivity + specificity) / 2 if sensitivity is not None and specificity is not None else None)
    return {
        "n": n, "n_real": negatives, "n_fake": positives,
        "accuracy": accuracy, "balanced_accuracy": bacc,
        "roc_auc": auc, "average_precision": ap if positives else None,
        "specificity": specificity, "fake_recall": sensitivity,
        "false_positive_rate": fp / negatives if negatives else None,
        "false_negative_rate": fn / positives if positives else None,
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def truthy(value: str | int | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def correlate(a: list[int], b: list[int]) -> float | None:
    if not a or len(a) != len(b):
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def load_predictions(path: Path, expected: dict[str, dict], tool: str) -> dict[str, dict]:
    rows = read_csv(path)
    if len(rows) != len(expected):
        raise ValueError(f"{tool}: expected {len(expected)} rows, found {len(rows)} in {path}")
    result: dict[str, dict] = {}
    for row in rows:
        sample_id = row.get("sample_id", "")
        if sample_id not in expected:
            raise ValueError(f"{tool}: unknown sample_id {sample_id!r}")
        ref = expected[sample_id]
        if sample_id in result:
            raise ValueError(f"{tool}: duplicate sample_id {sample_id}")
        if as_int(row.get("ground_truth" if tool != "PROBE" else "label"), f"{tool}.label") != int(ref["label_id"]):
            raise ValueError(f"{tool}: label mismatch for {sample_id}")
        generator = row.get("generator", "").lower()
        if generator and generator != ref["generator"]:
            raise ValueError(f"{tool}: generator mismatch for {sample_id}")
        source_group = row.get("source_group", row.get("source_group_id", ""))
        if source_group and source_group != ref["source_group"]:
            raise ValueError(f"{tool}: source-group mismatch for {sample_id}")
        image_path = row.get("path", "")
        if image_path and Path(image_path.replace("\\", "/")).stem != Path(ref["relative_path"]).stem:
            raise ValueError(f"{tool}: path/sample mismatch for {sample_id}: {image_path}")
        result[sample_id] = row
    if set(result) != set(expected):
        raise ValueError(f"{tool}: prediction IDs do not match frozen manifest")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--patchcraft", type=Path, required=True)
    parser.add_argument("--rigid", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--safe-jsonl", type=Path, required=True,
                        help="Existing SAFE frozen-set scores; SAFE is not rerun or retuned")
    parser.add_argument("--safe-threshold", type=Path, required=True,
                        help="Previously frozen SAFE threshold from independent calibration")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--patchcraft-runtime", type=Path)
    parser.add_argument("--rigid-runtime", type=Path)
    parser.add_argument("--calibration", type=Path)
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    if len(manifest) != 300:
        raise ValueError(f"Frozen evaluation manifest must contain 300 images; found {len(manifest)}")
    expected = {row["sample_id"]: row for row in manifest}
    if len(expected) != 300:
        raise ValueError("Manifest contains duplicate sample IDs")
    if len({row["source_group"] for row in manifest}) != 100:
        raise ValueError("Frozen manifest must contain 100 source groups")
    for generator in GENERATORS:
        if sum(row["generator"] == generator for row in manifest) != 100:
            raise ValueError(f"Frozen manifest does not contain 100 {generator} images")

    probe = load_predictions(args.probe, expected, "PROBE")
    patchcraft = load_predictions(args.patchcraft, expected, "PatchCraft")
    rigid = load_predictions(args.rigid, expected, "RIGID")
    provenance_rows = read_csv(args.provenance)
    if len(provenance_rows) != 300:
        raise ValueError(f"Provenance: expected 300 rows, found {len(provenance_rows)}")
    provenance: dict[str, dict] = {}
    for row in provenance_rows:
        sample_id = row.get("sample_id", "")
        if sample_id not in expected or sample_id in provenance:
            raise ValueError(f"Provenance: unknown or duplicate sample_id {sample_id!r}")
        ref = expected[sample_id]
        if row.get("source_group_id", row.get("source_group", "")) != ref["source_group"]:
            raise ValueError(f"Provenance source-group mismatch for {sample_id}")
        if as_int(row.get("ground_truth"), "Provenance.label") != ref["label_id"]:
            raise ValueError(f"Provenance label mismatch for {sample_id}")
        if row.get("generator", "").lower() != ref["generator"]:
            raise ValueError(f"Provenance generator mismatch for {sample_id}")
        if Path(row.get("path", "").replace("\\", "/")).stem != Path(ref["relative_path"]).stem:
            raise ValueError(f"Provenance path/sample mismatch for {sample_id}")
        provenance[sample_id] = row
    if set(provenance) != set(expected):
        raise ValueError("Provenance IDs do not match the frozen manifest")
    safe_threshold_data = json.loads(args.safe_threshold.read_text(encoding="utf-8"))
    safe_threshold = float(safe_threshold_data["threshold"])
    if safe_threshold_data.get("manifest_sha256") == __import__("hashlib").sha256(args.manifest.read_bytes()).hexdigest():
        raise ValueError("SAFE threshold metadata unexpectedly references the frozen test manifest")
    safe = {row["sample_id"]: row for row in read_jsonl(args.safe_jsonl)}
    if len(safe) != 300 or set(safe) != set(expected):
        raise ValueError("Existing SAFE scores must cover all 300 frozen images exactly once")
    for sid, row in safe.items():
        ref = expected[sid]
        if row["source_group"] != ref["source_group"] or row["generator"] != ref["generator"]:
            raise ValueError(f"SAFE source identity mismatch for {sid}")
        if int(row["label"] == "fake") != int(ref["label_id"]):
            raise ValueError(f"SAFE label mismatch for {sid}")

    aligned: list[dict] = []
    for ref in manifest:
        sid = ref["sample_id"]
        p, pc, rg, pr = probe[sid], patchcraft[sid], rigid[sid], provenance[sid]
        probe_score = as_float(p["score"], "PROBE.score")
        patch_score = as_float(pc["raw_score"], "PatchCraft.raw_score")
        rigid_score = as_float(rg["raw_decision_score"], "RIGID.raw_decision_score")
        pp = as_int(p["prediction"], "PROBE.prediction")
        pcp = as_int(pc["prediction"], "PatchCraft.prediction")
        rgp = as_int(rg["prediction"], "RIGID.prediction")
        safe_score = as_float(safe[sid]["fake_probability"], "SAFE.fake_probability")
        safe_pred = int(safe_score >= safe_threshold)
        label = int(ref["label_id"])
        pc_margin = abs(patch_score - 0.5)
        pc_unified = {
            "tool": "PatchCraft", "evidence_type": "local_texture",
            "verdict": "fake" if pcp else "real", "score": patch_score,
            "strength": "weak", "observation": "Official PatchCraft binary output; raw sigmoid score retained.",
            "limitations": "Patch/residual evidence may be affected by resizing or compression.",
        }
        rg_unified = {
            "tool": "RIGID", "evidence_type": "perturbation_stability",
            "verdict": "fake" if rgp else "real", "score": rigid_score,
            "strength": "weak", "observation": "Official DINOv2 representation stability under the fixed perturbation.",
            "limitations": "The fixed binary operating point was estimated on separate calibration groups.",
        }
        aligned.append({
            "path": ref["relative_path"], "source_group_id": ref["source_group"],
            "group": ref["source_group"], "sample_id": sid, "label": label,
            "generator": ref["generator"],
            "probe_score": probe_score, "probe_pred": pp, "probe_correct": int(pp == label),
            "patchcraft_score": patch_score, "patchcraft_pred": pcp,
            "patchcraft_correct": int(pcp == label), "patchcraft_margin_from_0_5": pc_margin,
            "rigid_score": rigid_score, "rigid_pred": rgp, "rigid_correct": int(rgp == label),
            "safe_score": safe_score, "safe_pred": safe_pred, "safe_correct": int(safe_pred == label),
            "provenance_actionable": int(truthy(pr["actionable"])),
            "provenance_type": pr.get("provenance_evidence_type", ""),
            "provenance_strength": pr.get("provenance_strength", ""),
            "patchcraft_unified_output": json.dumps(pc_unified, ensure_ascii=False, separators=(",", ":")),
            "rigid_unified_output": json.dumps(rg_unified, ensure_ascii=False, separators=(",", ":")),
            "provenance_unified_output": pr.get("unified_output_json", ""),
        })

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    aligned_fields = list(aligned[0])
    write_csv(output_dir / "aligned_predictions.csv", aligned, aligned_fields)

    keys = {"PROBE": ("probe_score", "probe_pred"),
            "PatchCraft": ("patchcraft_score", "patchcraft_pred"),
            "RIGID": ("rigid_score", "rigid_pred")}
    metrics: dict = {
        "manifest_sha256": __import__("hashlib").sha256(args.manifest.read_bytes()).hexdigest(),
        "sample_count": len(aligned), "source_group_count": 100,
        "independent_sampling_unit": "source_group (100 groups; image-level descriptive metrics)",
        "threshold_sources": {
            "PROBE": "official fixed score > 0.5",
            "PatchCraft": "official fixed sigmoid score > 0.5",
            "RIGID": str(args.calibration.resolve()) if args.calibration else "threshold recorded in rigid predictions/config",
        },
        "overall_metrics": {}, "by_generator_pair": {},
    }
    for tool, (score_key, pred_key) in keys.items():
        metrics["overall_metrics"][tool] = metric_block(aligned, score_key, pred_key)

    generator_metric_rows: list[dict] = []
    for fake_generator, comparison in (("flux", "RAISE_vs_FLUX"), ("sd3_5", "RAISE_vs_SD3_5")):
        subset = [r for r in aligned if r["generator"] in ("raise", fake_generator)]
        metrics["by_generator_pair"][comparison] = {}
        for tool, (score_key, pred_key) in keys.items():
            result = metric_block(subset, score_key, pred_key)
            metrics["by_generator_pair"][comparison][tool] = result
            generator_metric_rows.append({"tool": tool, "comparison": comparison, **result})

    coverage_fields = {
        "c2pa_present": "c2pa_present", "exif_present": "exif_present",
        "xmp_present": "xmp_present", "iptc_present": "iptc_present",
        "camera_metadata_present": "camera_metadata_present",
        "software_metadata_present": "software_metadata_present", "actionable": "actionable",
    }
    provenance_coverage = {}
    for group_name, subset in [("overall", aligned)] + [(g, [r for r in aligned if r["generator"] == g]) for g in GENERATORS]:
        coverage = {name: sum(truthy(provenance[sid].get(column, "")) for sid in [r["sample_id"] for r in subset]) / len(subset)
                    for name, column in coverage_fields.items()}
        coverage["n"] = len(subset)
        provenance_coverage[group_name] = coverage
        generator_metric_rows.append({"tool": "Provenance", "comparison": group_name, "n": len(subset), **coverage})
    metrics["provenance_coverage"] = provenance_coverage

    probe_errors = [row for row in aligned if row["probe_correct"] == 0]
    failure_rows = []
    conditional: dict[str, dict] = {}
    for tool in ("PatchCraft", "RIGID"):
        correct_key = "patchcraft_correct" if tool == "PatchCraft" else "rigid_correct"
        fixed_correct = sum(row[correct_key] for row in probe_errors)
        conditional[tool] = {
            "probe_error_n": len(probe_errors),
            "tool_correct_given_probe_wrong_n": fixed_correct,
            "tool_correct_given_probe_wrong": fixed_correct / len(probe_errors) if probe_errors else None,
        }
    safe_correct_given_probe_wrong = sum(row["safe_correct"] for row in probe_errors)
    conditional["SAFE (existing frozen result)"] = {
        "probe_error_n": len(probe_errors),
        "tool_correct_given_probe_wrong_n": safe_correct_given_probe_wrong,
        "tool_correct_given_probe_wrong": safe_correct_given_probe_wrong / len(probe_errors) if probe_errors else None,
        "threshold": safe_threshold,
        "threshold_source": str(args.safe_threshold.resolve()),
        "rerun": False,
    }
    for row in probe_errors:
        failure_rows.append({
            "path": row["path"], "source_group_id": row["source_group_id"],
            "sample_id": row["sample_id"], "label": row["label"], "generator": row["generator"],
            "probe_score": row["probe_score"], "probe_pred": row["probe_pred"],
            "patchcraft_score": row["patchcraft_score"], "patchcraft_pred": row["patchcraft_pred"],
            "patchcraft_correct": row["patchcraft_correct"],
            "rigid_score": row["rigid_score"], "rigid_pred": row["rigid_pred"],
            "rigid_correct": row["rigid_correct"],
            "safe_score": row["safe_score"], "safe_pred": row["safe_pred"], "safe_correct": row["safe_correct"],
            "provenance_actionable": row["provenance_actionable"],
            "provenance_type": row["provenance_type"],
        })
    write_csv(output_dir / "probe_failure_analysis.csv", failure_rows, list(failure_rows[0]) if failure_rows else [
        "path", "source_group_id", "sample_id", "label", "generator", "probe_score", "probe_pred",
        "patchcraft_score", "patchcraft_pred", "patchcraft_correct", "rigid_score", "rigid_pred",
        "rigid_correct", "safe_score", "safe_pred", "safe_correct", "provenance_actionable", "provenance_type",
    ])

    overlap_rows = []
    for first, second in (("PROBE", "PatchCraft"), ("PROBE", "RIGID"), ("PatchCraft", "RIGID")):
        first_correct_key = {"PROBE": "probe_correct", "PatchCraft": "patchcraft_correct", "RIGID": "rigid_correct"}[first]
        second_correct_key = {"PROBE": "probe_correct", "PatchCraft": "patchcraft_correct", "RIGID": "rigid_correct"}[second]
        first_pred_key = keys[first][1]
        second_pred_key = keys[second][1]
        fc = [row[first_correct_key] for row in aligned]
        sc = [row[second_correct_key] for row in aligned]
        overlap_rows.append({
            "first_tool": first, "second_tool": second, "scope": "overall", "n": len(aligned),
            "both_correct": sum(a == 1 and b == 1 for a, b in zip(fc, sc)),
            "first_correct_second_wrong": sum(a == 1 and b == 0 for a, b in zip(fc, sc)),
            "first_wrong_second_correct": sum(a == 0 and b == 1 for a, b in zip(fc, sc)),
            "both_wrong": sum(a == 0 and b == 0 for a, b in zip(fc, sc)),
            "disagreement_n": sum(row[first_pred_key] != row[second_pred_key] for row in aligned),
            "disagreement_rate": sum(row[first_pred_key] != row[second_pred_key] for row in aligned) / len(aligned),
            "error_indicator_correlation": correlate([1 - x for x in fc], [1 - x for x in sc]),
        })
    write_csv(output_dir / "error_overlap.csv", overlap_rows, list(overlap_rows[0]))

    oracle_sets = {
        "PROBE": ("probe_correct",),
        "PROBE + PatchCraft": ("probe_correct", "patchcraft_correct"),
        "PROBE + RIGID": ("probe_correct", "rigid_correct"),
        "PROBE + PatchCraft + RIGID": ("probe_correct", "patchcraft_correct", "rigid_correct"),
    }
    oracle = {}
    probe_oracle_count = sum(row["probe_correct"] for row in aligned)
    for label, fields in oracle_sets.items():
        count = sum(any(row[field] for field in fields) for row in aligned)
        oracle[label] = {"any_tool_correct_n": count, "n": len(aligned), "upper_bound_accuracy": count / len(aligned),
                         "delta_vs_probe": (count - probe_oracle_count) / len(aligned),
                         "diagnostic_only": True}
    disagreement_detail = {}
    for candidate in ("PatchCraft", "RIGID"):
        pred_key = keys[candidate][1]
        cases = [row for row in aligned if row["probe_pred"] != row[pred_key]]
        disagreement_detail[candidate] = {
            "n": len(cases),
            "probe_correct_n": sum(row["probe_correct"] for row in cases),
            "candidate_correct_n": sum(row["patchcraft_correct" if candidate == "PatchCraft" else "rigid_correct"] for row in cases),
            "cases": [{"sample_id": row["sample_id"], "source_group_id": row["source_group_id"],
                       "generator": row["generator"], "label": row["label"],
                       "probe_pred": row["probe_pred"], "probe_correct": row["probe_correct"],
                       "candidate_pred": row[pred_key],
                       "candidate_correct": row["patchcraft_correct" if candidate == "PatchCraft" else "rigid_correct"]}
                      for row in cases],
        }
    metrics["probe_failure_correction"] = conditional
    metrics["oracle_analysis"] = oracle
    metrics["pairwise_error_overlap"] = overlap_rows
    metrics["disagreement_cases"] = disagreement_detail
    metrics["interpretation_guardrails"] = [
        "All metrics are descriptive on the frozen test set; no thresholds, models, or preprocessing were selected from these labels.",
        "The oracle is an upper-bound diagnostic and not deployable performance.",
        "Image-level metrics have 100 source groups as the independent sampling unit.",
        "Provenance absence is inconclusive and is never mapped to fake.",
    ]

    if args.patchcraft_runtime and args.patchcraft_runtime.exists():
        metrics.setdefault("operational_cost", {})["PatchCraft"] = json.loads(args.patchcraft_runtime.read_text(encoding="utf-8"))
    if args.rigid_runtime and args.rigid_runtime.exists():
        metrics.setdefault("operational_cost", {})["RIGID"] = json.loads(args.rigid_runtime.read_text(encoding="utf-8"))
    if args.calibration and args.calibration.exists():
        metrics["rigid_calibration"] = json.loads(args.calibration.read_text(encoding="utf-8"))

    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generator_fields = sorted({key for row in generator_metric_rows for key in row})
    write_csv(output_dir / "metrics_by_generator.csv", generator_metric_rows, generator_fields)
    complementarity = {
        "probe_failure_correction": conditional,
        "pairwise_error_overlap": overlap_rows,
        "oracle_upper_bound_diagnostic_only": oracle,
        "disagreement_cases": disagreement_detail,
        "provenance_coverage": provenance_coverage,
        "decision_basis_note": "Use complementarity and evidence diversity alongside individual performance and operational cost; do not use oracle as system performance.",
    }
    (output_dir / "complementarity.json").write_text(json.dumps(complementarity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(aligned), "probe_errors": len(probe_errors), "overall": metrics["overall_metrics"],
                      "probe_failure_correction": conditional, "oracle": oracle}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
