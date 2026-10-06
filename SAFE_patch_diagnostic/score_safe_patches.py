#!/usr/bin/env python3
"""Score the frozen 1,500-patch SAFE diagnostic set with the baseline pipeline."""

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path


POSITIONS = ("top_left", "top_right", "bottom_left", "bottom_right", "center")
EXPECTED_MANIFEST_SHA256 = "ceb396cbf9a78d2aa04a4e77307e6062e4486de900b6c8bd12be13f7732fcc58"
EXPECTED_CHECKPOINT_SHA256 = "b3f5ecfb46a154ed553aaaf4bf3ba59182310726ddb0cbb1fe42bd0e22d2f20e"
EXPECTED_COMMIT = "4e998724651b227def64f5be0cd60c0aa1552c35"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--safe-root", type=Path, required=True)
    args = parser.parse_args()

    checkpoint = args.safe_root / "checkpoint" / "checkpoint-best.pth"
    if sha256(checkpoint) != EXPECTED_CHECKPOINT_SHA256:
        raise ValueError("SAFE checkpoint SHA-256 mismatch")
    metadata_path = args.experiment / "metadata.csv"
    metadata = list(csv.DictReader(metadata_path.open(encoding="utf-8", newline="")))
    if len(metadata) != 1500 or len({(r["image_id"], r["position"]) for r in metadata}) != 1500:
        raise ValueError("Expected 1,500 unique image/position crops")

    list_path = args.experiment / "baseline_file_list.txt"
    lines = list_path.read_text(encoding="utf-8").splitlines()
    declared_manifest = next(line.split("=", 1)[1] for line in lines if line.startswith("# manifest_sha256="))
    if declared_manifest != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Frozen screening manifest SHA-256 mismatch")
    baseline_rows = list(csv.DictReader(line for line in lines if line and not line.startswith("#")))
    if len(baseline_rows) != 300 or len({row["image_id"] for row in baseline_rows}) != 300:
        raise ValueError("Expected 300 unique baseline images")
    if {row["position"] for row in metadata} != set(POSITIONS):
        raise ValueError("Unexpected crop positions")
    if {row["image_id"] for row in metadata} != {row["image_id"] for row in baseline_rows}:
        raise ValueError("Crop IDs do not match the frozen baseline list")

    output = args.experiment / "patch_output"
    scores_path = output / "scores.csv"
    if scores_path.exists():
        raise FileExistsError(scores_path)
    output.mkdir(parents=True, exist_ok=True)

    import torch
    from PIL import Image
    from torchvision import transforms

    sys.path.insert(0, str(args.safe_root))
    from models.resnet import resnet50

    checkpoint_data = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model = resnet50(num_classes=2)
    model.load_state_dict(checkpoint_data["model"], strict=True)
    model.eval().to("cuda")
    torch.cuda.reset_peak_memory_stats()
    transform = transforms.Compose([transforms.CenterCrop((256, 256)), transforms.ToTensor()])
    crop_root = args.experiment / "cropped_images"
    lookup = {(row["image_id"], row["position"]): row for row in metadata}
    labels = {row["image_id"]: row["label"] for row in baseline_rows}
    ordered = [(row["image_id"], position) for row in baseline_rows for position in POSITIONS]
    if len(ordered) != 1500 or len(lookup) != 1500:
        raise ValueError("Unexpected scoring order or crop lookup size")

    started = time.perf_counter()
    print(json.dumps({
        "event": "start",
        "images": len(baseline_rows),
        "crops": len(ordered),
        "positions": list(POSITIONS),
        "manifest_sha256": declared_manifest,
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
        "safe_commit": EXPECTED_COMMIT,
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
        "device": torch.cuda.get_device_name(0),
        "preprocessing": "RGB, CenterCrop(256), ToTensor(); batch_size=1",
    }, ensure_ascii=False), flush=True)
    with scores_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("image", "label", "position", "score"))
        for index, (image_id, position) in enumerate(ordered, 1):
            crop = lookup[(image_id, position)]
            image_path = crop_root / f"{image_id}_{position}.png"
            with Image.open(image_path) as image:
                tensor = transform(image.convert("RGB")).unsqueeze(0).to("cuda")
            with torch.inference_mode():
                logits = model(tensor)
            score = logits.softmax(dim=1)[0, 1].item()
            writer.writerow((image_path.name, labels[image_id], position, repr(float(score))))
            if index % 50 == 0 or index == len(ordered):
                stream.flush()
                torch.cuda.synchronize()
                print(json.dumps({"event": "progress", "completed": index, "total": len(ordered)}), flush=True)
    torch.cuda.synchronize()
    print(json.dumps({
        "event": "complete",
        "scored": len(ordered),
        "seconds": round(time.perf_counter() - started, 3),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 3),
    }), flush=True)


if __name__ == "__main__":
    main()
