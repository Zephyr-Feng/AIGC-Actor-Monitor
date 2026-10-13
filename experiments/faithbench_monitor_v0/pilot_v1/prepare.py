#!/usr/bin/env python3
"""Derive exactly the approved eight examples, without reading silver annotations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(BASE.parent))
from monitor_protocol import make_packet
from pilot_protocol import enrich_packet, render_pilot_request


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def protocol_hashes():
    names = ("pilot_protocol.py", "prepare.py", "prompt.md", "proposal.schema.json", "run_text.py")
    paths = [BASE / n for n in names] + [BASE.parent / n for n in
            ("monitor_protocol.py", "monitor_response.schema.json", "ANNOTATION_GUIDELINES.md")]
    paths.append(ROOT / "experiments/actor_b/actor_b_protocol.py")
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in paths}


def prepare(source, output):
    if output.exists():
        raise FileExistsError("pilot output exists; do not overwrite it")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("inputs.jsonl", "case_index.json"):
        if sha(source / name) != manifest["artifact_hashes"][name]:
            raise ValueError(f"original artifact changed: {name}")
    selected = [r["case_id"] for r in json.loads((source / "case_index.json").read_text(encoding="utf-8"))]
    if len(selected) != 8 or len(set(selected)) != 8:
        raise ValueError("expected exactly eight unique existing development cases")
    packets = {r["case_id"]: r for r in readl(source / "inputs.jsonl") if r["case_id"] in selected}
    if set(packets) != set(selected):
        raise ValueError("selected input is missing")
    modes = [p["review_mode"] for p in packets.values()]
    if modes.count("terminal") != 5 or modes.count("call_prefix") != 3:
        raise ValueError("expected five terminal and three CALL examples")
    derived, source_hashes = {}, {"original_manifest": sha(manifest_path)}
    counter = 0
    audit = ROOT / "experiments/actor_b/actor_b0_d/audit_assist/work"
    for condition in ("full", "probe_mask", "probe_delay", "tool_rename"):
        work = audit / condition
        for name in ("tools.json", "calls.jsonl", "trajectories.jsonl"):
            path = work / name
            relative = str(path.relative_to(ROOT)).replace("\\", "/")
            digest = sha(path)
            if digest != manifest["source_hashes"][relative]:
                raise ValueError(f"locked source changed: {relative}")
            source_hashes[relative] = digest
        tools = json.loads((work / "tools.json").read_text(encoding="utf-8"))
        calls = readl(work / "calls.jsonl")
        for row in readl(work / "trajectories.jsonl"):
            counter += 1
            cid = f"terminal_{counter:04d}"
            if cid not in packets:
                continue
            original = make_packet(row, tools, "terminal", cid)
            if original != packets[cid]:
                raise ValueError("terminal source mapping differs from original packet")
            enriched = enrich_packet(original)
            # Cross-check reconstruction against the separately retained CALL prefixes.
            for call in calls:
                if call["sample_id"] == row["sample_id"]:
                    prefix = make_packet(call, tools, "call_prefix", call["record_id"])
                    enrich_packet(prefix)  # rejects a budget disagreement
            derived[cid] = enriched
        for row in calls:
            cid = row["record_id"]
            if cid in packets:
                original = make_packet(row, tools, "call_prefix", cid)
                if original != packets[cid]:
                    raise ValueError("CALL source mapping differs from original packet")
                derived[cid] = enrich_packet(original)
    if set(derived) != set(selected):
        raise ValueError("not all approved examples were reconstructed")
    output.mkdir(parents=True)
    ordered = [derived[cid] for cid in selected]
    (output / "inputs.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False)+"\n" for p in ordered), encoding="utf-8")
    for packet in ordered:
        (output / f"{packet['case_id']}_request.txt").write_text(render_pilot_request(packet), encoding="utf-8")
    model = json.loads((ROOT / "experiments/actor_b/config/model_config.json").read_text(encoding="utf-8"))
    record = {"status": "prepared_no_inference", "purpose": "development_only",
              "modality": "text_only", "cases": 8, "terminal": 5, "call_prefix": 3,
              "case_ids": selected, "model": model,
              "generation": {"do_sample": False, "max_new_tokens": 4096,
                             "repetition_penalty": 1.05, "seed": 42, "format_retries": 0},
              "source_hashes": source_hashes, "protocol_hashes": protocol_hashes(),
              "artifact_hashes": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
              "annotations_read": False, "images_loaded": False, "actor_actions_executed": False,
              "semantics_validated": False}
    (output / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("status", "cases", "terminal", "call_prefix", "annotations_read", "images_loaded")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=BASE.parent / "private")
    parser.add_argument("--output", type=Path, default=BASE.parent / "private/pilot_v1")
    args = parser.parse_args()
    prepare(args.source, args.output)
