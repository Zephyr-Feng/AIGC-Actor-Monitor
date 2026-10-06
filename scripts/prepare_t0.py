"""Create the paired 24-image T0 discovery manifest and common-channel images."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.t0 import prepare_t0  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-dir", type=Path, required=True)
    parser.add_argument("--fake-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-pairs", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()
    rows = prepare_t0(
        args.real_dir, args.fake_dir, args.output,
        n_pairs=args.n_pairs, seed=args.seed, size=args.size,
    )
    print(f"Prepared {len(rows)} T0 images: {args.output / 'manifest.jsonl'}")


if __name__ == "__main__":
    main()
