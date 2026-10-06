"""Validate the structural contract of P0 prefix and outcome ledgers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl, validate_p0  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--prefixes", required=True)
    parser.add_argument("--outcomes", required=True)
    args = parser.parse_args()
    report = validate_p0(
        read_jsonl(args.manifest), read_jsonl(args.prefixes), read_jsonl(args.outcomes)
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
