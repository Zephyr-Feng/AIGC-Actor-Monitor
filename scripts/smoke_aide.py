#!/usr/bin/env python3
"""Load an external AIDE checkpoint and optionally score one image."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aide-repo", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--deps-dir", type=Path, required=True)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--repeats", type=int, default=1)
    return parser.parse_args()


def prepare_image(image_path: Path):
    import torch
    from PIL import Image
    from torchvision import transforms
    from data.dct import DCT_base_Rec_Module

    image = transforms.ToTensor()(Image.open(image_path).convert("RGB"))
    dct = DCT_base_Rec_Module()
    x_min, x_max, x_min_1, x_max_1 = dct(image)
    transform = transforms.Compose(
        [
            transforms.Resize([256, 256]),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )
    return torch.stack(
        [
            transform(x_min),
            transform(x_max),
            transform(x_min_1),
            transform(x_max_1),
            transform(image),
        ],
        dim=0,
    ).unsqueeze(0)


def main() -> None:
    args = parse_args()
    if args.repeats < 1:
        raise ValueError("--repeats must be positive")

    sys.path.insert(0, str(args.deps_dir.resolve()))
    sys.path.insert(0, str(args.aide_repo.resolve()))

    import torch
    from models.AIDE import AIDE

    started = time.perf_counter()
    model = AIDE(resnet_path=None, convnext_path=None)
    checkpoint = torch.load(
        args.checkpoint.resolve(),
        map_location="cpu",
        weights_only=False,
    )
    state_dict = checkpoint["model"] if "model" in checkpoint else checkpoint
    model.load_state_dict(state_dict, strict=True)
    del checkpoint, state_dict
    gc.collect()

    model.eval().to(args.device)
    result: dict[str, object] = {
        "device": args.device,
        "load_seconds": time.perf_counter() - started,
        "checkpoint": str(args.checkpoint.resolve()),
    }

    if args.image:
        prepare_started = time.perf_counter()
        image = prepare_image(args.image.resolve()).to(args.device)
        if args.device == "cuda":
            torch.cuda.synchronize()
        prepare_seconds = time.perf_counter() - prepare_started
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()

        runs: list[dict[str, object]] = []
        with torch.inference_mode():
            for _ in range(args.repeats):
                if args.device == "cuda":
                    torch.cuda.synchronize()
                started = time.perf_counter()
                logits = model(image)
                if args.device == "cuda":
                    torch.cuda.synchronize()
                probabilities = torch.softmax(logits, dim=1)
                runs.append(
                    {
                        "score_seconds": time.perf_counter() - started,
                        "prepare_seconds": prepare_seconds,
                        "end_to_end_seconds": prepare_seconds + time.perf_counter() - started,
                        "logits": logits[0].detach().cpu().tolist(),
                        "fake_probability": probabilities[0, 1].item(),
                        "label": "fake" if probabilities[0, 1].item() > 0.5 else "real",
                    }
                )

        result.update(
            {
                "image": str(args.image.resolve()),
                "runs": runs,
            }
        )
        if args.device == "cuda":
            result["peak_allocated_mib"] = torch.cuda.max_memory_allocated() / 2**20

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
