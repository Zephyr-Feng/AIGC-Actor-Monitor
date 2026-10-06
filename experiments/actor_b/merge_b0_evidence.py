#!/usr/bin/env python3
"""Merge newly generated frozen PROBE Evidence-only cards with reused tool outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ORDER = (
    "global_forensic_analyzer",
    "local_texture_analyzer",
    "complementary_forensic_analyzer",
    "provenance_inspector",
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--nonprobe-tools", type=Path, required=True)
    parser.add_argument("--evidence-card-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = read_jsonl(args.manifest)
    existing = {row["sample_id"]: row for row in read_jsonl(args.nonprobe_tools)}
    output = []
    for row in manifest:
        sid = row["sample_id"]
        stem = sid.replace(":", "__")
        card_path = args.evidence_card_dir / f"{stem}.json"
        card = json.loads(card_path.read_text(encoding="utf-8"))
        if card.get("sample_id") != sid:
            raise ValueError(f"card sample mismatch: {sid}")
        forbidden = ("classifier_score", "patch_logits", "image_logit", "probability", "prediction", "verdict")
        lowered = json.dumps(card, ensure_ascii=False).lower()
        if any(key in lowered for key in forbidden):
            raise ValueError(f"classifier leakage in Evidence-only card: {sid}")
        tools = [card, *existing[sid]["tools"]]
        if [item["tool"] for item in tools] != list(ORDER):
            raise ValueError(f"tool order mismatch: {sid}")
        output.append({"sample_id": sid, "image_sha256": row["sha256"], "tools": tools})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                   for row in output), encoding="utf-8")
    print(f"merged {len(output)} Actor-B0 tool records")


if __name__ == "__main__":
    main()

