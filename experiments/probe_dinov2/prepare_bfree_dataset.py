#!/usr/bin/env python3
"""Freeze and extract a new, unused 100-source-group B-Free test set."""

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
MEMBER_PREFIXES = {
    "raise": ("real_RAISE_1k/", "real"),
    "flux": ("flux/", "fake_flux"),
    "sd3_5": ("sd3_large/", "fake_sd35"),
}
GENERATOR_ORDER = ("raise", "flux", "sd3_5")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_members(archive: ZipFile, prefix: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in archive.namelist():
        path = PurePosixPath(name)
        if not name.startswith(prefix) or path.suffix.lower() != ".png":
            continue
        if ".ipynb_checkpoints" in path.parts:
            continue
        if len(path.parts) != 2:
            raise ValueError(f"Unexpected nested image path: {name}")
        if path.stem in result:
            raise ValueError(f"Duplicate source id under {prefix}: {path.stem}")
        result[path.stem] = name
    return result


def used_groups(manifests: list[Path]) -> set[str]:
    groups: set[str] = set()
    for manifest in manifests:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                groups.add(json.loads(line)["source_group"])
    return groups


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-archive", type=Path, required=True)
    parser.add_argument("--generated-archive", type=Path, required=True)
    parser.add_argument("--stage1-manifest", type=Path, required=True)
    parser.add_argument("--safe-independent-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--groups", type=int, default=100)
    parser.add_argument("--landscape-groups", type=int, default=70)
    args = parser.parse_args()

    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {args.output}")
    if not 0 < args.landscape_groups < args.groups:
        raise ValueError("landscape-groups must be between 1 and groups-1")

    archives = (args.real_archive.resolve(), args.generated_archive.resolve())
    archive_info: dict[str, dict[str, object]] = {}
    for archive in archives:
        expected_md5 = EXPECTED_MD5.get(archive.name)
        if expected_md5 is None:
            raise ValueError(f"Unexpected B-Free archive name: {archive.name}")
        md5 = file_hash(archive, "md5")
        if md5 != expected_md5:
            raise ValueError(f"B-Free MD5 mismatch for {archive.name}: {md5}")
        archive_info[archive.name] = {
            "bytes": archive.stat().st_size,
            "md5": md5,
            "sha256": file_hash(archive, "sha256"),
        }

    stage1_groups = used_groups([args.stage1_manifest])
    safe_groups = used_groups([args.safe_independent_manifest])
    if stage1_groups & safe_groups:
        raise ValueError("Stage 1 and SAFE independent groups unexpectedly overlap")

    rng = random.Random(args.seed)
    with ZipFile(args.real_archive) as real_zip, ZipFile(
        args.generated_archive
    ) as generated_zip:
        members = {
            generator: archive_members(
                real_zip if generator == "raise" else generated_zip,
                prefix,
            )
            for generator, (prefix, _) in MEMBER_PREFIXES.items()
        }
        group_sets = {generator: set(values) for generator, values in members.items()}
        if any(len(group_set) != 1000 for group_set in group_sets.values()):
            raise ValueError(f"Expected 1,000 images per source: {group_sets}")
        if not (group_sets["raise"] == group_sets["flux"] == group_sets["sd3_5"]):
            raise ValueError("RAISE, FLUX, and SD3.5 source ids do not match")

        all_groups = group_sets["raise"]
        excluded_groups = stage1_groups | safe_groups
        unknown = excluded_groups - all_groups
        if unknown:
            raise ValueError(f"Previously scored source groups are not in archives: {sorted(unknown)[:5]}")
        available_groups = all_groups - excluded_groups
        if len(stage1_groups) != 200 or len(safe_groups) != 200 or len(available_groups) != 600:
            raise ValueError(
                "Expected 200 Stage 1 groups, 200 SAFE-independent groups, "
                f"and 600 unused groups; got {len(stage1_groups)}, {len(safe_groups)}, "
                f"and {len(available_groups)}"
            )

        orientations: dict[str, list[str]] = {"landscape": [], "portrait": []}
        for source_group in sorted(available_groups):
            member = members["raise"][source_group]
            with Image.open(io.BytesIO(real_zip.read(member))) as image:
                width, height = image.size
            if width == height:
                raise ValueError(f"Unexpected square RAISE image: {source_group}")
            orientations["landscape" if width > height else "portrait"].append(source_group)

        portrait_count = args.groups - args.landscape_groups
        if len(orientations["landscape"]) < args.landscape_groups or len(orientations["portrait"]) < portrait_count:
            raise ValueError(f"Insufficient groups in orientation strata: {orientations}")
        selected = rng.sample(orientations["landscape"], args.landscape_groups)
        selected.extend(rng.sample(orientations["portrait"], portrait_count))
        rng.shuffle(selected)

        args.output.mkdir(parents=True)
        records: list[dict[str, object]] = []
        orientation_by_group = {
            source_group: orientation
            for orientation, source_groups in orientations.items()
            for source_group in source_groups
        }
        for group_index, source_group in enumerate(selected):
            for generator in GENERATOR_ORDER:
                prefix, class_dir = MEMBER_PREFIXES[generator]
                archive = real_zip if generator == "raise" else generated_zip
                member = members[generator][source_group]
                payload = archive.read(member)
                with Image.open(io.BytesIO(payload)) as image:
                    image_format = image.format
                    width, height = image.size
                    mode = image.mode
                relative_path = Path("probe_eval_data", class_dir, f"{source_group}.png")
                destination = args.output / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
                records.append(
                    {
                        "sample_id": f"{source_group}:{generator}",
                        "source_group": source_group,
                        "group_index": group_index,
                        "split": "test",
                        "orientation": orientation_by_group[source_group],
                        "label": "real" if generator == "raise" else "fake",
                        "label_id": 0 if generator == "raise" else 1,
                        "generator": generator,
                        "relative_path": relative_path.as_posix(),
                        "archive": (
                            args.real_archive.name if generator == "raise" else args.generated_archive.name
                        ),
                        "archive_member": member,
                        "bytes": len(payload),
                        "sha256": sha256_bytes(payload),
                        "image_format": image_format,
                        "width": width,
                        "height": height,
                        "mode": mode,
                    }
                )

        manifest_path = args.output / "manifest.jsonl"
        with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

        licenses = args.output / "licenses"
        licenses.mkdir()
        license_payload = real_zip.read("real_RAISE_1k/RAISE_License.pdf")
        (licenses / "RAISE_License.pdf").write_bytes(license_payload)
        (licenses / "RAISE_README.txt").write_bytes(real_zip.read("real_RAISE_1k/README.txt"))

    summary = {
        "name": "probe-dinov2-bfree-20261001",
        "purpose": "frozen common evaluation set for PROBE-DINOv2 and re-scored FSD/AIDE/SAFE",
        "created_date": "2026-10-01",
        "source_url": "https://www.grip.unina.it/download/prog/B-Free/extended_synthbuster/",
        "selection_seed": args.seed,
        "selection_unit": "source_group",
        "selection_rule": (
            f"sample {args.landscape_groups} landscape and {portrait_count} portrait groups "
            "without replacement from groups absent from Stage 1 and SAFE independent manifests"
        ),
        "excluded_group_counts": {
            "stage1": len(stage1_groups),
            "safe_independent": len(safe_groups),
            "previously_scored_union": len(excluded_groups),
        },
        "unused_groups_before_selection": len(available_groups),
        "reserved_unused_groups_after_selection": len(available_groups) - args.groups,
        "selected_source_groups": selected,
        "selected_orientation_counts": dict(Counter(orientation_by_group[group] for group in selected)),
        "generator_counts": dict(Counter(str(row["generator"]) for row in records)),
        "label_counts": dict(Counter(str(row["label"]) for row in records)),
        "image_count": len(records),
        "archive_integrity": archive_info,
        "excluded_manifest_sha256": {
            "stage1": file_hash(args.stage1_manifest, "sha256"),
            "safe_independent": file_hash(args.safe_independent_manifest, "sha256"),
        },
        "manifest_sha256": file_hash(manifest_path, "sha256"),
        "license": {
            "b_free": "informational and nonprofit use; retain notices and cite authors",
            "raise": "scientific non-commercial use; cite RAISE; retain copyright, license, and original link",
        },
        "preprocessing": "Original PNG bytes extracted from the verified B-Free archives; no image transformation.",
        "known_design_boundary": (
            "Each source group contains matched RAISE, FLUX, and SD3.5 images, but their "
            "native resolution and aspect ratio differ."
        ),
    }
    write_json(args.output / "dataset_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
