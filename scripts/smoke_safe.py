"""Minimal official-order SAFE checkpoint and single-image execution check."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--image", type=Path, action="append", default=[])
    args = parser.parse_args()
    if len(args.image) > 3:
        parser.error("smoke is limited to three non-scoring images")

    sys.path.insert(0, str(args.source))
    from models.resnet import resnet50

    start = time.perf_counter()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = resnet50(num_classes=2)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().to(args.device)
    load_seconds = time.perf_counter() - start
    if args.device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    transform = transforms.Compose(
        [transforms.CenterCrop((256, 256)), transforms.ToTensor()]
    )
    results = []
    for path in args.image:
        start = time.perf_counter()
        with Image.open(path) as source_image:
            image = source_image.convert("RGB")
            input_size = image.size
            tensor = transform(image).unsqueeze(0).to(args.device)
        if args.device == "cuda":
            torch.cuda.synchronize()
        preprocess_seconds = time.perf_counter() - start
        start = time.perf_counter()
        with torch.inference_mode():
            logits = model(tensor)
        if args.device == "cuda":
            torch.cuda.synchronize()
        forward_seconds = time.perf_counter() - start
        results.append(
            {
                "image": str(path),
                "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "original_size": input_size,
                "logits_real_fake": logits[0].detach().cpu().tolist(),
                "fake_probability": logits.softmax(dim=1)[0, 1].item(),
                "preprocess_seconds": preprocess_seconds,
                "forward_seconds": forward_seconds,
            }
        )

    print(
        json.dumps(
            {
                "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                "strict_load": True,
                "device": args.device,
                "load_seconds": load_seconds,
                "peak_allocated_mib": (
                    torch.cuda.max_memory_allocated() / 1024**2
                    if args.device == "cuda"
                    else None
                ),
                "images": results,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
