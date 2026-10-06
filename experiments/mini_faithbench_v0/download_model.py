#!/usr/bin/env python3
"""Download the exact frozen Actor-0 Hub snapshot to this experiment's cache."""

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
    snapshot = Path(snapshot_download(
        repo_id="Qwen/Qwen3-VL-8B-Instruct",
        revision=revision,
        cache_dir=str(args.cache_dir),
    )).resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"repo_id": "Qwen/Qwen3-VL-8B-Instruct",
                                       "revision": revision, "snapshot_path": str(snapshot)}, indent=2) + "\n")
    print(snapshot, flush=True)


if __name__ == "__main__":
    main()
