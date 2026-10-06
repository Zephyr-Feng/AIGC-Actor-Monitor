"""Frozen Evidence v1 validity, descriptive statistics, and visual audit exports."""

from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from extract_features import ACTOR, OUT, manifest_rows, safe_stem


FORBIDDEN = re.compile(r"\b(?:real|fake|probability|verdict|prediction|classifier_score|patch_logits|image_logit)\b", re.I)


def mean_median(values):
    return {"mean": float(np.mean(values)), "median": float(np.median(values))}


def make_sheet(row, card, percentiles, destination):
    stem = safe_stem(row["sample_id"])
    processed = Image.open(OUT / "evidence/processed_images" / f"{stem}.png").convert("RGB")
    thumb = processed.copy()
    thumb.thumbnail((460, 380))
    sheet = Image.new("RGB", (1320, 500), "white")
    sheet.paste(thumb, (20, 65))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 20), f"{row['sample_id']} | processed image", fill="black")
    for rank, region in enumerate(card["most_atypical_regions"], 1):
        crop = Image.open(OUT / "evidence" / region["crop_path"]).convert("RGB")
        crop.thumbnail((265, 350))
        x = 480 + (rank - 1) * 275
        sheet.paste(crop, (x, 65))
        draw.text((x, 20), f"R{rank} p={region['deviation_percentile']:.1f}", fill="black")
        draw.text((x, 425), f"bbox {region['bbox']}", fill="black")
    draw.text((20, 465), f"patch percentile grid: {np.asarray(percentiles).round(1).tolist()}", fill="black")
    sheet.save(destination, format="PNG")


def make_deviation_map(row, patch_records, destination):
    stem = safe_stem(row["sample_id"])
    processed = Image.open(OUT / "evidence/processed_images" / f"{stem}.png").convert("RGBA")
    overlay = Image.new("RGBA", processed.size, (0, 0, 0, 0))
    painter = ImageDraw.Draw(overlay)
    for patch in patch_records:
        percentile = patch["reference_deviation_percentile"]
        bbox = patch["processed_bbox"]
        # Color is a display mapping of the fixed percentile, not a detector threshold.
        red = int(round(255 * percentile / 100))
        blue = 255 - red
        painter.rectangle(tuple(bbox), fill=(red, 20, blue, 75), outline=(255, 255, 255, 210), width=2)
        painter.text((bbox[0] + 6, bbox[1] + 6), f"{percentile:.1f}", fill=(255, 255, 255, 255))
    Image.alpha_composite(processed, overlay).convert("RGB").save(destination, format="PNG")


def main():
    parity = json.loads((OUT / "analysis/parity_report.json").read_text())
    if not parity.get("pass"):
        raise RuntimeError("Stage A parity failed; analysis must stop")
    eval_rows = manifest_rows("eval")
    row_by_id = {row["sample_id"]: row for row in eval_rows}
    summaries = [json.loads(line) for line in (OUT / "evidence/image_statistics.jsonl").read_text().splitlines()]
    if len(summaries) != 300 or [x["sample_id"] for x in summaries] != [x["sample_id"] for x in eval_rows]:
        raise ValueError("evidence summary does not align with frozen eval")
    patches = defaultdict(list)
    for line in (OUT / "evidence/patch_records.jsonl").read_text().splitlines():
        patch = json.loads(line)
        patches[patch["sample_id"]].append(patch)
        if not np.isfinite(patch["deviation"]) or not np.isfinite(patch["reference_deviation_percentile"]):
            raise ValueError("nonfinite evidence distance or percentile")
    bank = np.load(OUT / "reference_bank/features.npy")
    calibration = np.load(OUT / "reference_bank/calibration_distribution.npy")
    if not np.isfinite(bank).all() or not np.isfinite(calibration).all():
        raise ValueError("nonfinite reference bank")
    if len(bank) != len(calibration):
        raise ValueError("reference patch count and calibration count differ")
    if any(len(patches[x["sample_id"]]) != x["num_patches"] for x in summaries):
        raise ValueError("patch records and image summary counts differ")

    cards = OUT / "evidence/cards"
    card_json = sorted(cards.glob("*.json"))
    card_txt = sorted(cards.glob("*.txt"))
    if len(card_json) != 300 or len(card_txt) != 300:
        raise ValueError("expected 300 JSON and 300 text Evidence Cards")
    leaks = []
    for path in card_json + card_txt:
        matches = FORBIDDEN.findall(path.read_text())
        if matches:
            leaks.append({"path": str(path), "matches": matches})
    if leaks:
        raise ValueError(f"Actor-facing conclusion leakage: {leaks[:3]}")
    crop_report = json.loads((OUT / "analysis/crop_reconstruction.json").read_text())
    if crop_report["sampled_images"] != 20 or crop_report["pixel_matches"] != crop_report["crops_checked"]:
        raise ValueError("crop pixel consistency check failed")

    by_generator = {}
    for generator in ("raise", "flux", "sd3_5"):
        selected = [x for x in summaries if row_by_id[x["sample_id"]]["generator"] == generator]
        by_generator[generator] = {
            "count": len(selected),
            "max_deviation_percentile": mean_median([x["max_deviation_percentile"] for x in selected]),
            "atypical_fraction": mean_median([x["atypical_fraction"] for x in selected]),
            "spatial_pattern": dict(sorted(Counter(x["spatial_pattern"] for x in selected).items())),
        }
    if any(x["count"] != 100 for x in by_generator.values()):
        raise ValueError("unexpected eval generator counts")
    analysis = OUT / "analysis"
    statistics = {
        "pipeline_validity": {
            "eval_processed": len(summaries), "features_finite": True,
            "distances_finite": True, "crop_pixel_checks": crop_report,
            "baseline_parity": parity, "actor_facing_leak_matches": 0,
        },
        "reference_bank": {
            "images": 100, "patches": len(bank), "feature_dimension": bank.shape[1],
            "calibration_distance": {
                "min": float(calibration.min()), "mean": float(calibration.mean()),
                "median": float(np.median(calibration)), "p95": float(np.percentile(calibration, 95)),
                "max": float(calibration.max()),
            },
        },
        "by_generator": by_generator,
    }
    (analysis / "evidence_statistics.json").write_text(json.dumps(statistics, indent=2, ensure_ascii=False) + "\n")
    markdown = ["# PROBE Evidence v1 statistics", "",
                f"- Eval processed: {len(summaries)}/300",
                f"- Reference bank: 100 images, {len(bank)} patches, {bank.shape[1]} features",
                f"- Source-group-excluded calibration distance min/mean/median/p95/max: "
                f"{calibration.min():.6f}/{calibration.mean():.6f}/{np.median(calibration):.6f}/"
                f"{np.percentile(calibration, 95):.6f}/{calibration.max():.6f}",
                f"- Parity: {parity['prediction_matches']}/300; max probability difference {parity['max_probability_abs_error']:.9g}",
                f"- Crop reconstruction: {crop_report['pixel_matches']}/{crop_report['crops_checked']} crops",
                f"- Actor-facing forbidden-term matches: {len(leaks)}", "",
                "| Generator | Mean/median max percentile | Mean/median atypical fraction | Spatial patterns |",
                "| --- | --- | --- | --- |"]
    for generator, group in by_generator.items():
        p = group["max_deviation_percentile"]
        f = group["atypical_fraction"]
        markdown.append(f"| {generator} | {p['mean']:.2f}/{p['median']:.2f} | "
                        f"{f['mean']:.3f}/{f['median']:.3f} | {group['spatial_pattern']} |")
    (analysis / "evidence_statistics.md").write_text("\n".join(markdown) + "\n")

    with (ACTOR / "probe_predictions.csv").open(newline="") as stream:
        baseline = {x["sample_id"]: x for x in csv.DictReader(stream)}
    errors = [x for x in summaries if int(baseline[x["sample_id"]]["correct"]) == 0]
    failure_dir = analysis / "probe_failures"
    failure_dir.mkdir(exist_ok=True)
    failure_lines = ["# Original PROBE errors under frozen evidence", "",
                     f"Frozen eval classifier errors: {len(errors)}", "",
                     "The values below are descriptive; no evidence parameter was changed.", ""]
    for item in errors:
        sid = item["sample_id"]
        row = row_by_id[sid]
        stem = safe_stem(sid)
        card = json.loads((cards / f"{stem}.json").read_text())
        make_deviation_map(row, patches[sid], failure_dir / f"{stem}_deviation_map.png")
        make_sheet(row, card, [x["reference_deviation_percentile"] for x in patches[sid]],
                   failure_dir / f"{stem}_contact_sheet.png")
        failure_lines.extend([
            f"## {sid}", "",
            f"- True category: {row['generator']}; frozen classifier prediction: {baseline[sid]['prediction']} (incorrect).",
            f"- Atypical fraction: {item['atypical_fraction']:.3f}; spatial pattern: {item['spatial_pattern']}.",
            f"- Maximum percentile: {item['max_deviation_percentile']:.2f}.",
            f"- [Original and top-3 crops](probe_failures/{stem}_contact_sheet.png); "
            f"[deviation map](probe_failures/{stem}_deviation_map.png).", "",
        ])
    (analysis / "PROBE_FAILURE_EVIDENCE_ANALYSIS.md").write_text("\n".join(failure_lines) + "\n")

    qualitative_dir = analysis / "qualitative_contact_sheets"
    qualitative_dir.mkdir(exist_ok=True)
    rng = random.Random(20261005)
    audit_ids = []
    for generator in ("raise", "flux", "sd3_5"):
        candidates = sorted(x["sample_id"] for x in summaries if row_by_id[x["sample_id"]]["generator"] == generator)
        audit_ids.extend(rng.sample(candidates, 10))
    qualitative = ["# Stratified 30-image visual audit", "",
                   "Seed: 20261005; 10 RAISE, 10 FLUX, 10 SD3.5. "
                   "Review bbox, crop alignment, padding, edge concentration, and spatial statistics. "
                   "Use findings to identify pipeline bugs only.", ""]
    for sid in audit_ids:
        row = row_by_id[sid]
        stem = safe_stem(sid)
        card = json.loads((cards / f"{stem}.json").read_text())
        make_sheet(row, card, [x["reference_deviation_percentile"] for x in patches[sid]],
                   qualitative_dir / f"{stem}.png")
        qualitative.append(f"- {sid}: [contact sheet](qualitative_contact_sheets/{stem}.png); "
                           f"pattern `{card['observations']['spatial_pattern']}`")
    (analysis / "qualitative_audit.md").write_text("\n".join(qualitative) + "\n")
    print(json.dumps({"eval": len(summaries), "reference_patches": len(bank),
                      "classifier_errors": len(errors), "qualitative_sheets": len(audit_ids),
                      "actor_facing_leaks": len(leaks)}, indent=2))


if __name__ == "__main__":
    main()
