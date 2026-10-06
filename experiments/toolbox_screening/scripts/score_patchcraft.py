#!/usr/bin/env python3
"""Score a manifest with the official ModelScope PatchCraft test pipeline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path


FIELDS = [
    "path", "relative_path", "sample_id", "source_group", "ground_truth", "generator",
    "raw_logit", "raw_score", "normalized_score", "prediction", "correct",
]


def file_sha256(path: Path) -> str:
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
    parser.add_argument("--official-source", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--name", choices=("sanity", "full"), required=True)
    args = parser.parse_args()

    records = read_manifest(args.manifest)
    if not records:
        raise ValueError("Manifest is empty")
    if args.name == "sanity":
        counts = {g: sum(r["generator"] == g for r in records) for g in ("raise", "flux", "sd3_5")}
        if counts != {"raise": 5, "flux": 5, "sd3_5": 5}:
            raise ValueError(f"Sanity set must contain 5 images per generator: {counts}")
    elif len(records) != 300:
        raise ValueError(f"Full run requires all 300 frozen images, got {len(records)}")

    run_root = args.run_root.resolve()
    output_csv = run_root / ("predictions.csv" if args.name == "full" else "sanity_predictions.csv")
    raw_jsonl = run_root / "raw_outputs" / f"{args.name}_raw_scores.jsonl"
    config_path = run_root / "raw_outputs" / f"{args.name}_config.json"
    layout = run_root / "data" / f"{args.name}_official_layout"
    for path in (output_csv, raw_jsonl, config_path, layout):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {path}")

    args.official_source = args.official_source.resolve()
    args.image_root = args.image_root.resolve()
    args.checkpoint = args.checkpoint.resolve()
    if not args.checkpoint.is_file():
        raise FileNotFoundError(args.checkpoint)

    # The official reader requires 0_real / 1_fake folders. Symlinks preserve the
    # original PNG bytes and filenames are unique across the two fake generators.
    alias_to_record: dict[str, dict] = {}
    for record in records:
        relative = Path(record["relative_path"])
        source = args.image_root / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        label_dir = "0_real" if int(record["label_id"]) == 0 else "1_fake"
        alias = f"{record['generator']}_{record['source_group']}.png"
        destination = layout / label_dir / alias
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source)
        alias_to_record[alias] = record

    sys.path.insert(0, str(args.official_source))
    # Match eval_all.py's global seed and default CLI configuration.
    sys.argv = [sys.argv[0]]
    os.chdir(run_root)
    from PIL import ImageFile
    import torch
    from data import create_dataloader_new
    from networks import Net as RPTC, initWeights
    from options import TestOptions
    from util import set_random_seed

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    set_random_seed(42)
    opt = TestOptions().parse(print_options=False)
    opt.dataroot = str(layout)
    opt.model_path = str(args.checkpoint)
    opt.isTrain = False
    opt.isVal = False
    opt.noise_type = None

    model = RPTC()
    model.apply(initWeights)
    state_dict = torch.load(opt.model_path, map_location="cpu")
    try:
        model.load_state_dict(state_dict["netC"], strict=True)
    except Exception:
        model.load_state_dict({k.replace("module.", ""): v for k, v in state_dict["netC"].items()})
    model.cuda()
    model.eval()

    loader = create_dataloader_new(opt)
    dataset = loader.dataset
    if len(dataset) != len(records):
        raise ValueError(f"Official reader saw {len(dataset)} files; manifest has {len(records)}")
    dataset_records = [alias_to_record[Path(path).name] for path in dataset.img]
    config = {
        "tool": "PatchCraft",
        "source": "aemilia/AIGCDetectionBenchMark/PatchCraft",
        "manifest_sha256": file_sha256(args.manifest),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "seed": 42,
        "official_defaults": {
            "loadSize": opt.loadSize,
            "patch_num": opt.patch_num,
            "batch_size": opt.batch_size,
            "noise_type": None,
            "input_transform": "official read_data_new -> processing_RPTC; RGB uint8 to [0,1] tensor; 3*8*8 random 32x32 crops sorted by pixel-difference energy into poor/rich grids",
            "score": "sigmoid(logit), higher means fake; official prediction is score > 0.5",
        },
        "ordered_sample_ids": [r["sample_id"] for r in dataset_records],
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    failures = 0
    cursor = 0
    with output_csv.open("x", newline="", encoding="utf-8") as csv_file, raw_jsonl.open("x", encoding="utf-8") as raw_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        for batch_index, (images, labels) in enumerate(loader, start=1):
            batch_records = dataset_records[cursor:cursor + len(labels)]
            cursor += len(labels)
            if len(batch_records) != len(labels):
                raise RuntimeError("Batch/path alignment failed")
            with torch.no_grad():
                logits = model(images.cuda()).flatten()
                scores = torch.sigmoid(logits)
            torch.cuda.synchronize()
            logits_cpu = logits.detach().cpu().tolist()
            scores_cpu = scores.detach().cpu().tolist()
            labels_cpu = labels.detach().cpu().tolist()
            for record, logit, score, observed_label in zip(batch_records, logits_cpu, scores_cpu, labels_cpu):
                finite = math.isfinite(logit) and math.isfinite(score)
                if not finite:
                    failures += 1
                prediction = int(score > 0.5) if finite else ""
                row = {
                    "path": str(args.image_root / record["relative_path"]),
                    "relative_path": record["relative_path"],
                    "sample_id": record["sample_id"],
                    "source_group": record["source_group"],
                    "ground_truth": int(record["label_id"]),
                    "generator": record["generator"],
                    "raw_logit": logit,
                    "raw_score": score,
                    "normalized_score": score,
                    "prediction": prediction,
                    "correct": int(prediction == int(record["label_id"])) if finite else "",
                }
                if int(observed_label) != int(record["label_id"]):
                    raise RuntimeError(f"Directory label mismatch for {record['sample_id']}")
                writer.writerow(row)
                raw_file.write(json.dumps(row, ensure_ascii=False) + "\n")
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
    (run_root / "raw_outputs" / f"{args.name}_runtime.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    if failures:
        raise RuntimeError(f"Found {failures} non-finite PatchCraft scores")


if __name__ == "__main__":
    main()
