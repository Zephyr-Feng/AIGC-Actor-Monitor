"""Build the fixed authentic-reference kNN evidence branch after Stage A passes."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, deque
from pathlib import Path

import numpy as np
from PIL import Image

from extract_features import ACTOR, OUT, REFERENCE, manifest_rows, safe_stem


K = 20
ATYPICAL_PERCENTILE = 95.0


def knn_mean(query: np.ndarray, bank: np.ndarray, eligible: np.ndarray | None = None) -> np.ndarray:
    similarities = np.asarray(query @ bank.T, dtype=np.float64)
    distances = 1.0 - similarities
    if eligible is not None:
        distances[:, ~eligible] = np.inf
    if distances.shape[1] < K or np.sum(np.isfinite(distances[0])) < K:
        raise ValueError("fewer than 20 eligible authentic reference patches")
    # Stable sorting fixes a deterministic tie order by reference-bank index.
    return np.mean(np.sort(distances, axis=1, kind="stable")[:, :K], axis=1)


def spatial_pattern(mask: np.ndarray, rows: int, cols: int):
    active = set(np.flatnonzero(mask).tolist())
    if not active:
        return "none", 0, 0, 0.0
    remaining = set(active)
    component_sizes = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = deque([start])
        size = 0
        while queue:
            index = queue.popleft()
            size += 1
            row, col = divmod(index, cols)
            neighbors = []
            if row > 0: neighbors.append(index - cols)
            if row + 1 < rows: neighbors.append(index + cols)
            if col > 0: neighbors.append(index - 1)
            if col + 1 < cols: neighbors.append(index + 1)
            for neighbor in neighbors:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
        component_sizes.append(size)
    largest = max(component_sizes)
    fraction = largest / len(active)
    descriptor = "isolated" if largest == 1 else ("clustered" if fraction >= 0.5 else "dispersed")
    return descriptor, len(component_sizes), largest, fraction


def main():
    parity = json.loads((OUT / "analysis/parity_report.json").read_text())
    if not parity.get("pass"):
        raise RuntimeError("Stage A failed; do not build evidence")
    reference_rows = manifest_rows("reference")
    evaluation_rows = manifest_rows("eval")
    reference_groups = {x["source_group"] for x in reference_rows}
    eval_groups = {x["source_group"] for x in evaluation_rows}
    if reference_groups & eval_groups:
        raise ValueError("reference and evaluation source groups overlap")

    bank_features = []
    metadata = []
    for row in reference_rows:
        sid = row["sample_id"]
        with np.load(OUT / "work/reference" / f"{safe_stem(sid)}.npz") as record:
            features = record["features"].copy()
            grid = record["grid"].tolist()
        if not np.isfinite(features).all():
            raise ValueError(f"nonfinite reference feature: {sid}")
        bank_features.append(features)
        for patch_id in range(len(features)):
            grid_row, grid_col = divmod(patch_id, grid[1])
            metadata.append({"sample_id": sid, "source_group": row["source_group"],
                             "patch_id": patch_id, "grid_row": grid_row, "grid_col": grid_col})
    bank = np.concatenate(bank_features, axis=0)
    groups = np.asarray([x["source_group"] for x in metadata])
    ref_out = OUT / "reference_bank"
    ref_out.mkdir(parents=True, exist_ok=True)
    np.save(ref_out / "features.npy", bank)
    with (ref_out / "metadata.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metadata[0]))
        writer.writeheader()
        writer.writerows(metadata)
    calibration = np.empty(len(bank), dtype=np.float64)
    for group in sorted(reference_groups):
        query = groups == group
        eligible = groups != group
        calibration[query] = knn_mean(bank[query], bank, eligible)
    if not np.isfinite(calibration).all():
        raise ValueError("nonfinite authentic calibration distances")
    np.save(ref_out / "calibration_distribution.npy", calibration)
    calib_sorted = np.sort(calibration)
    (ref_out / "manifest.json").write_text(json.dumps({
        "reference_images": len(reference_rows), "reference_groups": len(reference_groups),
        "reference_patches": len(bank), "feature_dimension": bank.shape[1],
        "source_manifest_sha256": hashlib.sha256((REFERENCE / "manifest.jsonl").read_bytes()).hexdigest(),
        "k": K, "metric": "cosine_distance", "calibration": "source_group_excluded",
        "atypical_percentile_threshold": ATYPICAL_PERCENTILE,
    }, indent=2) + "\n")

    card_dir = OUT / "evidence/cards"
    crop_dir = OUT / "evidence/crops"
    for directory in (card_dir, crop_dir):
        directory.mkdir(parents=True, exist_ok=True)
    records_path = OUT / "evidence/patch_records.jsonl"
    summary_path = OUT / "evidence/image_statistics.jsonl"
    with records_path.open("w", encoding="utf-8") as records, summary_path.open("w", encoding="utf-8") as summaries:
        for index, row in enumerate(evaluation_rows, 1):
            sid = row["sample_id"]
            stem = safe_stem(sid)
            with np.load(OUT / "work/eval" / f"{stem}.npz") as record:
                features = record["features"].copy()
                boxes = record["boxes"].tolist()
                nrows, ncols = map(int, record["grid"])
            if not np.isfinite(features).all() or len(features) != nrows * ncols:
                raise ValueError(f"invalid evaluation features or grid: {sid}")
            distances = knn_mean(features, bank)
            percentiles = np.searchsorted(calib_sorted, distances, side="right") * 100.0 / len(calib_sorted)
            atypical = percentiles >= ATYPICAL_PERCENTILE
            pattern, count, largest, fraction = spatial_pattern(atypical, nrows, ncols)
            top = np.argsort(-percentiles, kind="stable")[:min(3, len(percentiles))]
            image = Image.open(OUT / "evidence/processed_images" / f"{stem}.png").convert("RGB")
            sample_crop_dir = crop_dir / stem
            sample_crop_dir.mkdir(parents=True, exist_ok=True)
            top_regions = []
            for rank, patch_id in enumerate(top, 1):
                bbox = boxes[int(patch_id)]
                relative = f"crops/{stem}/region_{rank:02d}.png"
                image.crop(tuple(bbox)).save(OUT / "evidence" / relative, format="PNG")
                grid_row, grid_col = divmod(int(patch_id), ncols)
                top_regions.append({"region_id": f"R{rank}", "patch_id": int(patch_id),
                                    "grid_row": grid_row, "grid_col": grid_col,
                                    "bbox": bbox, "deviation_percentile": float(percentiles[patch_id]),
                                    "crop_path": relative})
            for patch_id, (bbox, distance, percentile, is_atypical) in enumerate(
                    zip(boxes, distances, percentiles, atypical)):
                grid_row, grid_col = divmod(patch_id, ncols)
                records.write(json.dumps({
                    "sample_id": sid, "source_group": row["source_group"],
                    "patch_id": patch_id, "grid_row": grid_row, "grid_col": grid_col,
                    "processed_bbox": bbox, "deviation": float(distance),
                    "reference_deviation_percentile": float(percentile),
                    "atypical": bool(is_atypical),
                }, ensure_ascii=False) + "\n")
            summary = {
                "sample_id": sid, "source_group": row["source_group"],
                "num_patches": len(features), "num_atypical_patches": int(atypical.sum()),
                "atypical_fraction": float(atypical.mean()),
                "max_deviation_percentile": float(percentiles.max()),
                "median_deviation_percentile": float(np.median(percentiles)),
                "spatial_pattern": pattern,
                "connected_component_count": count,
                "largest_component_size": largest,
                "largest_component_fraction": fraction,
            }
            summaries.write(json.dumps(summary, ensure_ascii=False) + "\n")
            card = {
                "tool": "global_representation_analyzer", "evidence_type": "representation_deviation",
                "sample_id": sid, "scope": {"num_regions_examined": len(features)},
                "reference": {"type": "authentic_image_reference_bank", "distance_metric": "cosine_knn", "k": K},
                "observations": {
                    "num_atypical_regions": int(atypical.sum()),
                    "atypical_fraction": float(atypical.mean()),
                    "max_deviation_percentile": float(percentiles.max()),
                    "median_deviation_percentile": float(np.median(percentiles)),
                    "spatial_pattern": pattern,
                    "connected_component_count": count,
                    "largest_component_size": largest,
                    "largest_component_fraction": fraction,
                },
                "most_atypical_regions": top_regions,
                "limitations": [
                    "表征偏离只表示与真实参考图块的距离，不构成图像来源的证明。",
                    "罕见的真实内容或后处理也可能产生高偏离值。",
                    "该表征本身不能指认具体的物理伪造痕迹。",
                ],
            }
            card_file = card_dir / f"{stem}.json"
            card_file.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
            text_lines = [
                "PROBE 表征偏离证据", "", f"检查区域数：{len(features)}",
                f"高于真实参考校准分布第 95 百分位的区域：{int(atypical.sum())}/{len(features)}",
                f"空间模式：{pattern}", "", "偏离程度最高的区域：",
            ]
            for region in top_regions:
                text_lines.extend([f"{region['region_id']}：坐标 {region['bbox']}；"
                                   f"偏离百分位 {region['deviation_percentile']:.2f}；"
                                   f"图块 {region['crop_path']}"])
            text_lines.extend(["", "局限："] + card["limitations"])
            card_file.with_suffix(".txt").write_text("\n".join(text_lines) + "\n")
            print(f"evidence {index}/{len(evaluation_rows)} {sid}", flush=True)

    sample = random.Random(20261005).sample(evaluation_rows, 20)
    pixel_checks = 0
    for row in sample:
        stem = safe_stem(row["sample_id"])
        card = json.loads((card_dir / f"{stem}.json").read_text())
        processed = Image.open(OUT / "evidence/processed_images" / f"{stem}.png").convert("RGB")
        for region in card["most_atypical_regions"]:
            stored = Image.open(OUT / "evidence" / region["crop_path"]).convert("RGB")
            reconstructed = processed.crop(tuple(region["bbox"]))
            if not np.array_equal(np.asarray(stored), np.asarray(reconstructed)):
                raise ValueError(f"crop reconstruction mismatch: {row['sample_id']}")
            pixel_checks += 1
    (OUT / "analysis/crop_reconstruction.json").write_text(
        json.dumps({"seed": 20261005, "sampled_images": 20,
                    "crops_checked": pixel_checks, "pixel_matches": pixel_checks}, indent=2) + "\n")
    print(f"reference patches={len(bank)}; evidence images={len(evaluation_rows)}; crop pixel checks={pixel_checks}")


if __name__ == "__main__":
    main()
