#!/usr/bin/env python3
"""Load an external FSD checkout and optionally score one image."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fsd-repo", type=Path, required=True)
    parser.add_argument("--weights-dir", type=Path, required=True)
    parser.add_argument("--deps-dir", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.deps_dir:
        sys.path.insert(0, str(args.deps_dir.resolve()))
    sys.path.insert(0, str(args.fsd_repo.resolve()))

    import torch
    from fsd import FSDDetector

    started = time.perf_counter()
    detector = FSDDetector.load(
        weights_dir=args.weights_dir.resolve(),
        device=args.device,
    )
    result: dict[str, object] = {
        "device": args.device,
        "load_seconds": time.perf_counter() - started,
        "weights_dir": str(args.weights_dir.resolve()),
    }

    if args.image:
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        started = time.perf_counter()
        score = detector.score(args.image.resolve())
        if args.device == "cuda":
            torch.cuda.synchronize()
            result["peak_allocated_mib"] = torch.cuda.max_memory_allocated() / 2**20
        result.update(
            {
                "image": str(args.image.resolve()),
                "score_seconds": time.perf_counter() - started,
                "z_score": score.z_score,
                "raw_score": score.raw_score,
                "is_fake": score.is_fake,
                "threshold": score.threshold,
            }
        )

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
