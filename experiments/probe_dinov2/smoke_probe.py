#!/usr/bin/env python3
"""Strict-load PROBE and score one frozen 336px patch before full inference."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--deps", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(args.deps.resolve()))
    sys.path.insert(0, str(args.repo.resolve() / "Detector"))
    import torch
    from PIL import Image
    from torchvision import transforms
    from model.dino_classifier import dino_classifier

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    started = time.perf_counter()
    model = dino_classifier(classifier_type="linear", model_name=str(args.config.resolve()))
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True, mmap=True)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    del checkpoint
    model.eval().to("cuda")
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    with Image.open(args.image) as image:
        rgb = image.convert("RGB")
        patch = rgb.crop((0, 0, 336, 336))
    tensor = transform(patch).unsqueeze(0).to("cuda")
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        logit = float(model(tensor).reshape(-1)[0].item())
    torch.cuda.synchronize()
    result = {
        "strict_checkpoint_load": True,
        "image": str(args.image),
        "raw_patch_logit": logit,
        "fake_probability": 1 / (1 + __import__("math").exp(-logit)),
        "seconds": round(time.perf_counter() - started, 3),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
