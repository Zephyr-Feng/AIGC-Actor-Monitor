"""Collect only the three fixed CPU tool families for the paired pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl  # noqa: E402
from actor_monitor.pilot_tool_text import FORMAL_FAMILIES  # noqa: E402
from agent.tool_env import run_tool  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.manifest)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(rows, 1):
            image_path = Path(row["image_path"])
            image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if image_hash != row["image_sha256"]:
                raise ValueError(f"{row['sample_id']}: image hash changed")
            results = []
            for family in FORMAL_FAMILIES:
                result = run_tool(family, str(image_path), region="center")
                results.append({
                    "tool": family, "ok": result.ok, "values": result.values,
                    "error": result.error, "elapsed_ms": round(result.elapsed_ms, 2),
                })
            stream.write(json.dumps({
                "sample_id": row["sample_id"], "image_sha256": image_hash,
                "results": results,
            }, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            print(f"{index}/{len(rows)} {row['sample_id']}", flush=True)


if __name__ == "__main__":
    main()
