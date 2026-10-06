#!/usr/bin/env python3
"""Align frozen detector outputs into brand-hidden semantic tool observations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


IMPLEMENTATION = {
    "global_forensic_analyzer": "PROBE-DINOv2",
    "local_texture_analyzer": "PatchCraft",
    "complementary_forensic_analyzer": "SAFE",
    "provenance_inspector": "c2patool + ExifTool",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_csv(path: Path, key: str = "sample_id") -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    indexed = {row[key]: row for row in rows if row.get(key)}
    if len(indexed) != len(rows):
        raise ValueError(f"{path}: missing or duplicate {key}")
    return indexed


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def number(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite {name}: {value!r}")
    return result


def strength(score: float) -> str:
    if score <= 0.10 or score >= 0.90:
        return "high"
    if score <= 0.25 or score >= 0.75:
        return "moderate"
    return "low"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--probe-csv", type=Path, required=True)
    parser.add_argument("--patchcraft-csv", type=Path, required=True)
    parser.add_argument("--safe-jsonl", type=Path, required=True)
    parser.add_argument("--safe-threshold", type=Path, required=True)
    parser.add_argument("--provenance-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    sample_ids = [row["sample_id"] for row in manifest]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("manifest has duplicate sample_id")
    probe = load_csv(args.probe_csv)
    patchcraft = load_csv(args.patchcraft_csv)
    safe_rows = read_jsonl(args.safe_jsonl)
    safe = {row["sample_id"]: row for row in safe_rows}
    provenance = load_csv(args.provenance_csv)
    expected = set(sample_ids)
    for name, rows in (("PROBE", probe), ("PatchCraft", patchcraft), ("SAFE", safe), ("Provenance", provenance)):
        if set(rows) != expected:
            raise ValueError(f"{name} IDs do not exactly match manifest (missing={len(expected-set(rows))}, extra={len(set(rows)-expected)})")
    threshold_doc = json.loads(args.safe_threshold.read_text(encoding="utf-8"))
    safe_threshold = float(threshold_doc["threshold"])
    output_rows = []
    for row in manifest:
        sample_id = row["sample_id"]
        image_path = args.image_root / row["relative_path"]
        image_hash = sha256(image_path)
        if image_hash != row["sha256"]:
            raise ValueError(f"manifest image hash mismatch: {sample_id}")
        probe_score = number(probe[sample_id].get("score", probe[sample_id].get("raw_score")), "PROBE score")
        patch_score = number(patchcraft[sample_id].get("raw_score", patchcraft[sample_id].get("normalized_score")), "PatchCraft score")
        safe_score = number(safe[sample_id].get("fake_probability"), "SAFE fake_probability")
        if safe[sample_id].get("image_sha256") and safe[sample_id]["image_sha256"] != image_hash:
            raise ValueError(f"SAFE image hash mismatch: {sample_id}")

        p_sig = "fake" if probe_score > 0.5 else "real"
        l_sig = "synthetic_like" if patch_score > 0.5 else "real_like"
        s_sig = "fake" if safe_score >= safe_threshold else "real"
        pro_row = provenance[sample_id]
        unified = json.loads(pro_row["unified_output_json"])
        pro_sig = unified.get("verdict", "inconclusive")
        if pro_sig not in ("real", "fake", "inconclusive"):
            pro_sig = "inconclusive"
        provenance_observation = unified.get("observation", "")
        if pro_sig == "inconclusive":
            if str(pro_row.get("actionable", "0")) not in ("1", "True", "true"):
                provenance_observation = "未发现可用的 C2PA 或来源元数据线索，因此来源判断为 inconclusive。"
            else:
                provenance_observation = "发现部分元数据或来源声明，但不足以验证图像起源，因此来源判断为 inconclusive。"
        else:
            provenance_observation = f"检测到经验证的来源凭据，来源倾向为 {pro_sig}。"

        tool_results = [
            {
                "tool": "global_forensic_analyzer", "evidence_type": "global_forensic",
                "signal": p_sig, "score": probe_score, "strength": strength(probe_score),
                "observation": f"全局取证原始合成分数为 {probe_score:.6f}，固定判定阈值为 0.5，信号倾向 {p_sig}。",
                "limitations": "模型输出是证据而非真值；分数强度仅表示原始分数幅度，未校准。",
            },
            {
                "tool": "local_texture_analyzer", "evidence_type": "local_texture",
                "signal": l_sig, "score": patch_score, "strength": strength(patch_score),
                "observation": f"局部纹理原始合成分数为 {patch_score:.6f}，固定判定阈值为 0.5，信号为 {l_sig}。",
                "limitations": "真实图像可能出现局部误报；分数强度未校准。",
            },
            {
                "tool": "complementary_forensic_analyzer", "evidence_type": "complementary_forensic",
                "signal": s_sig, "score": safe_score, "strength": strength(safe_score),
                "observation": f"互补取证原始合成分数为 {safe_score:.6f}，既有独立校准阈值为 {safe_threshold:.10f}，信号倾向 {s_sig}。",
                "limitations": "可能受分布变化影响；阈值来自既有独立校准集，分数强度未校准。",
            },
            {
                "tool": "provenance_inspector", "evidence_type": "provenance",
                "signal": pro_sig, "score": None, "strength": unified.get("strength", "none"),
                "observation": provenance_observation,
                "limitations": "元数据可能缺失、被移除或伪造；没有来源信息不能作为 fake 证据。",
            },
        ]
        output_rows.append({
            "sample_id": sample_id,
            "image_sha256": image_hash,
            "tools": tool_results,
            "internal_implementations": IMPLEMENTATION,
            "tool_score_sources": {
                "probe": str(args.probe_csv), "patchcraft": str(args.patchcraft_csv),
                "safe": str(args.safe_jsonl), "provenance": str(args.provenance_csv),
                "safe_threshold_sha256": hashlib.sha256(args.safe_threshold.read_bytes()).hexdigest(),
            },
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        for row in output_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"samples": len(output_rows), "manifest_sha256": sha256(args.manifest),
                      "safe_threshold": safe_threshold, "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
