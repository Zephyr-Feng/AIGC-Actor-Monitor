"""Prepare source-disjoint COCO/SDXL pairs for the three-arm pilot."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from .t0 import _images_by_name, save_common_channel


def prepare_pilot(
    real_dir: Path,
    fake_dir: Path,
    output: Path,
    excluded_groups: set[str],
    *,
    n_pairs: int,
    seed: int = 220928,
) -> list[dict]:
    real = _images_by_name(real_dir)
    fake = _images_by_name(fake_dir)
    candidates = sorted(
        name for name in real.keys() & fake.keys()
        if f"caption-{Path(name).stem}" not in excluded_groups
    )
    if len(candidates) < n_pairs:
        raise ValueError(f"only {len(candidates)} unused same-named pairs; need {n_pairs}")
    names = sorted(random.Random(seed).sample(candidates, n_pairs))

    output.mkdir(parents=True, exist_ok=False)
    image_dir = output / "images"
    image_dir.mkdir()
    rows: list[dict] = []
    for name in names:
        pair_id = Path(name).stem
        for label, source in (("real", real[name]), ("fake", fake[name])):
            target = image_dir / f"{pair_id}_{label}.jpg"
            save_common_channel(source, target, 512)
            rows.append({
                "sample_id": f"pilot-{pair_id}-{label}",
                "source_group_id": f"caption-{pair_id}",
                "label": label,
                "split": "P-pilot",
                "image_path": str(target),
                "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "original_path": str(source),
                "channel": "center-fit-512px-jpeg-q90-444",
            })
    with (output / "manifest.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return rows
