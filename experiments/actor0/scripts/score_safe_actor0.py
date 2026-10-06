#!/usr/bin/env python3
"""Score the frozen PROBE B-Free manifest with the already-installed SAFE model."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=300)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines()]
    if len(rows) != args.expected_count or len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError(f"manifest must contain {args.expected_count} unique images; got {len(rows)}")
    for row in rows:
        image = args.dataset / row["relative_path"]
        if sha256(image) != row["sha256"]:
            raise ValueError(f"image hash mismatch: {row['sample_id']}")

    metadata = {
        "purpose": "frozen Actor-0 B-Free tool-score set",
        "manifest_sha256": sha256(args.manifest),
        "checkpoint_sha256": sha256(args.checkpoint),
        "source_commit": "4e998724651b227def64f5be0cd60c0aa1552c35",
        "preprocessing": "RGB, CenterCrop(256), ToTensor()",
        "score": "softmax(logits)[1] = fake probability",
        "device": "cuda",
    }
    meta_path = args.output.with_suffix(".meta.json")
    if args.output.exists() or meta_path.exists():
        raise FileExistsError(f"refusing to overwrite an existing SAFE result: {args.output}")

    import torch
    from PIL import Image
    from torchvision import transforms

    sys.path.insert(0, str(args.source.resolve()))
    from models.resnet import resnet50

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = resnet50(num_classes=2)
    model.load_state_dict(checkpoint["model"], strict=True)
    del checkpoint
    model.eval().to("cuda")
    torch.cuda.reset_peak_memory_stats()
    transform = transforms.Compose([transforms.CenterCrop((256, 256)), transforms.ToTensor()])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    with args.output.open("w", encoding="utf-8") as stream:
        for index, row in enumerate(rows, 1):
            start = time.perf_counter()
            image_path = args.dataset / row["relative_path"]
            with Image.open(image_path) as source_image:
                tensor = transform(source_image.convert("RGB")).unsqueeze(0).to("cuda")
            with torch.inference_mode():
                logits = model(tensor)
            torch.cuda.synchronize()
            result = {
                "sample_id": row["sample_id"],
                "source_group": row["source_group"],
                "generator": row["generator"],
                "label": row["label"],
                "image_sha256": row["sha256"],
                "logits_real_fake": logits[0].detach().cpu().tolist(),
                "fake_probability": logits.softmax(dim=1)[0, 1].item(),
                "score_seconds": time.perf_counter() - start,
            }
            stream.write(json.dumps(result) + "\n")
            stream.flush()
            if index % 20 == 0 or index == len(rows):
                print(json.dumps({"event": "progress", "completed": index, "total": len(rows)}), flush=True)
    print(json.dumps({"event": "complete", "count": len(rows), "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20}), flush=True)


if __name__ == "__main__":
    main()
