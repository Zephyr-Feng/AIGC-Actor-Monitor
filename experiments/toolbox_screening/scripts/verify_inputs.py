#!/usr/bin/env python3
"""Verify frozen and calibration manifests against the original image bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(name: str, manifest_path: Path, image_root: Path, expected_images: int,
           expected_groups: int, expected_per_generator: int) -> tuple[dict, set[str]]:
    records = read_jsonl(manifest_path)
    ids = [record["sample_id"] for record in records]
    if len(ids) != expected_images or len(set(ids)) != expected_images:
        raise ValueError(f"{name}: expected {expected_images} unique images, got {len(ids)} rows/{len(set(ids))} IDs")
    group_ids = {record["source_group"] for record in records}
    if len(group_ids) != expected_groups:
        raise ValueError(f"{name}: expected {expected_groups} source groups, got {len(group_ids)}")
    counts = Counter(record["generator"] for record in records)
    if counts != {"raise": expected_per_generator, "flux": expected_per_generator, "sd3_5": expected_per_generator}:
        raise ValueError(f"{name}: unexpected generator counts {dict(counts)}")
    checked = []
    for record in records:
        image = image_root / record["relative_path"]
        if not image.is_file():
            raise FileNotFoundError(f"{name}: missing {record['sample_id']}: {image}")
        actual = sha256(image)
        if actual != record["sha256"]:
            raise ValueError(f"{name}: SHA-256 mismatch for {record['sample_id']}: {actual} != {record['sha256']}")
        checked.append({"sample_id": record["sample_id"], "sha256": actual})
    manifest_hash = sha256(manifest_path)
    return ({"name": name, "manifest": str(manifest_path.resolve()), "manifest_sha256": manifest_hash,
             "image_root": str(image_root.resolve()), "images": len(records),
             "source_groups": len(group_ids), "generator_counts": dict(counts),
             "images_sha256_verified": len(checked)}, group_ids)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--test-image-root", type=Path, required=True)
    parser.add_argument("--calibration-manifest", type=Path)
    parser.add_argument("--calibration-image-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.calibration_manifest) != bool(args.calibration_image_root):
        raise ValueError("Provide both calibration manifest and calibration image root, or neither")

    test_result, test_groups = verify("frozen_test", args.test_manifest, args.test_image_root, 300, 100, 100)
    result = {"status": "PASS", "test": test_result}
    if args.calibration_manifest:
        calibration_result, calibration_groups = verify("rigid_calibration", args.calibration_manifest,
                                                        args.calibration_image_root, 90, 30, 30)
        overlap = sorted(test_groups & calibration_groups)
        if overlap:
            raise ValueError(f"Frozen test and calibration groups overlap: {overlap}")
        calibration_result["overlap_with_frozen_test"] = overlap
        result["rigid_calibration"] = calibration_result
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
