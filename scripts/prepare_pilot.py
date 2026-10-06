"""Build a pilot set disjoint from T0 and its real-image reference pool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl  # noqa: E402
from actor_monitor.pilot import prepare_pilot  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-dir", type=Path, required=True)
    parser.add_argument("--fake-dir", type=Path, required=True)
    parser.add_argument("--exclude-manifest", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-pairs", type=int, required=True)
    parser.add_argument("--seed", type=int, default=220928)
    args = parser.parse_args()
    excluded = {
        row["source_group_id"]
        for manifest in args.exclude_manifest
        for row in read_jsonl(manifest)
    }
    rows = prepare_pilot(
        args.real_dir, args.fake_dir, args.output, excluded,
        n_pairs=args.n_pairs, seed=args.seed,
    )
    print(f"Saved {len(rows)} images from {len(rows) // 2} disjoint source pairs")


if __name__ == "__main__":
    main()
