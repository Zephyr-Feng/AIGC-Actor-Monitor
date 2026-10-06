#!/usr/bin/env python3
"""Combine frozen splits and make read-only official PROBE directory aliases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_or_compare(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise FileExistsError(f"existing file differs; refusing to overwrite: {path}")
    else:
        path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-manifest", type=Path, required=True)
    parser.add_argument("--eval-manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    dev, evaluation = read_jsonl(args.dev_manifest), read_jsonl(args.eval_manifest)
    if len(dev) != 180 or len(evaluation) != 300:
        raise ValueError(f"expected 180 dev + 300 eval images, found {len(dev)} + {len(evaluation)}")
    rows = dev + evaluation
    ids = [row["sample_id"] for row in rows]
    dev_groups = {row["source_group"] for row in dev}
    eval_groups = {row["source_group"] for row in evaluation}
    if len(ids) != len(set(ids)) or len(dev_groups) != 60 or len(eval_groups) != 100 or dev_groups & eval_groups:
        raise ValueError("Actor-0 IDs or source-group splits are invalid/overlapping")
    layout = args.output_root / "tool_layout" / "probe"
    for label_dir in ("real", "fake_flux", "fake_sd35"):
        (layout / label_dir).mkdir(parents=True, exist_ok=True)
    for row in rows:
        source = (args.image_root / row["relative_path"]).resolve()
        if sha256(source) != row["sha256"]:
            raise ValueError(f"image hash mismatch: {row['sample_id']}")
        target_dir = {"raise": "real", "flux": "fake_flux", "sd3_5": "fake_sd35"}[row["generator"]]
        target = layout / target_dir / f"{row['source_group']}.png"
        if target.exists() or target.is_symlink():
            if not target.is_symlink() or target.resolve() != source:
                raise FileExistsError(f"existing PROBE alias differs; refusing overwrite: {target}")
        else:
            target.symlink_to(source)
    combined = args.output_root / "manifests" / "actor0_all_manifest.jsonl"
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    write_or_compare(combined, payload)
    summary = {
        "dev_count": len(dev), "eval_count": len(evaluation), "combined_count": len(rows),
        "combined_manifest_sha256": sha256(combined),
        "dev_manifest_sha256": sha256(args.dev_manifest),
        "eval_manifest_sha256": sha256(args.eval_manifest),
        "groups_disjoint": True, "image_sha256_checked": len(rows),
        "probe_alias_count": len(rows), "probe_alias_layout": str(layout),
    }
    write_or_compare(args.output_root / "manifests" / "tool_input_summary.json",
                     json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
