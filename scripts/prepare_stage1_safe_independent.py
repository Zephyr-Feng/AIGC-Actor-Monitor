#!/usr/bin/env python3
"""Freeze group-disjoint SAFE calibration/screening and extract only scored PNGs."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from prepare_stage1_expert_data import EXPECTED_MD5, PREFIXES, file_hash, image_members, write_json


SEED = 2026092910
EXPECTED_SHA256 = {
    "real_RAISE_1k.zip": "bd25842eb4069937d6676a31538bb557dc78db9867fa6e463df5af11d86fa73e",
    "sd3_flux.zip": "92a1d7f4f33e9a34c4556c3677e190a6db63ff6821fff98425271926013116b6",
}
PRIOR_MANIFEST_SHA256 = "f305e5ffd99f3ec9d908494f2dcbfdcb856d7e74dedb8a3dd1130fad0c99660b"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-archive", type=Path, required=True)
    parser.add_argument("--generated-archive", type=Path, required=True)
    parser.add_argument("--prior-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    archives = (args.real_archive, args.generated_archive)
    archive_info = {}
    for path in archives:
        if path.name not in EXPECTED_MD5:
            raise ValueError(f"Unexpected archive {path.name}")
        md5, sha256 = file_hash(path, "md5"), file_hash(path, "sha256")
        if md5 != EXPECTED_MD5[path.name] or sha256 != EXPECTED_SHA256[path.name]:
            raise ValueError(f"Archive digest mismatch: {path.name}: {md5}, {sha256}")
        archive_info[path.name] = {"bytes": path.stat().st_size, "md5": md5, "sha256": sha256}

    if file_hash(args.prior_manifest, "sha256") != PRIOR_MANIFEST_SHA256:
        raise ValueError("Prior manifest digest mismatch")
    prior_records = [json.loads(line) for line in args.prior_manifest.read_text(encoding="utf-8").splitlines()]
    prior_ids = {record["source_group"] for record in prior_records}
    if len(prior_ids) != 200 or len(prior_records) != 600:
        raise ValueError("Expected 200 prior groups and 600 images")

    with ZipFile(args.real_archive) as real_zip, ZipFile(args.generated_archive) as generated_zip:
        zips = {"raise": real_zip, "flux": generated_zip, "sd3_5": generated_zip}
        members = {name: image_members(zips[name], PREFIXES[name]) for name in zips}
        ids = set(members["raise"])
        if len(ids) != 1000 or any(set(item) != ids for item in members.values()):
            raise ValueError("Expected 1,000 matching source groups")
        if not prior_ids <= ids:
            raise ValueError("Prior groups absent from archives")

        by_orientation = {"landscape": [], "portrait": []}
        for source_id in sorted(ids - prior_ids):
            with real_zip.open(members["raise"][source_id]) as stream:
                header = stream.read(24)
            if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
                raise ValueError(f"Invalid PNG header: {source_id}")
            width = int.from_bytes(header[16:20], "big")
            height = int.from_bytes(header[20:24], "big")
            if width == height:
                raise ValueError(f"Square RAISE image: {source_id}")
            by_orientation["landscape" if width > height else "portrait"].append(source_id)
        if {key: len(value) for key, value in by_orientation.items()} != {"landscape": 608, "portrait": 192}:
            raise ValueError("Unexpected unused-group orientation counts")

        rng = random.Random(SEED)
        for key in ("landscape", "portrait"):
            rng.shuffle(by_orientation[key])
        groups = {
            "calibration": by_orientation["landscape"][:70] + by_orientation["portrait"][:30],
            "screening": by_orientation["landscape"][70:140] + by_orientation["portrait"][30:60],
        }
        if len(set(groups["calibration"] + groups["screening"])) != 200:
            raise ValueError("New split overlap")
        design = {
            "seed": SEED,
            "randomization": "sort IDs in each orientation; shuffle landscape then portrait with one Python random.Random(seed); first 70/30 calibration, next 70/30 screening",
            "groups": groups,
            "prior_manifest_sha256": PRIOR_MANIFEST_SHA256,
            "archive_integrity": archive_info,
            "threshold_rule": "k=ceil(100*0.80)=80; t=nextafter(80th ascending calibration real score,+inf); fake iff score>=t",
            "screening_gate": {"real_correct_min": 80, "flux_correct_min": 70, "sd3_5_correct_min": 70, "orientation_real_specificity_warning_below": 0.70},
            "screened_images": 400,
        }
        args.output.mkdir(parents=True)
        write_json(args.output / "design.json", design)
        licenses = args.output / "licenses"
        licenses.mkdir()
        for member, filename in (("real_RAISE_1k/RAISE_License.pdf", "RAISE_License.pdf"), ("real_RAISE_1k/README.txt", "RAISE_README.txt")):
            (licenses / filename).write_bytes(real_zip.read(member))

        records = []
        for split, group_ids in groups.items():
            for group_index, source_id in enumerate(group_ids):
                sources = ("raise",) if split == "calibration" else ("raise", "flux", "sd3_5")
                for generator in sources:
                    member = members[generator][source_id]
                    payload = zips[generator].read(member)
                    with Image.open(io.BytesIO(payload)) as image:
                        image.load()
                        image_format, (width, height), mode = image.format, image.size, image.mode
                    if image_format != "PNG" or mode != "RGB":
                        raise ValueError(f"Unexpected image format or mode: {member}")
                    relative_path = Path("images", split, generator, f"{source_id}.png")
                    destination = args.output / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(payload)
                    records.append({
                        "sample_id": f"{source_id}:{generator}", "source_group": source_id,
                        "group_index": group_index, "split": split,
                        "label": "real" if generator == "raise" else "fake", "generator": generator,
                        "relative_path": relative_path.as_posix(),
                        "archive": args.real_archive.name if generator == "raise" else args.generated_archive.name,
                        "archive_member": member, "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "image_format": image_format, "width": width, "height": height, "mode": mode,
                        "orientation": "landscape" if source_id in by_orientation["landscape"] else "portrait",
                    })
            print(f"Extracted {split}: {len(group_ids)} groups", flush=True)

        with (args.output / "manifest.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        summary = {
            "created_date": "2026-09-29", "name": args.output.name,
            "image_count": len(records), "image_bytes": sum(record["bytes"] for record in records),
            "generator_counts": dict(Counter(record["generator"] for record in records)),
            "split_counts": dict(Counter(record["split"] for record in records)),
            "design_sha256": file_hash(args.output / "design.json", "sha256"),
            "manifest_sha256": file_hash(args.output / "manifest.jsonl", "sha256"),
            "license": {"b_free": "informational and nonprofit use; retain notices and cite authors", "raise": "scientific non-commercial use; cite RAISE; retain copyright, license, and original link"},
            "usage": "Stage 1 SAFE independent calibration and screening only; excluded from Stages 2-4",
        }
        if len(records) != 400 or summary["generator_counts"] != {"raise": 200, "flux": 100, "sd3_5": 100}:
            raise ValueError("Unexpected extracted image counts")
        write_json(args.output / "dataset_summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
