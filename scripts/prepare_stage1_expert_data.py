#!/usr/bin/env python3
"""Prepare the frozen Stage 1 expert-screening subset from B-Free archives."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from PIL import Image


EXPECTED_MD5 = {
    "real_RAISE_1k.zip": "a6aad7728226218f22a28b9c9aacaa2c",
    "sd3_flux.zip": "5a255c18fa99eb3115c7ed39d2840796",
}
PREFIXES = {
    "raise": "real_RAISE_1k/",
    "flux": "flux/",
    "sd3_5": "sd3_large/",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-archive", type=Path, required=True)
    parser.add_argument("--generated-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--calibration-groups", type=int, default=100)
    parser.add_argument("--screening-groups", type=int, default=100)
    return parser.parse_args()


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_members(archive: ZipFile, prefix: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in archive.namelist():
        path = PurePosixPath(name)
        if (
            not name.startswith(prefix)
            or path.suffix.lower() != ".png"
            or ".ipynb_checkpoints" in path.parts
        ):
            continue
        if len(path.parts) != 2:
            raise ValueError(f"Unexpected nested image path: {name}")
        if path.stem in result:
            raise ValueError(f"Duplicate source id under {prefix}: {path.stem}")
        result[path.stem] = name
    return result


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Output already exists: {args.output}")
    if args.calibration_groups < 1 or args.screening_groups < 1:
        raise ValueError("Both split sizes must be positive")

    archives = (args.real_archive.resolve(), args.generated_archive.resolve())
    archive_info: dict[str, dict[str, object]] = {}
    for archive in archives:
        expected = EXPECTED_MD5.get(archive.name)
        if expected is None:
            raise ValueError(f"Unexpected archive name: {archive.name}")
        md5 = file_hash(archive, "md5")
        if md5 != expected:
            raise ValueError(
                f"MD5 mismatch for {archive.name}: expected {expected}, got {md5}"
            )
        archive_info[archive.name] = {
            "bytes": archive.stat().st_size,
            "md5": md5,
            "sha256": file_hash(archive, "sha256"),
        }

    with ZipFile(args.real_archive) as real_zip, ZipFile(
        args.generated_archive
    ) as generated_zip:
        members = {
            "raise": image_members(real_zip, PREFIXES["raise"]),
            "flux": image_members(generated_zip, PREFIXES["flux"]),
            "sd3_5": image_members(generated_zip, PREFIXES["sd3_5"]),
        }
        member_sets = {name: set(paths) for name, paths in members.items()}
        if any(len(paths) != 1000 for paths in member_sets.values()):
            raise ValueError(
                "Expected 1,000 valid images per source, got "
                + repr({name: len(paths) for name, paths in member_sets.items()})
            )
        if not (
            member_sets["raise"] == member_sets["flux"] == member_sets["sd3_5"]
        ):
            raise ValueError("RAISE, FLUX, and SD3.5 source ids do not match")

        group_ids = sorted(member_sets["raise"])
        rng = random.Random(args.seed)
        rng.shuffle(group_ids)
        needed = args.calibration_groups + args.screening_groups
        if needed > len(group_ids):
            raise ValueError(f"Requested {needed} groups from {len(group_ids)}")
        split_groups = {
            "calibration": group_ids[: args.calibration_groups],
            "screening": group_ids[
                args.calibration_groups : args.calibration_groups
                + args.screening_groups
            ],
        }

        args.output.mkdir(parents=True)
        licenses = args.output / "licenses"
        licenses.mkdir()
        license_payload = real_zip.read("real_RAISE_1k/RAISE_License.pdf")
        licenses.joinpath("RAISE_License.pdf").write_bytes(license_payload)
        licenses.joinpath("RAISE_README.txt").write_bytes(
            real_zip.read("real_RAISE_1k/README.txt")
        )

        records: list[dict[str, object]] = []
        source_specs = (
            ("raise", "real", real_zip),
            ("flux", "fake", generated_zip),
            ("sd3_5", "fake", generated_zip),
        )
        for split, ids in split_groups.items():
            for group_index, source_id in enumerate(ids):
                for generator, label, archive in source_specs:
                    member = members[generator][source_id]
                    payload = archive.read(member)
                    with Image.open(io.BytesIO(payload)) as image:
                        image_format = image.format
                        width, height = image.size
                        mode = image.mode
                    relative_path = Path("images", split, generator, f"{source_id}.png")
                    destination = args.output / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(payload)
                    records.append(
                        {
                            "sample_id": f"{source_id}:{generator}",
                            "source_group": source_id,
                            "group_index": group_index,
                            "split": split,
                            "label": label,
                            "generator": generator,
                            "relative_path": relative_path.as_posix(),
                            "archive": (
                                args.real_archive.name
                                if generator == "raise"
                                else args.generated_archive.name
                            ),
                            "archive_member": member,
                            "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "image_format": image_format,
                            "width": width,
                            "height": height,
                            "mode": mode,
                        }
                    )

        with args.output.joinpath("manifest.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

        hidden_checkpoint_members = sorted(
            name
            for name in generated_zip.namelist()
            if ".ipynb_checkpoints" in PurePosixPath(name).parts
            and name.lower().endswith(".png")
        )
        summary = {
            "name": "stage1-bfree-screen-20260928",
            "created_date": "2026-09-28",
            "source_url": "https://www.grip.unina.it/download/prog/B-Free/extended_synthbuster/",
            "seed": args.seed,
            "independent_unit": "source_group",
            "split_group_counts": {
                split: len(ids) for split, ids in split_groups.items()
            },
            "image_count": len(records),
            "generator_counts": dict(Counter(r["generator"] for r in records)),
            "label_counts": dict(Counter(r["label"] for r in records)),
            "archive_integrity": archive_info,
            "excluded_members": hidden_checkpoint_members,
            "license": {
                "b_free": "informational and nonprofit use; retain notices and cite authors",
                "raise": "scientific non-commercial use; cite RAISE; retain copyright, license, and original link",
            },
            "usage": "Stage 1 calibration and expert screening only; excluded from Stages 2-4",
            "known_design_boundary": (
                "All files are RGB PNG, but RAISE images are approximately 1256-1258 by "
                "833-835 while FLUX and SD3.5 images are 1024 by 1024. Results may reflect "
                "resolution or aspect-ratio sensitivity as well as generator artifacts."
            ),
        }
        write_json(args.output / "dataset_summary.json", summary)

    copied_license = args.output / "licenses" / "RAISE_License.pdf"
    if file_hash(copied_license, "sha256") != hashlib.sha256(license_payload).hexdigest():
        raise ValueError("Copied RAISE license does not match the archive member")

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
