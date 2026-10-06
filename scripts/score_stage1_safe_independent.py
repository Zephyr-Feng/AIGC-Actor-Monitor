"""Score one frozen split of the independent SAFE calibration/screening set."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("calibration", "screening"), required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    all_rows = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines()]
    if len(all_rows) != 400 or len({row["sample_id"] for row in all_rows}) != 400:
        raise ValueError("frozen independent manifest must contain 400 unique images")
    rows = [row for row in all_rows if row["split"] == args.split]
    expected = 100 if args.split == "calibration" else 300
    if len(rows) != expected:
        raise ValueError(f"expected {expected} images in {args.split}")
    for row in rows:
        image = args.dataset / row["relative_path"]
        if file_sha256(image) != row["sha256"]:
            raise ValueError(f"image hash mismatch: {row['sample_id']}")
    manifest_sha256 = file_sha256(args.manifest)
    checkpoint_sha256 = file_sha256(args.checkpoint)
    metadata = {
        "purpose": "independent SAFE threshold calibration and screening",
        "split": args.split,
        "manifest_sha256": manifest_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "source_commit": "4e998724651b227def64f5be0cd60c0aa1552c35",
        "script_sha256": file_sha256(Path(__file__)),
        "preprocessing": "RGB, CenterCrop(256), ToTensor()",
        "score": "softmax(logits)[1] = fake probability",
        "device": "cuda",
    }
    meta_path = args.output.with_suffix(".meta.json")
    if meta_path.exists() and json.loads(meta_path.read_text(encoding="utf-8")) != metadata:
        raise ValueError("run metadata changed")
    if args.output.exists() and not meta_path.exists():
        raise ValueError("score file exists without metadata")
    completed = set()
    if args.output.exists():
        previous = [json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines()]
        completed = {row["sample_id"] for row in previous}
        if len(previous) != len(completed):
            raise ValueError("duplicate scored sample")
    pending = [row for row in rows if row["sample_id"] not in completed]
    if args.check_only:
        print(json.dumps({"total": len(rows), "completed": len(completed), "pending": len(pending), "manifest_sha256": manifest_sha256}))
        return
    if not pending:
        return

    import torch
    from PIL import Image
    from torchvision import transforms

    sys.path.insert(0, str(args.source))
    from models.resnet import resnet50

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = resnet50(num_classes=2)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().to("cuda")
    torch.cuda.reset_peak_memory_stats()
    transform = transforms.Compose([transforms.CenterCrop((256, 256)), transforms.ToTensor()])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not meta_path.exists():
        meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    with args.output.open("a", encoding="utf-8") as stream:
        for index, row in enumerate(pending, 1):
            start = time.perf_counter()
            image_path = args.dataset / row["relative_path"]
            with Image.open(image_path) as source_image:
                tensor = transform(source_image.convert("RGB")).unsqueeze(0).to("cuda")
            torch.cuda.synchronize()
            preprocess_seconds = time.perf_counter() - start
            start = time.perf_counter()
            with torch.inference_mode():
                logits = model(tensor)
            torch.cuda.synchronize()
            forward_seconds = time.perf_counter() - start
            score = {
                "sample_id": row["sample_id"],
                "source_group": row["source_group"],
                "split": row["split"],
                "generator": row["generator"],
                "label": row["label"],
                "image_sha256": row["sha256"],
                "logits_real_fake": logits[0].detach().cpu().tolist(),
                "fake_probability": logits.softmax(dim=1)[0, 1].item(),
                "preprocess_seconds": preprocess_seconds,
                "forward_seconds": forward_seconds,
            }
            stream.write(json.dumps(score) + "\n")
            stream.flush()
            if index % 10 == 0 or index == len(pending):
                print(json.dumps({"event": "progress", "completed_this_run": index, "total_pending": len(pending)}), flush=True)
    print(json.dumps({"event": "complete", "total": len(rows), "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20}), flush=True)


if __name__ == "__main__":
    main()
