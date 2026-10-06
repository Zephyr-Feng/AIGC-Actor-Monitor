"""Frozen PROBE inference with an additional CLS-feature export.

Run the evaluation split first. The analysis script enforces parity before this
script may be run for the authentic reference split.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image


DATA_ROOT = Path("/root/autodl-tmp")
ACTOR = DATA_ROOT / "actor0-bfree-20261002"
PROBE = DATA_ROOT / "probe-dinov2-bfree-20261001"
REFERENCE = DATA_ROOT / "probe-evidence-v1/reference_source"
OUT = Path(os.environ.get("PROBE_EVIDENCE_OUT", DATA_ROOT / "probe-evidence-v1/output"))
OFFICIAL = PROBE / "src/probe/PROBE-AIGI-Detection-b145f7130004c02725e9b3703954a3329ebf56de/Detector"
sys.path.insert(0, str(OFFICIAL))

from model.dino_classifier import dino_classifier  # noqa: E402
from util import data_augment  # noqa: E402


CROP_SIZE = 336
AUGMENT = {
    "blur_prob": 0.0, "blur_sig_min": 0.0, "blur_sig_max": 3.0,
    "blur_sig": 0.0, "jpeg_prob": 0.0, "jpeg_quality_min": 60,
    "jpeg_quality_max": 100, "jpeg_quality": 100, "cutout_prob": 0.0,
    "cutout_ratio_min": 0.1, "cutout_ratio_max": 0.5,
    "noise_prob": 0.0, "noise_std_min": 0.0, "noise_std_max": 50.0,
    "noise_std": 0.0, "resize_prob": 0.0, "resize_scale_min": 0.5,
    "resize_scale_max": 2.0, "resize_scale": 1.0, "pad_mode": "repeat",
}
TRANSFORM = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def manifest_rows(split: str) -> list[dict]:
    if split == "eval":
        manifest = ACTOR / "manifests/actor0_all_manifest.jsonl"
        rows = {x["sample_id"]: x for x in map(json.loads, manifest.read_text().splitlines())
                if x["split"] == "evaluation"}
        with (ACTOR / "probe_predictions.csv").open(newline="") as stream:
            order = [x["sample_id"] for x in csv.DictReader(stream) if x["sample_id"] in rows]
        if len(order) != len(rows) or len(set(order)) != len(order):
            raise ValueError("frozen PROBE scores do not align 1:1 with Actor eval")
        return [rows[sid] for sid in order]
    manifest = REFERENCE / "manifest.jsonl"
    return [x for x in map(json.loads, manifest.read_text().splitlines())
            if x["split"] == "calibration" and x["generator"] == "raise"]


def image_path(split: str, row: dict) -> Path:
    return (ACTOR / "data" if split == "eval" else REFERENCE) / row["relative_path"]


def safe_stem(sample_id: str) -> str:
    return sample_id.replace(":", "__")


def patch_input(path: Path):
    # These calls and constants mirror official EvaluateDataset.__getitem__ and
    # generate_sliding_patches. The returned PIL image is exactly the image on
    # which the official transform and patch generator operate.
    image = Image.open(path).convert("RGB")
    processed = data_augment(image, data_augment_params=AUGMENT,
                             mode="fix", crop_size=CROP_SIZE)
    tensor = TRANSFORM(processed)
    channels, height, width = tensor.shape
    assert height >= CROP_SIZE and width >= CROP_SIZE
    patches = tensor.unfold(1, CROP_SIZE, CROP_SIZE).unfold(2, CROP_SIZE, CROP_SIZE)
    patches = patches.permute(1, 2, 0, 3, 4).contiguous()
    patches = patches.view(-1, channels, CROP_SIZE, CROP_SIZE)
    nrows, ncols = height // CROP_SIZE, width // CROP_SIZE
    boxes = [[col * CROP_SIZE, row * CROP_SIZE,
              (col + 1) * CROP_SIZE, (row + 1) * CROP_SIZE]
             for row in range(nrows) for col in range(ncols)]
    assert len(boxes) == patches.shape[0]
    return processed, patches, boxes, nrows, ncols


def load_model():
    torch.manual_seed(42)
    torch.cuda.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    np.random.seed(42)
    random.seed(42)
    torch.backends.cudnn.deterministic = False
    torch.backends.cudnn.benchmark = True
    model = dino_classifier(
        classifier_type="linear", model_name=str(PROBE / "src/probe/dinov2_config.json")
    )
    checkpoint = torch.load(
        PROBE / "weights/DINOv2_best_model_step_34999.pth", map_location="cpu"
    )
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model = model.to("cuda")
    return model.eval()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("eval", "reference"), required=True)
    args = parser.parse_args()
    split = args.split
    rows = manifest_rows(split)
    assert len(rows) == (300 if split == "eval" else 100)
    if split == "reference":
        eval_groups = {x["source_group"] for x in manifest_rows("eval")}
        if eval_groups & {x["source_group"] for x in rows}:
            raise ValueError("authentic reference groups overlap evaluation")
    if split == "reference" and not (OUT / "analysis/parity_report.json").exists():
        raise RuntimeError("Stage A parity report is missing; reference extraction is blocked")
    if split == "reference":
        parity = json.loads((OUT / "analysis/parity_report.json").read_text())
        if not parity.get("pass"):
            raise RuntimeError("Stage A parity failed; reference extraction is blocked")
    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 is not available; extraction requires GPU")

    audit_dir = OUT / "audit"
    work_dir = OUT / "work" / split
    processed_dir = OUT / "evidence/processed_images" if split == "eval" else OUT / "reference_bank/processed_images"
    for path in (audit_dir, work_dir, processed_dir):
        path.mkdir(parents=True, exist_ok=True)
    output_path = audit_dir / f"{split}_classifier_internal_outputs.jsonl"
    existing = {}
    if output_path.exists():
        for line in output_path.read_text().splitlines():
            record = json.loads(line)
            existing[record["sample_id"]] = record
    model = load_model()
    print(f"split={split} rows={len(rows)} completed={len(existing)}", flush=True)

    with output_path.open("a", encoding="utf-8") as stream, torch.no_grad():
        for number, row in enumerate(rows, 1):
            sid = row["sample_id"]
            stem = safe_stem(sid)
            feature_path = work_dir / f"{stem}.npz"
            processed_path = processed_dir / f"{stem}.png"
            if sid in existing and feature_path.exists() and processed_path.exists():
                continue
            source = image_path(split, row)
            if hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError(f"image SHA-256 mismatch: {sid}")
            processed, patches, boxes, nrows, ncols = patch_input(source)
            logits, features = model(patches.to("cuda"), return_feature=True)
            logits = logits.squeeze(-1)
            image_logit = logits.mean()
            image_probability = image_logit.sigmoid()
            logits_array = logits.cpu().numpy().astype(np.float32)
            features_array = features.cpu().numpy().astype(np.float32)
            if not np.isfinite(features_array).all() or not np.isfinite(logits_array).all():
                raise ValueError(f"non-finite model output: {sid}")
            norms = np.linalg.norm(features_array, axis=1, keepdims=True)
            if not np.isfinite(norms).all() or (norms <= 0).any():
                raise ValueError(f"invalid CLS feature norm: {sid}")
            normalized = features_array / norms
            np.savez_compressed(feature_path, features=normalized, boxes=np.asarray(boxes, dtype=np.int32),
                                grid=np.asarray([nrows, ncols], dtype=np.int32))
            processed.save(processed_path, format="PNG")
            audit = {
                "sample_id": sid, "split": split, "source_group": row["source_group"],
                "patch_count": len(boxes), "patch_logits": logits_array.tolist(),
                "image_logit": float(image_logit.cpu().item()),
                "image_probability": float(image_probability.cpu().item()),
                "prediction": int(image_probability.cpu().item() > 0.5),
                "source_sha256": row["sha256"],
            }
            stream.write(json.dumps(audit, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"{split} {number}/{len(rows)} {sid} patches={len(boxes)}", flush=True)


if __name__ == "__main__":
    main()
