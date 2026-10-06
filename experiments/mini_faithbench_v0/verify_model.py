#!/usr/bin/env python3
"""Verify the pinned Qwen snapshot against the completed Actor-0 run."""

import argparse
import hashlib
import json
from pathlib import Path

from transformers import AutoProcessor


EXPECTED = {
    "model-00001-of-00004.safetensors": "d5d0aef0eb170fc7453a296c43c0849a56f510555d3588e4fd662bb35490aefa",
    "model-00002-of-00004.safetensors": "8be88fb5501e4d5719a6d4cc212e6a13480330e74f3e8c77daa1a68f199106b5",
    "model-00003-of-00004.safetensors": "83de00eafe6e0d57ccd009dbcf71c9974d74df2f016c27afb7e95aafd16b2192",
    "model-00004-of-00004.safetensors": "0a88b98e9f96270973f567e6a2c103ede6ccdf915ca3075e21c755604d0377a5",
}
REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
CONFIG_SHA = "5cd452860dc1e9c29dd71cc3cef7f39b338b7a40793f7a260655c2d3568f3661"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.snapshot_record.read_text())
    snapshot = Path(record["snapshot_path"])
    if record["revision"] != REVISION or REVISION not in snapshot.resolve().parts:
        raise ValueError("snapshot revision mismatch")
    hashes = {name: sha256(snapshot / name) for name in EXPECTED}
    if hashes != EXPECTED:
        raise ValueError("weight shard SHA-256 mismatch")
    config_hash = sha256(snapshot / "config.json")
    if config_hash != CONFIG_SHA:
        raise ValueError("config SHA-256 mismatch")
    config = json.loads((snapshot / "config.json").read_text())
    if config["model_type"] != "qwen3_vl":
        raise ValueError("wrong model architecture")
    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    result = {
        "repo_id": record["repo_id"], "revision": REVISION,
        "snapshot_path": str(snapshot), "config_sha256": config_hash,
        "weight_sha256": hashes, "processor_class": type(processor).__name__,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
