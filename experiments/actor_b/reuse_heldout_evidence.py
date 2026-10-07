#!/usr/bin/env python3
"""Reuse frozen eval Evidence v1 cards, changing only the callable name alias."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from prepare_b0_subset import read_jsonl


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--frozen-evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cards = args.output_dir / "cards"
    cards.mkdir(parents=True, exist_ok=True)
    provenance = []
    for row in read_jsonl(args.manifest):
        stem = row["sample_id"].replace(":", "__")
        source = args.frozen_evidence_dir / "cards" / f"{stem}.json"
        card = json.loads(source.read_text(encoding="utf-8"))
        if card.get("sample_id") != row["sample_id"] or card.get("tool") != "global_representation_analyzer":
            raise ValueError(f"frozen card identity mismatch: {row['sample_id']}")
        for region in card["most_atypical_regions"]:
            crop = args.frozen_evidence_dir / region["crop_path"]
            if not crop.is_file():
                raise FileNotFoundError(crop)
        adapted = dict(card)
        adapted["tool"] = "global_forensic_analyzer"
        target = cards / source.name
        target.write_text(json.dumps(adapted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        provenance.append({"sample_id": row["sample_id"], "source_sha256": sha256(source),
                           "adapted_sha256": sha256(target)})
    (args.output_dir / "alias_provenance.json").write_text(
        json.dumps({"records": len(provenance), "change": "tool name alias only",
                    "frozen_evidence_dir": str(args.frozen_evidence_dir),
                    "cards": provenance}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reused {len(provenance)} frozen Evidence-only cards; tool alias only")


if __name__ == "__main__":
    main()
