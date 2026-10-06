#!/usr/bin/env python3
"""Verify the pinned local Qwen snapshot and load its processor on CPU."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import transformers
from transformers import AutoProcessor


RUN = Path("/root/autodl-tmp/actor0-bfree-20261002")
EXPECTED_REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    downloaded = json.loads((RUN / "model_download.json").read_text())
    assert downloaded["revision"] == EXPECTED_REVISION
    snapshot = Path(downloaded["snapshot_path"])
    config = json.loads((snapshot / "config.json").read_text())
    index = json.loads((snapshot / "model.safetensors.index.json").read_text())
    shards = {item.name: item.stat().st_size for item in snapshot.glob("*.safetensors")}
    assert config["model_type"] == "qwen3_vl", config.get("model_type")
    assert set(shards) == set(downloaded["weight_shards"])
    assert shards == downloaded["weight_shards"]
    assert not list(snapshot.glob("*.incomplete"))
    assert sum(shards.values()) >= index["metadata"]["total_size"]

    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    result = {
        "revision": downloaded["revision"],
        "snapshot_path": str(snapshot),
        "model_type": config["model_type"],
        "index_tensor_bytes": index["metadata"]["total_size"],
        "weight_file_bytes": sum(shards.values()),
        "weight_shards": shards,
        "config_sha256": sha256(snapshot / "config.json"),
        "index_sha256": sha256(snapshot / "model.safetensors.index.json"),
        "processor_class": processor.__class__.__name__,
        "image_processor_class": processor.image_processor.__class__.__name__,
        "tokenizer_class": processor.tokenizer.__class__.__name__,
        "transformers": transformers.__version__,
        "python": platform.python_version(),
        "verification": "PASS (local processor/config/index; no GPU inference)",
    }
    target = RUN / "model_verify.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
