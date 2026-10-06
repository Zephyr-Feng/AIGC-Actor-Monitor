#!/usr/bin/env python3
"""Score the fixed Stage 1 manifest, appending one recoverable record per image."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expert", choices=("fsd", "aide"), required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--deps-dir", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    manifest = args.dataset / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    meta = {
        "expert": args.expert,
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "repo": str(args.repo.resolve()),
        "weights": str(args.weights.resolve()),
        "device": "cuda",
    }
    if args.expert == "aide":
        meta["input_order"] = "dct4_then_original"
    meta_path = args.output.with_suffix(".meta.json")
    if meta_path.exists() and json.loads(meta_path.read_text()) != meta:
        raise ValueError(f"run metadata changed: {meta_path}")
    if args.output.exists() and not meta_path.exists():
        raise ValueError(f"existing results have no run metadata: {args.output}")
    completed = set()
    if args.output.exists():
        completed = {json.loads(line)["sample_id"] for line in args.output.read_text().splitlines()}
    pending = [row for row in rows if row["sample_id"] not in completed]
    if args.check_only:
        print(json.dumps({"expert": args.expert, "total": len(rows), "completed": len(completed), "pending": len(pending), "manifest_sha256": meta["manifest_sha256"]}))
        return
    if not pending:
        return

    if args.deps_dir:
        sys.path.insert(0, str(args.deps_dir.resolve()))
    sys.path.insert(0, str(args.repo.resolve()))
    import torch

    started = time.perf_counter()
    if args.expert == "fsd":
        from fsd import FSDDetector

        detector = FSDDetector.load(weights_dir=args.weights.resolve(), device="cuda")
    else:
        from models.AIDE import AIDE
        from smoke_aide import prepare_image

        model = AIDE(resnet_path=None, convnext_path=None)
        checkpoint = torch.load(args.weights.resolve(), map_location="cpu", weights_only=False)
        state_dict = checkpoint["model"] if "model" in checkpoint else checkpoint
        model.load_state_dict(state_dict, strict=True)
        del checkpoint, state_dict
        gc.collect()
        model.eval().to("cuda")
    print(json.dumps({"event": "loaded", "expert": args.expert, "seconds": round(time.perf_counter() - started, 3)}), flush=True)
    torch.cuda.reset_peak_memory_stats()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not meta_path.exists():
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    with args.output.open("a", encoding="utf-8") as stream:
        for index, row in enumerate(rows, 1):
            if row["sample_id"] in completed:
                continue
            image_path = args.dataset / row["relative_path"]
            started = time.perf_counter()
            if args.expert == "fsd":
                result = detector.score(image_path)
                torch.cuda.synchronize()
                score = {"z_score": result.z_score, "raw_score": result.raw_score, "is_fake": result.is_fake, "threshold": result.threshold}
            else:
                image = prepare_image(image_path).to("cuda")
                torch.cuda.synchronize()
                prepare_seconds = time.perf_counter() - started
                with torch.inference_mode():
                    logits = model(image)
                    torch.cuda.synchronize()
                    fake_probability = torch.softmax(logits, dim=1)[0, 1].item()
                score = {"logits": logits[0].detach().cpu().tolist(), "fake_probability": fake_probability, "prepare_seconds": prepare_seconds}
                del image, logits
            output = {
                "sample_id": row["sample_id"],
                "source_group": row["source_group"],
                "split": row["split"],
                "generator": row["generator"],
                "label": row["label"],
                "image_sha256": row["sha256"],
                "score_seconds": time.perf_counter() - started,
                **score,
            }
            stream.write(json.dumps(output, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"event": "scored", "index": index, "sample_id": row["sample_id"], "seconds": round(output["score_seconds"], 3)}), flush=True)
    print(json.dumps({"event": "complete", "expert": args.expert, "count": len(rows), "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20}), flush=True)


if __name__ == "__main__":
    main()
