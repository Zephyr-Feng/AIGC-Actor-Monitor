#!/usr/bin/env python3
"""Run IBM/RIGID's official ViT-L/14 stability score on a manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import time
from pathlib import Path


FIELDS = [
    "path", "relative_path", "sample_id", "source_group", "ground_truth", "generator",
    "similarity_score", "perturbation_mean", "perturbation_std", "raw_decision_score",
    "prediction", "correct",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--torch-home", type=Path, required=True)
    parser.add_argument("--name", choices=("calibration", "full"), required=True)
    parser.add_argument("--threshold-json", type=Path)
    args = parser.parse_args()

    records = read_manifest(args.manifest)
    if not records:
        raise ValueError("Manifest is empty")
    if args.name == "full" and len(records) != 300:
        raise ValueError(f"RIGID final run requires all 300 frozen samples, got {len(records)}")
    if args.name == "calibration" and len({r["source_group"] for r in records}) < 20:
        raise ValueError("Calibration must contain at least 20 source groups")

    run_root = args.run_root.resolve()
    output_csv = run_root / ("predictions.csv" if args.name == "full" else "calibration_predictions.csv")
    raw_jsonl = run_root / "raw_outputs" / f"{args.name}_raw_scores.jsonl"
    config_path = run_root / "raw_outputs" / f"{args.name}_config.json"
    for path in (output_csv, raw_jsonl, config_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    args.image_root = args.image_root.resolve()
    args.torch_home = args.torch_home.resolve()
    hub_repo = args.torch_home / "hub" / "facebookresearch_dinov2_main"
    checkpoint = args.torch_home / "hub" / "checkpoints" / "dinov2_vitl14_pretrain.pth"
    if not (hub_repo / "hubconf.py").is_file():
        raise FileNotFoundError(f"Official DINOv2 torch hub cache missing: {hub_repo / 'hubconf.py'}")
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Official DINOv2 checkpoint missing: {checkpoint}")

    threshold = None
    if args.threshold_json:
        threshold_payload = json.loads(args.threshold_json.read_text(encoding="utf-8"))
        threshold = float(threshold_payload["threshold_similarity"])

    os.environ["TORCH_HOME"] = str(args.torch_home)
    import numpy as np
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms

    seed = 100
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    # Exact transform from IBM/RIGID.ipynb.
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])

    class ImageFolderWithPath(datasets.ImageFolder):
        def __getitem__(self, index):
            image, target = super().__getitem__(index)
            return image, target, self.samples[index][0]

    dataset = ImageFolderWithPath(root=str(args.image_root), transform=transform)
    class_dir_for_generator = {"raise": "real", "flux": "fake_flux", "sd3_5": "fake_sd35"}
    record_by_identity = {}
    for record in records:
        path = (args.image_root / class_dir_for_generator[record["generator"]] / f"{record['source_group']}.png").resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        record_by_identity[(class_dir_for_generator[record["generator"]], record["source_group"])] = record
    if len(dataset) != len(records):
        raise ValueError(f"ImageFolder saw {len(dataset)} images; manifest has {len(records)}")

    class RIGIDDetector:
        def __init__(self, lamb=0.05, percentile=5):
            self.lamb = lamb
            # This is IBM/RIGID's original Hub call. The exact upstream repo and
            # official checkpoint are pre-populated in the isolated torch cache.
            self.model = torch.hub.load("facebookresearch/dinov2", "dinov2_vitl14").cuda()
            self.model.eval()

        @torch.no_grad()
        def calculate_sim(self, data):
            features = self.model(data)
            noise = torch.randn_like(data).to(data.device)
            trans_data = data + noise * self.lamb
            trans_features = self.model(trans_data)
            return F.cosine_similarity(features, trans_features, dim=-1)

        @torch.no_grad()
        def detect(self, data):
            return self.calculate_sim(data)

    detector = RIGIDDetector(lamb=0.05, percentile=5)
    loader = DataLoader(dataset, batch_size=256, shuffle=True, num_workers=2)
    config = {
        "tool": "RIGID",
        "source": "IBM/RIGID",
        "manifest_sha256": sha256(args.manifest),
        "dino_checkpoint_sha256": sha256(checkpoint),
        "seed": seed,
        "backbone": "facebookresearch/dinov2:dinov2_vitl14",
        "transform": "Resize((224,224)), ToTensor(), ImageNet Normalize(mean=(0.485,0.456,0.406), std=(0.229,0.224,0.225))",
        "noise": {"distribution": "standard_normal", "space": "normalized tensor", "lambda": 0.05, "draws_per_image": 1},
        "similarity": "cosine_similarity(original_features, perturbed_features, dim=-1)",
        "batch_size": 256,
        "shuffle": True,
        "num_workers": 2,
        "fake_direction": "lower similarity indicates more synthetic; raw_decision_score = -similarity",
        "threshold_similarity": threshold,
        "threshold_source": str(args.threshold_json.resolve()) if args.threshold_json else None,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    cursor = 0
    failures = 0
    with output_csv.open("x", newline="", encoding="utf-8") as csv_file, raw_jsonl.open("x", encoding="utf-8") as raw_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        for batch_index, (images, _, paths) in enumerate(loader, start=1):
            images = images.cuda()
            with torch.no_grad():
                similarities = detector.calculate_sim(images)
            torch.cuda.synchronize()
            similarities = similarities.detach().cpu().tolist()
            for path, similarity in zip(paths, similarities):
                path_obj = Path(path).resolve()
                record = record_by_identity[(path_obj.parent.name, path_obj.stem)]
                finite = math.isfinite(similarity)
                if not finite:
                    failures += 1
                prediction = int(similarity < threshold) if finite and threshold is not None else ""
                row = {
                    "path": str(path_obj),
                    "relative_path": record["relative_path"],
                    "sample_id": record["sample_id"],
                    "source_group": record["source_group"],
                    "ground_truth": int(record["label_id"]),
                    "generator": record["generator"],
                    "similarity_score": similarity,
                    "perturbation_mean": similarity,
                    "perturbation_std": "",
                    "raw_decision_score": -similarity if finite else "",
                    "prediction": prediction,
                    "correct": int(prediction == int(record["label_id"])) if prediction != "" else "",
                }
                writer.writerow(row)
                raw_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            cursor += len(paths)
            csv_file.flush()
            raw_file.flush()
            print(f"batch={batch_index}/{len(loader)} images={cursor}/{len(records)} failures={failures}", flush=True)

    elapsed = time.perf_counter() - start
    summary = {
        "images": cursor,
        "nonfinite_scores": failures,
        "seconds": elapsed,
        "seconds_per_image": elapsed / max(cursor, 1),
        "peak_vram_mib": torch.cuda.max_memory_allocated() / (1024 ** 2),
    }
    (run_root / "raw_outputs" / f"{args.name}_runtime.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    if failures:
        raise RuntimeError(f"Found {failures} non-finite RIGID similarities")


if __name__ == "__main__":
    main()
