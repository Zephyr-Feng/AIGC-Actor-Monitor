#!/usr/bin/env python3
"""Validate the frozen Stage 1 B-Free subset and its manifest."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


EXPECTED_GENERATORS = {"raise", "flux", "sd3_5"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    return parser.parse_args()


def main() -> None:
    root = parse_args().root.resolve()
    summary = json.loads(root.joinpath("dataset_summary.json").read_text("utf-8"))
    records = [
        json.loads(line)
        for line in root.joinpath("manifest.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    ]
    if len(records) != summary["image_count"]:
        raise ValueError("Manifest count does not match dataset summary")

    seen_ids: set[str] = set()
    split_groups: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    generator_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    dimensions: Counter[tuple[str, int, int, str, str]] = Counter()

    for record in records:
        sample_id = record["sample_id"]
        if sample_id in seen_ids:
            raise ValueError(f"Duplicate sample id: {sample_id}")
        seen_ids.add(sample_id)

        path = (root / record["relative_path"]).resolve()
        if root not in path.parents:
            raise ValueError(f"Path escapes dataset root: {path}")
        payload = path.read_bytes()
        if len(payload) != record["bytes"]:
            raise ValueError(f"Size mismatch: {path}")
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {path}")
        with Image.open(io.BytesIO(payload)) as image:
            observed = (image.format, image.width, image.height, image.mode)
        expected = (
            record["image_format"],
            record["width"],
            record["height"],
            record["mode"],
        )
        if observed != expected:
            raise ValueError(f"Image metadata mismatch: {path}")

        split = record["split"]
        group = record["source_group"]
        generator = record["generator"]
        split_groups[split][group].add(generator)
        generator_counts[generator] += 1
        label_counts[record["label"]] += 1
        dimensions[(generator, *observed)] += 1

    expected_split_counts = summary["split_group_counts"]
    for split, expected_count in expected_split_counts.items():
        groups = split_groups[split]
        if len(groups) != expected_count:
            raise ValueError(f"Wrong group count for {split}: {len(groups)}")
        incomplete = {
            group: sorted(generators)
            for group, generators in groups.items()
            if generators != EXPECTED_GENERATORS
        }
        if incomplete:
            raise ValueError(f"Incomplete source groups in {split}: {incomplete}")

    split_names = sorted(split_groups)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1 :]:
            overlap = set(split_groups[left]) & set(split_groups[right])
            if overlap:
                raise ValueError(f"Source-group overlap between {left} and {right}")

    if dict(generator_counts) != summary["generator_counts"]:
        raise ValueError("Generator counts do not match dataset summary")
    if dict(label_counts) != summary["label_counts"]:
        raise ValueError("Label counts do not match dataset summary")
    for required in ("RAISE_License.pdf", "RAISE_README.txt"):
        if not root.joinpath("licenses", required).is_file():
            raise FileNotFoundError(f"Missing license file: {required}")

    report = {
        "root": str(root),
        "images": len(records),
        "source_groups": sum(len(groups) for groups in split_groups.values()),
        "split_group_counts": {
            split: len(groups) for split, groups in split_groups.items()
        },
        "generator_counts": dict(generator_counts),
        "label_counts": dict(label_counts),
        "dimension_counts": {
            repr(key): count for key, count in sorted(dimensions.items())
        },
        "status": "ok",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
