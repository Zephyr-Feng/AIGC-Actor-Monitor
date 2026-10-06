#!/usr/bin/env python3
"""Split aligned semantic tool outputs back into the frozen dev/eval manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev-manifest", type=Path, required=True)
    parser.add_argument("--eval-manifest", type=Path, required=True)
    parser.add_argument("--all-tools", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    dev_ids = {row["sample_id"]: row["sha256"] for row in read_jsonl(args.dev_manifest)}
    eval_ids = {row["sample_id"]: row["sha256"] for row in read_jsonl(args.eval_manifest)}
    if set(dev_ids) & set(eval_ids):
        raise ValueError("development and evaluation sample IDs overlap")
    all_rows = read_jsonl(args.all_tools)
    records = {row["sample_id"]: row for row in all_rows}
    if len(records) != len(all_rows) or set(records) != set(dev_ids) | set(eval_ids):
        raise ValueError("combined semantic tool outputs do not exactly match frozen manifests")
    for sample_id, expected_hash in {**dev_ids, **eval_ids}.items():
        if records[sample_id].get("image_sha256") != expected_hash:
            raise ValueError(f"tool result image hash mismatch: {sample_id}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for split, ids in (("dev", dev_ids), ("eval", eval_ids)):
        path = args.output_dir / f"{split}_tool_observations.jsonl"
        payload = "".join(json.dumps(records[sample_id], ensure_ascii=False, sort_keys=True) + "\n"
                          for sample_id in ids)
        if path.exists() and path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"existing tool observations differ; refusing overwrite: {path}")
        if not path.exists():
            path.write_text(payload, encoding="utf-8", newline="\n")
        outputs[split] = {"count": len(ids), "path": str(path), "sha256": sha256(path)}
    summary = {
        "dev_manifest_sha256": sha256(args.dev_manifest), "eval_manifest_sha256": sha256(args.eval_manifest),
        "combined_tool_results_sha256": sha256(args.all_tools), "outputs": outputs,
        "label_fields_exposed_to_actor": False,
    }
    summary_path = args.output_dir / "tool_observation_split_summary.json"
    summary_text = json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if summary_path.exists() and summary_path.read_text(encoding="utf-8") != summary_text:
        raise FileExistsError(f"existing split summary differs; refusing overwrite: {summary_path}")
    if not summary_path.exists():
        summary_path.write_text(summary_text, encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
