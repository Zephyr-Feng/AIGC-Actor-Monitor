#!/usr/bin/env python3
"""Select the predeclared 5-per-generator PatchCraft sanity subset."""

import argparse
import hashlib
import json
import random
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261002)
    args = parser.parse_args()

    records = [json.loads(line) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line]
    rng = random.Random(args.seed)
    chosen = set()
    generators = ("raise", "flux", "sd3_5")
    for generator in generators:
        pool = [record for record in records if record["generator"] == generator]
        if len(pool) != 100:
            raise ValueError(f"Expected 100 {generator} samples, got {len(pool)}")
        chosen.update(record["sample_id"] for record in rng.sample(pool, 5))

    selected = [record for record in records if record["sample_id"] in chosen]
    if len(selected) != 15:
        raise ValueError(f"Expected 15 unique sanity samples, got {len(selected)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        for record in selected:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({
        "seed": args.seed,
        "counts": {generator: sum(r["generator"] == generator for r in selected) for generator in generators},
        "sample_ids": [r["sample_id"] for r in selected],
        "manifest_sha256": sha256(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
