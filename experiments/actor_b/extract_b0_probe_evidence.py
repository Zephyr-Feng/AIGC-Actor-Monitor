#!/usr/bin/env python3
"""Apply the frozen PROBE Evidence-only v1 branch to the Actor-B0 dev subset.

The checkpoint, preprocessing, reference bank, k, percentile threshold, patch
size, stride and card semantics are inherited unchanged from Evidence-only v1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import deque
from pathlib import Path


CROP_SIZE = 336
K = 20
ATYPICAL_PERCENTILE = 95.0


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def spatial_pattern(mask, rows: int, cols: int):
    import numpy as np
    active = set(np.flatnonzero(mask).tolist())
    if not active:
        return "none", 0, 0, 0.0
    remaining, sizes = set(active), []
    while remaining:
        queue, size = deque([remaining.pop()]), 0
        while queue:
            index = queue.popleft()
            size += 1
            row, col = divmod(index, cols)
            neighbors = ([index - cols] if row else []) + ([index + cols] if row + 1 < rows else [])
            neighbors += ([index - 1] if col else []) + ([index + 1] if col + 1 < cols else [])
            for neighbor in neighbors:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
        sizes.append(size)
    largest = max(sizes)
    fraction = largest / len(active)
    label = "isolated" if largest == 1 else ("clustered" if fraction >= 0.5 else "dispersed")
    return label, len(sizes), largest, fraction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--probe-detector-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dinov2-config", type=Path, required=True)
    parser.add_argument("--reference-bank-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    import numpy as np
    import torch
    import torchvision.transforms as transforms
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 is required for frozen PROBE feature extraction")
    sys.path.insert(0, str(args.probe_detector_dir))
    from model.dino_classifier import dino_classifier
    from util import data_augment

    bank = np.load(args.reference_bank_dir / "features.npy")
    calibration = np.load(args.reference_bank_dir / "calibration_distribution.npy")
    reference_manifest = json.loads((args.reference_bank_dir / "manifest.json").read_text(encoding="utf-8"))
    expected = {"k": K, "atypical_percentile_threshold": ATYPICAL_PERCENTILE,
                "metric": "cosine_distance", "reference_images": 100, "reference_patches": 600}
    for key, value in expected.items():
        if reference_manifest.get(key) != value:
            raise ValueError(f"reference bank mismatch for {key}")

    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    model = dino_classifier(classifier_type="linear", model_name=str(args.dinov2_config))
    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model = model.to("cuda").eval()
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    augment = {
        "blur_prob": 0.0, "blur_sig_min": 0.0, "blur_sig_max": 3.0, "blur_sig": 0.0,
        "jpeg_prob": 0.0, "jpeg_quality_min": 60, "jpeg_quality_max": 100, "jpeg_quality": 100,
        "cutout_prob": 0.0, "cutout_ratio_min": 0.1, "cutout_ratio_max": 0.5,
        "noise_prob": 0.0, "noise_std_min": 0.0, "noise_std_max": 50.0, "noise_std": 0.0,
        "resize_prob": 0.0, "resize_scale_min": 0.5, "resize_scale_max": 2.0,
        "resize_scale": 1.0, "pad_mode": "repeat",
    }
    cards = args.output_dir / "cards"
    crops = args.output_dir / "crops"
    processed_dir = args.output_dir / "processed_images"
    for directory in (cards, crops, processed_dir):
        directory.mkdir(parents=True, exist_ok=True)
    calib_sorted = np.sort(calibration)
    rows = read_jsonl(args.manifest)
    with torch.no_grad():
        for number, row in enumerate(rows, 1):
            sid, stem = row["sample_id"], row["sample_id"].replace(":", "__")
            source = args.image_root / row["relative_path"]
            if sha256(source) != row["sha256"]:
                raise ValueError(f"image SHA mismatch: {sid}")
            image = Image.open(source).convert("RGB")
            processed = data_augment(image, data_augment_params=augment, mode="fix", crop_size=CROP_SIZE)
            tensor = transform(processed)
            channels, height, width = tensor.shape
            patches = tensor.unfold(1, CROP_SIZE, CROP_SIZE).unfold(2, CROP_SIZE, CROP_SIZE)
            patches = patches.permute(1, 2, 0, 3, 4).contiguous().view(-1, channels, CROP_SIZE, CROP_SIZE)
            nrows, ncols = height // CROP_SIZE, width // CROP_SIZE
            boxes = [[col * CROP_SIZE, grid_row * CROP_SIZE, (col + 1) * CROP_SIZE,
                      (grid_row + 1) * CROP_SIZE] for grid_row in range(nrows) for col in range(ncols)]
            _, features = model(patches.to("cuda"), return_feature=True)
            features = features.cpu().numpy().astype(np.float32)
            features /= np.linalg.norm(features, axis=1, keepdims=True)
            distances = 1.0 - np.asarray(features @ bank.T, dtype=np.float64)
            knn = np.mean(np.sort(distances, axis=1, kind="stable")[:, :K], axis=1)
            percentiles = np.searchsorted(calib_sorted, knn, side="right") * 100.0 / len(calib_sorted)
            atypical = percentiles >= ATYPICAL_PERCENTILE
            pattern, count, largest, fraction = spatial_pattern(atypical, nrows, ncols)
            processed.save(processed_dir / f"{stem}.png", format="PNG")
            sample_crop_dir = crops / stem
            sample_crop_dir.mkdir(parents=True, exist_ok=True)
            regions = []
            for rank, patch_id in enumerate(np.argsort(-percentiles, kind="stable")[:3], 1):
                bbox = boxes[int(patch_id)]
                relative = f"crops/{stem}/region_{rank:02d}.png"
                processed.crop(tuple(bbox)).save(args.output_dir / relative, format="PNG")
                grid_row, grid_col = divmod(int(patch_id), ncols)
                regions.append({"region_id": f"R{rank}", "patch_id": int(patch_id),
                                "grid_row": grid_row, "grid_col": grid_col, "bbox": bbox,
                                "deviation_percentile": float(percentiles[patch_id]), "crop_path": relative})
            card = {
                "tool": "global_forensic_analyzer", "evidence_type": "representation_deviation",
                "sample_id": sid, "scope": {"num_regions_examined": len(features)},
                "reference": {"type": "authentic_image_reference_bank", "distance_metric": "cosine_knn", "k": K},
                "observations": {"num_atypical_regions": int(atypical.sum()),
                                 "atypical_fraction": float(atypical.mean()),
                                 "max_deviation_percentile": float(percentiles.max()),
                                 "median_deviation_percentile": float(np.median(percentiles)),
                                 "spatial_pattern": pattern, "connected_component_count": count,
                                 "largest_component_size": largest, "largest_component_fraction": fraction},
                "most_atypical_regions": regions,
                "limitations": ["表征偏离只表示与真实参考图块的距离，不构成图像来源的证明。",
                                "罕见的真实内容或后处理也可能产生高偏离值。",
                                "该表征本身不能指认具体的物理伪造痕迹。"],
            }
            (cards / f"{stem}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"evidence {number}/{len(rows)} {sid}", flush=True)
    runtime = {"records": len(rows), "checkpoint_sha256": sha256(args.checkpoint),
               "reference_features_sha256": sha256(args.reference_bank_dir / "features.npy"),
               "reference_calibration_sha256": sha256(args.reference_bank_dir / "calibration_distribution.npy"),
               "manifest_sha256": sha256(args.manifest), "k": K,
               "atypical_percentile_threshold": ATYPICAL_PERCENTILE, "crop_size": CROP_SIZE}
    (args.output_dir / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

