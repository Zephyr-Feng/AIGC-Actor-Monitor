#!/usr/bin/env python3
"""Extract a held-out RIGID threshold calibration subset from reserved B-Free groups."""

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
    "raise": ("real_RAISE_1k/", "real", 0),
    "flux": ("flux/", "fake_flux", 1),
    "sd3_5": ("sd3_large/", "fake_sd35", 1),
}


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def groups(path: Path) -> set[str]:
    rows = read_jsonl(path)
    return {row.get("source_group", row.get("source_group_id")) for row in rows}


def members(archive: ZipFile, prefix: str) -> dict[str, str]:
    result = {}
    for name in archive.namelist():
        posix = PurePosixPath(name)
        if name.startswith(prefix) and posix.suffix.lower() == ".png" and len(posix.parts) == 2:
            if posix.stem in result:
                raise ValueError(f"Duplicate source id under {prefix}: {posix.stem}")
            result[posix.stem] = name
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-archive", type=Path, required=True)
    parser.add_argument("--generated-archive", type=Path, required=True)
    parser.add_argument("--stage1-manifest", type=Path, required=True)
    parser.add_argument("--safe-manifest", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--groups", type=int, default=30)
    args = parser.parse_args()

    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite calibration output: {args.output}")
    for archive in (args.real_archive, args.generated_archive):
        expected = EXPECTED_MD5[archive.name]
        actual = hash_file(archive, "md5")
        if actual != expected:
            raise ValueError(f"B-Free archive MD5 mismatch for {archive.name}: {actual} != {expected}")

    stage1_groups = groups(args.stage1_manifest)
    safe_groups = groups(args.safe_manifest)
    test_rows = read_jsonl(args.test_manifest)
    test_groups = {row.get("source_group", row.get("source_group_id")) for row in test_rows}
    if len(stage1_groups) != 200 or len(safe_groups) != 200 or len(test_groups) != 100:
        raise ValueError(f"Unexpected split sizes: stage1={len(stage1_groups)} safe={len(safe_groups)} test={len(test_groups)}")
    if stage1_groups & safe_groups or (stage1_groups | safe_groups) & test_groups:
        raise ValueError("Source groups overlap across the previously used and frozen test manifests")

    archives = {"raise": ZipFile(args.real_archive), "generated": ZipFile(args.generated_archive)}
    try:
        source_members = {
            generator: members(archives["raise"] if generator == "raise" else archives["generated"], prefix)
            for generator, (prefix, _, _) in MEMBER_PREFIXES.items()
        }
        group_sets = [set(value) for value in source_members.values()]
        if any(len(group_set) != 1000 for group_set in group_sets) or not all(s == group_sets[0] for s in group_sets[1:]):
            raise ValueError("B-Free archives must contain the same 1,000 source groups for all generators")
        excluded = stage1_groups | safe_groups | test_groups
        if not excluded <= group_sets[0]:
            raise ValueError("An excluded source group is absent from the verified B-Free archives")
        available = sorted(group_sets[0] - excluded)
        if len(available) != 500:
            raise ValueError(f"Expected 500 unused reserved groups, got {len(available)}")

        selected = random.Random(args.seed).sample(available, args.groups)
        args.output.mkdir(parents=True)
        image_root = args.output / "images"
        for _, class_dir, _ in MEMBER_PREFIXES.values():
            (image_root / class_dir).mkdir(parents=True)

        rows = []
        orientation_counts = Counter()
        for group in selected:
            real_member = source_members["raise"][group]
            real_payload = archives["raise"].read(real_member)
            with Image.open(io.BytesIO(real_payload)) as image:
                width, height = image.size
                orientation = "landscape" if width > height else "portrait" if height > width else "square"
            orientation_counts[orientation] += 1
            for generator, archive_key in (("raise", "raise"), ("flux", "generated"), ("sd3_5", "generated")):
                prefix, class_dir, label_id = MEMBER_PREFIXES[generator]
                member = source_members[generator][group]
                payload = real_payload if generator == "raise" else archives[archive_key].read(member)
                relative_path = Path(class_dir, f"{group}.png").as_posix()
                destination = image_root / relative_path
                destination.write_bytes(payload)
                rows.append({
                    "sample_id": f"{group}:{generator}",
                    "source_group": group,
                    "split": "calibration",
                    "label": "real" if label_id == 0 else "fake",
                    "label_id": label_id,
                    "generator": generator,
                    "orientation": orientation,
                    "relative_path": relative_path,
                    "archive": args.real_archive.name if archive_key == "raise" else args.generated_archive.name,
                    "archive_member": member,
                    "bytes": len(payload),
                    "sha256": hash_bytes(payload),
                    "width": width if generator == "raise" else None,
                    "height": height if generator == "raise" else None,
                })

        manifest_path = args.output / "calibration_manifest.jsonl"
        with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        license_dir = args.output / "licenses"
        license_dir.mkdir()
        (license_dir / "RAISE_License.pdf").write_bytes(archives["raise"].read("real_RAISE_1k/RAISE_License.pdf"))
        (license_dir / "RAISE_README.txt").write_bytes(archives["raise"].read("real_RAISE_1k/README.txt"))
    finally:
        for archive in archives.values():
            archive.close()

    summary = {
        "purpose": "calibrate the RIGID score threshold only; never used to choose the model or inference parameters",
        "selection_seed": args.seed,
        "selection_unit": "source_group",
        "selection_rule": f"simple random sample of {args.groups} groups from the 500 source groups reserved after excluding Stage 1, SAFE-independent, and frozen test groups",
        "groups": args.groups,
        "images": len(rows),
        "generator_counts": dict(Counter(row["generator"] for row in rows)),
        "orientation_counts": dict(orientation_counts),
        "source_groups": selected,
        "excluded_group_counts": {"stage1": len(stage1_groups), "safe_independent": len(safe_groups), "frozen_test": len(test_groups)},
        "overlap_with_frozen_test": sorted(set(selected) & test_groups),
        "archive_integrity": {
            archive.name: {"md5": hash_file(archive, "md5"), "sha256": hash_file(archive, "sha256"), "bytes": archive.stat().st_size}
            for archive in (args.real_archive, args.generated_archive)
        },
        "source_manifest_sha256": {
            "stage1": hash_file(args.stage1_manifest, "sha256"),
            "safe_independent": hash_file(args.safe_manifest, "sha256"),
            "frozen_test": hash_file(args.test_manifest, "sha256"),
        },
        "calibration_manifest_sha256": hash_file(manifest_path, "sha256"),
        "threshold_policy": "choose similarity threshold maximizing image-level balanced accuracy on this calibration set; fake iff similarity < threshold; tie-break at median of maximizing finite candidate thresholds",
        "preprocessing": "original PNG bytes; no transformation during calibration data preparation",
    }
    (args.output / "calibration_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
