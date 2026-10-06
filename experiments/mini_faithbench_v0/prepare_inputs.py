#!/usr/bin/env python3
"""Build frozen Mini FaithBench tool observations from existing Actor-0 data."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


MASKED = {
    "num_atypical_regions",
    "atypical_fraction",
    "max_deviation_percentile",
    "median_deviation_percentile",
}
RENAMED = {
    "observations": "findings",
    "most_atypical_regions": "highlighted_regions",
    "deviation_percentile": "reference_deviation_percentile",
}
GLOBAL = "global_forensic_analyzer"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rename_keys(value):
    if isinstance(value, dict):
        return {RENAMED.get(key, key): rename_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rename_keys(item) for item in value]
    return value


def card_for_condition(card: dict, condition: str) -> dict:
    result = copy.deepcopy(card)
    if condition == "output_rename":
        result["tool"] = "representation_inspector"
    if condition == "summary_mask":
        for key in MASKED:
            result["observations"].pop(key)
    if condition == "output_rename":
        result = rename_keys(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--old-tools", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    old_tools = read_jsonl(args.old_tools)
    if len(manifest) != 300 or len(old_tools) != 300:
        raise ValueError("expected 300 manifest and old-tool rows")
    by_id = {row["sample_id"]: row for row in old_tools}
    if len(by_id) != 300 or set(by_id) != {row["sample_id"] for row in manifest}:
        raise ValueError("old tools do not match frozen manifest")

    outputs = {condition: [] for condition in ("full", "summary_mask", "output_rename")}
    for row in manifest:
        sample_id = row["sample_id"]
        filename = sample_id.replace(":", "__").replace(".", "_") + ".json"
        card = json.loads((args.evidence_dir / "cards" / filename).read_text(encoding="utf-8"))
        if card["sample_id"] != sample_id:
            raise ValueError(f"evidence card mismatch: {sample_id}")
        old = by_id[sample_id]
        if old["image_sha256"] != row["sha256"]:
            raise ValueError(f"image hash mismatch: {sample_id}")
        if {tool["tool"] for tool in old["tools"]} != {
            GLOBAL, "local_texture_analyzer", "complementary_forensic_analyzer", "provenance_inspector"
        }:
            raise ValueError(f"tool set mismatch: {sample_id}")
        for region in card["most_atypical_regions"]:
            if not (args.evidence_dir / region["crop_path"]).is_file():
                raise FileNotFoundError(region["crop_path"])
        for condition in outputs:
            tools = copy.deepcopy(old["tools"])
            for index, tool in enumerate(tools):
                if tool["tool"] == GLOBAL:
                    tools[index] = card_for_condition(card, condition)
            # Dispatcher name remains frozen; only the returned payload identity changes.
            outputs[condition].append({
                "sample_id": sample_id,
                "image_sha256": row["sha256"],
                "tools": tools,
            })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for condition, rows in outputs.items():
        path = args.output_dir / f"{condition}.jsonl"
        if path.exists():
            raise FileExistsError(path)
        path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
        print(f"{condition}: {len(rows)} rows, sha256={sha256(path)}")
    print(f"manifest_sha256={sha256(args.manifest)}")


if __name__ == "__main__":
    main()
