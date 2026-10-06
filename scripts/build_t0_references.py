"""Build same-channel real-image reference ranges for T0 tool descriptions."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.p0 import read_jsonl  # noqa: E402
from actor_monitor.t0 import IMAGE_EXTENSIONS, save_common_channel  # noqa: E402
from agent.tool_env import run_tool  # noqa: E402
from agent.tools import FAMILIES  # noqa: E402


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-dir", type=Path, required=True)
    parser.add_argument("--t0-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()

    excluded = {
        Path(row["original_path"]).name
        for row in read_jsonl(args.t0_manifest)
    }
    candidates = sorted(
        path for path in args.real_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        and path.name not in excluded
    )
    if len(candidates) < args.n:
        raise ValueError(f"only {len(candidates)} unused real images; need {args.n}")
    selected = sorted(random.Random(args.seed).sample(candidates, args.n))

    args.output.mkdir(parents=True, exist_ok=False)
    image_dir = args.output / "images"
    image_dir.mkdir()
    manifest_path = args.output / "manifest.jsonl"
    tools_path = args.output / "tools.jsonl"
    values: dict[str, list[float]] = defaultdict(list)

    with manifest_path.open("w", encoding="utf-8", newline="\n") as manifest_stream, \
         tools_path.open("w", encoding="utf-8", newline="\n") as tool_stream:
        for index, source in enumerate(selected, 1):
            target = image_dir / source.name
            save_common_channel(source, target, args.size)
            image_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            sample_id = f"t0-reference-{source.stem}"
            manifest_stream.write(json.dumps({
                "sample_id": sample_id,
                "source_group_id": f"caption-{source.stem}",
                "label": "real",
                "split": "T0-reference-only",
                "image_path": str(target),
                "image_sha256": image_hash,
                "original_path": str(source),
                "channel": f"center-fit-{args.size}px-jpeg-q90-444",
            }, ensure_ascii=False, sort_keys=True) + "\n")

            results = []
            for family in FAMILIES:
                result = run_tool(family, str(target), region="center")
                results.append({
                    "tool": family,
                    "ok": result.ok,
                    "values": result.values,
                    "error": result.error,
                })
                if result.ok:
                    for feature, value in result.values.items():
                        values[feature].append(value)
            tool_stream.write(json.dumps({
                "sample_id": sample_id,
                "image_sha256": image_hash,
                "results": results,
            }, ensure_ascii=False, sort_keys=True) + "\n")
            manifest_stream.flush()
            tool_stream.flush()
            if index % 10 == 0:
                print(f"{index}/{args.n} reference images", flush=True)

    ranges = {
        feature: [percentile(measurements, 0.05), percentile(measurements, 0.95)]
        for feature, measurements in sorted(values.items())
    }
    (args.output / "references.json").write_text(json.dumps({
        "kind": "T0-discovery-real-only",
        "n_images": args.n,
        "seed": args.seed,
        "channel": f"center-fit-{args.size}px-jpeg-q90-444",
        "ranges": ranges,
        "feature_counts": {key: len(item) for key, item in sorted(values.items())},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved references: {args.output / 'references.json'}")


if __name__ == "__main__":
    main()
