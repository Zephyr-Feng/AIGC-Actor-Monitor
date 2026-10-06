"""Prepare a small, paired discovery set for the tool usability check."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def save_common_channel(source: Path, target: Path, size: int) -> None:
    from PIL import Image, ImageOps

    with Image.open(source) as original:
        image = ImageOps.fit(
            ImageOps.exif_transpose(original).convert("RGB"),
            (size, size),
            method=Image.Resampling.LANCZOS,
        )
        image.save(target, format="JPEG", quality=90, subsampling=0)


def _images_by_name(directory: Path) -> dict[str, Path]:
    return {
        path.name: path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }


def prepare_t0(
    real_dir: Path,
    fake_dir: Path,
    output: Path,
    *,
    n_pairs: int = 12,
    seed: int = 20260927,
    size: int = 512,
) -> list[dict]:
    """Sample same-named pairs and apply the same output channel to both labels."""
    real = _images_by_name(real_dir)
    fake = _images_by_name(fake_dir)
    shared = sorted(real.keys() & fake.keys())
    if len(shared) < n_pairs:
        raise ValueError(f"only {len(shared)} same-named pairs; need {n_pairs}")

    names = sorted(random.Random(seed).sample(shared, n_pairs))
    output.mkdir(parents=True, exist_ok=False)
    image_dir = output / "images"
    image_dir.mkdir()
    rows: list[dict] = []

    for name in names:
        pair_id = Path(name).stem
        for label, source in (("real", real[name]), ("fake", fake[name])):
            target = image_dir / f"{pair_id}_{label}.jpg"
            save_common_channel(source, target, size)
            rows.append({
                "sample_id": f"t0-{pair_id}-{label}",
                "source_group_id": f"caption-{pair_id}",
                "label": label,
                "split": "T0-discovery",
                "image_path": str(target),
                "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "original_path": str(source),
                "channel": f"center-fit-{size}px-jpeg-q90-444",
            })

    manifest = output / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return rows
