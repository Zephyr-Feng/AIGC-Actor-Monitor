"""Freeze a small orientation-balanced SAFE triage subset from Stage 1 data."""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


PARENT_SHA256 = "f305e5ffd99f3ec9d908494f2dcbfdcb856d7e74dedb8a3dd1130fad0c99660b"
SEED = 20260929
PER_ORIENTATION = 15


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    parent_bytes = args.parent_manifest.read_bytes()
    parent_sha256 = hashlib.sha256(parent_bytes).hexdigest()
    if parent_sha256 != PARENT_SHA256:
        raise ValueError("Stage 1 parent manifest differs from the verified manifest")
    rows = [json.loads(line) for line in parent_bytes.splitlines()]
    groups = defaultdict(list)
    for row in rows:
        groups[row["source_group"]].append(row)

    by_orientation = defaultdict(list)
    for group_id, members in groups.items():
        if Counter(row["generator"] for row in members) != Counter(
            {"raise": 1, "flux": 1, "sd3_5": 1}
        ):
            raise ValueError(f"incomplete source group: {group_id}")
        real = next(row for row in members if row["generator"] == "raise")
        if real["width"] == real["height"]:
            raise ValueError(f"square RAISE image: {group_id}")
        orientation = "landscape" if real["width"] > real["height"] else "portrait"
        by_orientation[orientation].append(group_id)

    rng = random.Random(SEED)
    selected = {
        orientation: sorted(rng.sample(sorted(by_orientation[orientation]), PER_ORIENTATION))
        for orientation in ("landscape", "portrait")
    }
    selected_ids = set(selected["landscape"] + selected["portrait"])
    sample_rows = [row for row in rows if row["source_group"] in selected_ids]
    if len(sample_rows) != 3 * 2 * PER_ORIENTATION:
        raise ValueError("selected sample count is not 90")

    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = args.output_dir / "manifest.jsonl"
    manifest.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in sample_rows),
        encoding="utf-8",
    )
    design = {
        "purpose": "SAFE exploratory triage only; not independent Stage 1 admission",
        "parent_manifest_sha256": parent_sha256,
        "selection_seed": SEED,
        "selection_unit": "source_group",
        "selection_rule": "15 landscape and 15 portrait RAISE source groups sampled without replacement",
        "selected_source_groups": selected,
        "parent_split_counts": dict(Counter(row["split"] for row in sample_rows if row["generator"] == "raise")),
        "sample_count": len(sample_rows),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "preprocessing": "official SAFE eval crop: RGB, CenterCrop(256), ToTensor()",
        "score": "softmax(logits)[1] = fake probability",
        "analysis": "AUC overall and by generator; default 0.5 specificity/recall; landscape/portrait descriptions; no threshold search",
    }
    (args.output_dir / "design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(design, ensure_ascii=False))


if __name__ == "__main__":
    main()
