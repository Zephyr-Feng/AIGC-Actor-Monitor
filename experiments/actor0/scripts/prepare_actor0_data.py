#!/usr/bin/env python3
"""Freeze disjoint Actor-0 development/evaluation splits from verified B-Free archives."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/probe_dinov2"))
from prepare_bfree_dataset import (  # noqa: E402
    EXPECTED_MD5,
    GENERATOR_ORDER,
    MEMBER_PREFIXES,
    archive_members,
    file_hash,
    sha256_bytes,
    used_groups,
    write_json,
)


PRIOR_MANIFESTS = [
    ROOT / "runs/stage1-bfree-screen-20260928/manifest.jsonl",
    ROOT / "runs/stage1-safe-independent-20260929/manifest.jsonl",
    ROOT / "runs/stage1-safe-triage-20260929/manifest.jsonl",
    ROOT / "runs/probe-dinov2-bfree-20261001/manifest.jsonl",
    ROOT / "experiments/probe_dinov2/dataset_manifest.jsonl",
    ROOT / "experiments/toolbox_screening/dataset_manifest.jsonl",
    ROOT / "experiments/toolbox_screening/rigid/calibration/calibration_manifest.jsonl",
]
CLASS_DIR = {"raise": "real", "flux": "fake_flux", "sd3_5": "fake_sd35"}
SEED = 20261002
DEV_GROUPS = 60
EVAL_GROUPS = 100


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(path: Path, rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"existing manifest differs; refusing to overwrite: {path}")
        return digest(path)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    return digest(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-archive", type=Path,
                        default=ROOT / ".cache/bfree-stage1-20260928/real_RAISE_1k.zip")
    parser.add_argument("--generated-archive", type=Path,
                        default=ROOT / ".cache/bfree-stage1-20260928/sd3_flux.zip")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "experiments/actor0/data")
    parser.add_argument("--image-output", type=Path,
                        default=ROOT / "runs/actor0-bfree-20261002/data")
    parser.add_argument("--resume", action="store_true",
                        help="resume only matching partial files created by this script")
    args = parser.parse_args()
    if (args.output.exists() or args.image_output.exists()) and not args.resume:
        raise FileExistsError("Actor-0 data output exists; refusing to overwrite")
    missing = [str(path) for path in PRIOR_MANIFESTS if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required prior manifests are missing: {missing}")

    archive_paths = (args.real_archive.resolve(), args.generated_archive.resolve())
    archive_hashes = {}
    for archive in archive_paths:
        expected = EXPECTED_MD5.get(archive.name)
        if not expected:
            raise ValueError(f"unexpected archive name: {archive.name}")
        md5 = file_hash(archive, "md5")
        if md5 != expected:
            raise ValueError(f"B-Free MD5 mismatch for {archive.name}: {md5}")
        archive_hashes[archive.name] = {
            "bytes": archive.stat().st_size,
            "md5": md5,
            "sha256": file_hash(archive, "sha256"),
        }

    excluded_groups = used_groups(PRIOR_MANIFESTS)
    excluded_manifests = {
        str(path.relative_to(ROOT)): {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in PRIOR_MANIFESTS
    }
    rng = random.Random(SEED)
    with ZipFile(archive_paths[0]) as real_zip, ZipFile(archive_paths[1]) as generated_zip:
        members = {
            generator: archive_members(real_zip if generator == "raise" else generated_zip, prefix)
            for generator, (prefix, _) in MEMBER_PREFIXES.items()
        }
        source_ids = {name: set(value) for name, value in members.items()}
        if not (source_ids["raise"] == source_ids["flux"] == source_ids["sd3_5"]):
            raise ValueError("RAISE/FLUX/SD3.5 source IDs do not match")
        if len(source_ids["raise"]) != 1000:
            raise ValueError(f"expected 1,000 B-Free source groups; found {len(source_ids['raise'])}")
        unknown = excluded_groups - source_ids["raise"]
        if unknown:
            raise ValueError(f"prior manifest IDs missing from archives: {sorted(unknown)[:10]}")
        available = source_ids["raise"] - excluded_groups
        if len(available) < DEV_GROUPS + EVAL_GROUPS:
            raise ValueError(f"only {len(available)} unused groups; need {DEV_GROUPS + EVAL_GROUPS}")

        orientations: dict[str, list[str]] = {"landscape": [], "portrait": []}
        for sid in sorted(available):
            with Image.open(io.BytesIO(real_zip.read(members["raise"][sid]))) as image:
                if image.width == image.height:
                    raise ValueError(f"unexpected square source image: {sid}")
                orientations["landscape" if image.width > image.height else "portrait"].append(sid)
        dev_land, dev_portrait = 42, 18
        eval_land, eval_portrait = 70, 30
        if (len(orientations["landscape"]) < dev_land + eval_land
                or len(orientations["portrait"]) < dev_portrait + eval_portrait):
            raise ValueError("insufficient unused groups in an orientation stratum")

        dev = rng.sample(orientations["landscape"], dev_land)
        dev += rng.sample(orientations["portrait"], dev_portrait)
        rng.shuffle(dev)
        dev_set = set(dev)
        remaining_land = [sid for sid in orientations["landscape"] if sid not in dev_set]
        remaining_portrait = [sid for sid in orientations["portrait"] if sid not in dev_set]
        evaluation = rng.sample(remaining_land, eval_land)
        evaluation += rng.sample(remaining_portrait, eval_portrait)
        rng.shuffle(evaluation)
        if set(dev) & set(evaluation) or (set(dev) | set(evaluation)) & excluded_groups:
            raise ValueError("Actor-0 split overlaps prior groups or each other")

        args.output.mkdir(parents=True, exist_ok=True)
        args.image_output.mkdir(parents=True, exist_ok=True)
        licenses = args.output / "licenses"
        licenses.mkdir(exist_ok=True)
        for license_name, member_name in (("RAISE_License.pdf", "real_RAISE_1k/RAISE_License.pdf"),
                                          ("RAISE_README.txt", "real_RAISE_1k/README.txt")):
            payload = real_zip.read(member_name)
            path = licenses / license_name
            if path.exists() and path.read_bytes() != payload:
                raise FileExistsError(f"existing license file differs; refusing to overwrite: {path}")
            if not path.exists():
                path.write_bytes(payload)

        all_rows: dict[str, list[dict]] = {"dev": [], "eval": []}
        orientation_for: dict[str, str] = {
            sid: "landscape" for sid in orientations["landscape"]
        }
        orientation_for.update({sid: "portrait" for sid in orientations["portrait"]})
        for split, group_ids in (("dev", dev), ("eval", evaluation)):
            for group_index, sid in enumerate(group_ids):
                for generator in GENERATOR_ORDER:
                    archive = real_zip if generator == "raise" else generated_zip
                    member = members[generator][sid]
                    payload = archive.read(member)
                    with Image.open(io.BytesIO(payload)) as image:
                        width, height, fmt, mode = image.width, image.height, image.format, image.mode
                    relative = Path(split, CLASS_DIR[generator], f"{sid}.png").as_posix()
                    destination = args.image_output / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        if digest(destination) != sha256_bytes(payload):
                            raise FileExistsError(f"existing image differs; refusing to overwrite: {destination}")
                    else:
                        destination.write_bytes(payload)
                    all_rows[split].append({
                        "sample_id": f"{sid}:{generator}",
                        "source_group": sid,
                        "group_index": group_index,
                        "split": "development" if split == "dev" else "evaluation",
                        "orientation": orientation_for[sid],
                        "label": "real" if generator == "raise" else "fake",
                        "label_id": 0 if generator == "raise" else 1,
                        "generator": generator,
                        "relative_path": relative,
                        "archive": Path(archive.filename).name,
                        "archive_member": member,
                        "bytes": len(payload),
                        "sha256": sha256_bytes(payload),
                        "image_format": fmt,
                        "width": width,
                        "height": height,
                        "mode": mode,
                    })
                if group_index % 10 == 9:
                    print(f"prepared {split} source groups: {group_index + 1}/{len(group_ids)}", flush=True)

    dev_sha = write_manifest(args.output / "actor0_dev_manifest.jsonl", all_rows["dev"])
    eval_sha = write_manifest(args.output / "actor0_eval_manifest.jsonl", all_rows["eval"])
    summary = {
        "name": "actor0-bfree-20261002",
        "selection_seed": SEED,
        "selection_unit": "source_group",
        "dev_source_groups": len(dev),
        "eval_source_groups": len(evaluation),
        "dev_image_count": len(all_rows["dev"]),
        "eval_image_count": len(all_rows["eval"]),
        "groups_disjoint_from_prior_work": len(available),
        "unused_groups_after_selection": len(available) - len(dev) - len(evaluation),
        "prior_excluded_group_count": len(excluded_groups),
        "prior_exclusion_manifests": excluded_manifests,
        "archive_integrity": archive_hashes,
        "dev_manifest_sha256": dev_sha,
        "eval_manifest_sha256": eval_sha,
        "dev_orientation_groups": dict(Counter(orientation_for[sid] for sid in dev)),
        "eval_orientation_groups": dict(Counter(orientation_for[sid] for sid in evaluation)),
        "dev_generator_counts": dict(Counter(row["generator"] for row in all_rows["dev"])),
        "eval_generator_counts": dict(Counter(row["generator"] for row in all_rows["eval"])),
        "dev_selected_source_groups": dev,
        "eval_selected_source_groups": evaluation,
        "image_root_local": str(args.image_output),
        "known_license": {
            "b_free": "Informational and nonprofit research use; retain notices and cite authors.",
            "raise": "Scientific non-commercial use; retain/cite RAISE license and notice.",
        },
        "preprocessing": "Original PNG bytes extracted from verified B-Free archives; no image transformation.",
        "actor_label_isolation": "Ground truth is retained only in manifests/evaluation code and is never sent in model prompts or tool inputs.",
    }
    summary_path = args.output / "selection_summary.json"
    expected_summary = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if summary_path.exists():
        if summary_path.read_text(encoding="utf-8") != expected_summary:
            raise FileExistsError(f"existing selection summary differs; refusing to overwrite: {summary_path}")
    else:
        write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
