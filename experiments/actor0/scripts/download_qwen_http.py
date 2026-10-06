#!/usr/bin/env python3
"""Resume the pinned official Qwen snapshot through Hub's HTTP backend."""

from __future__ import annotations

import json
import os
from pathlib import Path


RUN = Path("/root/autodl-tmp/actor0-bfree-20261002")
REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"

# The Xet CAS hostname has intermittent DNS failures on this AutoDL node.
# Keep the same Hugging Face cache so completed files and compatible partial
# ranges can be reused; only the transfer backend changes.
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_CACHE"] = str(RUN / "model-cache-xet" / "hub")

from huggingface_hub import snapshot_download


def main() -> None:
    repo = "Qwen/Qwen3-VL-8B-Instruct"
    print(f"http_download_start {repo} {REVISION}", flush=True)
    path = Path(snapshot_download(repo_id=repo, revision=REVISION,
                                  cache_dir=os.environ["HF_HUB_CACHE"], max_workers=4))
    shards = {item.name: item.stat().st_size for item in path.glob("*.safetensors")}
    total = sum(shards.values())
    result = {
        "repo_id": repo,
        "revision": REVISION,
        "snapshot_path": str(path),
        "weight_shards": shards,
        "weight_bytes": total,
        "files": sorted(item.name for item in path.iterdir()),
        "transfer": "Hugging Face Hub HTTP backend (HF_HUB_DISABLE_XET=1)",
    }
    (RUN / "model_download.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
