#!/usr/bin/env python3
"""Export a label-blind image/trajectory bundle for the fixed Actor-0 audit set."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path, PurePosixPath

from PIL import Image, ImageDraw, ImageFont


def read_jsonl(path: Path) -> dict[str, dict]:
    return {row["sample_id"]: row for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())}


def fmt(value: object) -> str:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-sheet", type=int, default=10)
    args = parser.parse_args()

    with args.audit.open(encoding="utf-8-sig", newline="") as stream:
        audit = list(csv.DictReader(stream))
    actor = read_jsonl(args.actor)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    bundle: list[str] = [
        "# Actor-0 eval qualitative audit evidence bundle",
        "",
        "This review aid uses the fixed 50-case set in `qualitative_audit.csv`. Ground-truth labels are intentionally omitted.",
        "",
    ]
    for idx, row in enumerate(audit, 1):
        sid = row["sample_id"]
        record = actor[sid]
        bundle.extend([
            f"## {idx:02d}. {sid}",
            f"- Selection stratum: {row['selection_strata']}",
            f"- Actor verdict: {record.get('final_verdict')} | confidence: {(record.get('final_output') or {}).get('final_confidence')}",
        ])
        for step in record.get("steps", []):
            out = step.get("actor_output") or {}
            obs = step.get("tool_observation") or {}
            bundle.append(f"- Step {step.get('step')}: action `{step.get('action')}`")
            if obs:
                bundle.append(f"  - Tool observation: {obs.get('tool')} | signal={obs.get('signal')} | score={obs.get('score')} — {obs.get('observation')}")
            bundle.append(f"  - Visual: {out.get('visual_observation', '')}")
            bundle.append(f"  - Evidence summary: {fmt(out.get('evidence_summary', []))}")
            bundle.append(f"  - Conflict: {fmt(out.get('unresolved_conflicts', []))}; gap: {out.get('evidence_gap', '')}; reason: {out.get('action_reason', '')}")
        final = record.get("final_output") or {}
        bundle.append(
            "- Final: " + "; ".join(
                f"{key}={fmt(final.get(key))}"
                for key in ("final_verdict", "final_confidence", "supporting_evidence", "contradictory_evidence", "remaining_uncertainty", "stop_reason")
            )
        )
        bundle.append("")
    (args.output_dir / "evidence_bundle.md").write_text("\n".join(bundle), encoding="utf-8")

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    columns, cell_w, cell_h = 3, 320, 270
    for start in range(0, len(audit), args.per_sheet):
        subset = audit[start:start + args.per_sheet]
        rows = (len(subset) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(sheet)
        for offset, item in enumerate(subset):
            idx = start + offset + 1
            record = actor[item["sample_id"]]
            remote_path = PurePosixPath(record["image_path"])
            marker = "/data/eval/"
            if marker not in str(remote_path):
                raise ValueError(f"unexpected image path for {item['sample_id']}: {remote_path}")
            image_path = args.data_root / Path(str(remote_path).split(marker, 1)[1])
            with Image.open(image_path) as source:
                thumb = source.convert("RGB")
                thumb.thumbnail((cell_w - 16, cell_h - 55))
                x = (offset % columns) * cell_w + (cell_w - thumb.width) // 2
                y = (offset // columns) * cell_h + 8
                sheet.paste(thumb, (x, y))
            label = f"{idx} {item['sample_id']}\n{item['selection_strata']}"
            draw.text(((offset % columns) * cell_w + 5, (offset // columns) * cell_h + cell_h - 42), label, fill="black", font=font)
        sheet.save(args.output_dir / f"contact_sheet_{start // args.per_sheet + 1:02d}.jpg", quality=92)


if __name__ == "__main__":
    main()
