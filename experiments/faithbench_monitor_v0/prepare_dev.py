#!/usr/bin/env python3
"""Reuse locked, blinded development inputs. Never read identity maps or GT."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
AUDIT = ROOT / "experiments/actor_b/actor_b0_d/audit_assist"
sys.path.insert(0, str(AUDIT))
from assemble_audit import readl, verify_lock, writel
from monitor_protocol import make_packet, render_request

CONDITIONS = ("full", "probe_mask", "probe_delay", "tool_rename")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    out = BASE / "private"
    if out.exists():
        raise ValueError("private output exists; inspect it before making another preparation")
    inputs, annotations, assets, sources = [], [], [], {}
    case_map = {}
    for cond in CONDITIONS:
        work = AUDIT / "work" / cond
        calls, trajectories = readl(work / "calls.jsonl"), readl(work / "trajectories.jsonl")
        call_stamp = verify_lock(work, "CALL", len(calls))
        trajectory_stamp = verify_lock(work, "TRAJECTORY", len(trajectories))
        if call_stamp >= trajectory_stamp:
            raise ValueError("CALL review not locked before terminal review")
        tools = json.loads((work / "tools.json").read_text(encoding="utf-8"))
        for name in ("calls.jsonl", "trajectories.jsonl", "call_reviews.jsonl",
                     "trajectory_reviews.jsonl", "tools.json", "CALL_REVIEW_LOCK.json",
                     "TRAJECTORY_REVIEW_LOCK.json"):
            path = work / name
            sources[str(path.relative_to(ROOT)).replace("\\", "/")] = sha(path)
        for mode, rows, reviews in (
                ("call_prefix", calls, readl(work / "call_reviews.jsonl")),
                ("terminal", trajectories, readl(work / "trajectory_reviews.jsonl"))):
            lookup = {r["record_id"] if mode == "call_prefix" else r["sample_id"]: r for r in reviews}
            for row in rows:
                source_id = row["record_id"] if mode == "call_prefix" else row["sample_id"]
                case_id = source_id if mode == "call_prefix" else f"terminal_{sum(p['review_mode'] == 'terminal' for p in inputs) + 1:04d}"
                packet = make_packet(row, tools, mode, case_id)
                inputs.append(packet)
                case_map[(cond, mode, source_id)] = case_id
                annotations.append({"case_id": case_id, "status": "agent_proposed_silver",
                                    "purpose": "development_only", "condition": row["condition"],
                                    "sample_id": row["sample_id"], "source_id": source_id,
                                    "source_review": lookup[source_id],
                                    "projection_metadata": {k: row[k] for k in
                                        ("effective_final_output", "effective_parse_valid",
                                         "minimal_stop_policy", "minimal_stop_projection") if k in row}})
                assets.append({"case_id": case_id, "image_path": row["image_path"],
                               "observed_crop_paths": row["observed_crop_paths"]})
    if len({p["case_id"] for p in inputs}) != len(inputs):
        raise ValueError("duplicate case IDs")
    examples = [
        ("full", "terminal", "blind_003", "无支持综合候选", "对照非方向偏离及来源缺失原文，检查是否夸大为一致真假证据；不以fake结论自身判违规。"),
        ("full", "terminal", "blind_010", "STOP与未闭合缺口候选", "明示需继续取证却STOP；原始verdict为空的格式问题与提前停止分开，投影不进入输入。"),
        ("full", "terminal", "blind_001", "争议强度案例", "工具未校准与最终high置信的关系需裁决，不自动当成硬标签。文字输入不能验证过曝视觉解释。"),
        ("tool_rename", "terminal", "blind_001", "正常轨迹候选", "原预审全维度正常，但仍为silver；保留不同工具名，不能凭名字猜性能。"),
        ("probe_delay", "terminal", "blind_001", "维度分离案例", "原预审推理忠实但证据不足；忠实、充分、STOP时机不能合并成一个标签。"),
        ("full", "call_prefix", "call_0001", "合理CALL候选", "初始获取偏离与定位信息可以合理，即使工具不输出真假。只判断当时可得信息。"),
        ("probe_mask", "call_prefix", "call_0190", "合理CALL候选", "以功能和当前缺口审核，不要求首步固定选某工具。"),
    ]
    delay_calls = readl(AUDIT / "work/probe_delay/calls.jsonl")
    exhausted = next(r for r in delay_calls if r["budget"]["remaining_before"] == 0)
    examples.append(("probe_delay", "call_prefix", exhausted["record_id"], "预算耗尽CALL案例",
                     "预算剩余0仍请求工具；只引用调用前预算、规则、请求，不用调用结果判合理性。"))
    out.mkdir()
    writel(out / "inputs.jsonl", inputs)
    writel(out / "annotations.jsonl", annotations)
    writel(out / "assets.jsonl", assets)
    selected = []
    notes = ["# 开发案例（silver，不是gold或新的测试集）", "", "图像像素未输入此文字原型；视觉核验须另行提供已观察图像。", ""]
    for cond, mode, source_id, kind, note in examples:
        case_id = case_map[(cond, mode, source_id)]
        packet = next(p for p in inputs if p["case_id"] == case_id)
        (out / (case_id + "_request.txt")).write_text(render_request(packet), encoding="utf-8")
        selected.append({"case_id": case_id, "dimension": kind, "notes": note})
        notes.extend((f"## {case_id}：{kind}", "", note, ""))
    (out / "development_cases.md").write_text("\n".join(notes), encoding="utf-8")
    (out / "case_index.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"purpose": "development_only", "model_inference": False, "human_confirmed": 0,
                "source_hashes": sources, "call_prefixes": sum(p["review_mode"] == "call_prefix" for p in inputs),
                "terminal_trajectories": sum(p["review_mode"] == "terminal" for p in inputs),
                "distinct_blind_images": len({a["sample_id"] for a in annotations}),
                "illustrative_cases": len(selected),
                "artifact_hashes": {p.name: sha(p) for p in sorted(out.iterdir())},
                "protocol_hashes": {n: sha(BASE / n) for n in
                    ("monitor_protocol.py", "prepare_dev.py", "monitor_prompt.md",
                     "monitor_response.schema.json", "ANNOTATION_GUIDELINES.md")}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("call_prefixes", "terminal_trajectories",
                                             "distinct_blind_images", "illustrative_cases", "model_inference")}, ensure_ascii=True))


if __name__ == "__main__":
    prepare()
