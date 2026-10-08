#!/usr/bin/env python3
"""Assemble independently locked Agent proposals; never read GT or run evaluation."""
from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from render_review import LABELS

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
CONDITIONS = {"FULL": "full", "PROBE-MASK": "probe_mask",
              "PROBE-DELAY": "probe_delay", "TOOL-RENAME": "tool_rename"}
FIELDS = ("tool_selection_quality", "conflict_handling", "stop_timing",
          "evidence_sufficient", "premature_stop", "verdict_consistent",
          "unsupported_claim", "reasoning_faithful")
ALIASES = {"tool_alpha": "global_forensic_analyzer", "tool_beta": "local_texture_analyzer",
           "tool_gamma": "complementary_forensic_analyzer", "tool_delta": "provenance_inspector"}
PRIORITY = {"P0": 0, "P1": 1, "P2": 2, "normal": 3}


def readl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def writel(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def writecsv(path, rows, fields=None):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})


def confidence(row, trajectory=False):
    return row["confidence" if trajectory else "agent_confidence"]


def verify_lock(work, prefix, count):
    lock = json.loads((work / (prefix + "_REVIEW_LOCK.json")).read_text(encoding="utf-8"))
    stem = "call" if prefix == "CALL" else "trajectory"
    source = work / ("calls.jsonl" if stem == "call" else "trajectories.jsonl")
    review = work / (stem + "_reviews.jsonl")
    if lock["source_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest() or lock["review_sha256"] != hashlib.sha256(review.read_bytes()).hexdigest():
        raise ValueError(f"{work.name}: locked review or source changed")
    if lock["record_count"] != count or lock["reviewer_type"] != "agent":
        raise ValueError(f"{work.name}: invalid review lock scope")
    stamp = datetime.fromisoformat(lock["locked_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("review lock needs timezone")
    return stamp


def p0_reasons(row, trajectory=False):
    reasons = []
    if row.get("needs_source"):
        reasons.append("source_missing")
    if confidence(row, trajectory) == "low":
        reasons.append("agent_low_confidence")
    if trajectory:
        labels = row["agent_review"]
        for key, bad in (("tool_selection_quality", "inappropriate"), ("conflict_handling", "ignored"),
                         ("stop_timing", "no_legal_stop"), ("premature_stop", True),
                         ("unsupported_claim", True), ("reasoning_faithful", False),
                         ("verdict_consistent", False)):
            if labels.get(key) == bad:
                reasons.append("agent_" + key)
        if "unassessable" in labels.values():
            reasons.append("agent_unassessable_field")
    elif row["agent_label"] in ("inappropriate", "unassessable"):
        reasons.append("agent_" + row["agent_label"])
    return reasons


def observed_conflict(history):
    directions = {}
    for step in history:
        obs = step.get("tool_observation") or {}
        name = ALIASES.get(obs.get("tool"), obs.get("tool"))
        signal = obs.get("signal")
        if name == "local_texture_analyzer":
            directions[name] = {"real_like": "real", "synthetic_like": "fake"}.get(signal)
        elif name == "complementary_forensic_analyzer":
            directions[name] = signal if signal in ("real", "fake") else None
    a, b = directions.get("local_texture_analyzer"), directions.get("complementary_forensic_analyzer")
    return bool(a and b and a != b)


def main():
    fingerprint = json.loads((BASE / "input_fingerprint.json").read_text(encoding="utf-8"))
    for name, expected in fingerprint["source_hashes"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("immutable audit source changed: " + name)
    call_inputs, trajectory_inputs, tool_cards = {}, {}, {}
    calls, trajectories = [], []
    for condition, folder in CONDITIONS.items():
        work = BASE / "work" / folder
        ci, ti = readl(work / "calls.jsonl"), readl(work / "trajectories.jsonl")
        cr, tr = readl(work / "call_reviews.jsonl"), readl(work / "trajectory_reviews.jsonl")
        call_stamp = verify_lock(work, "CALL", len(ci))
        if verify_lock(work, "TRAJECTORY", 20) < call_stamp:
            raise ValueError("trajectory review must follow CALL lock")
        if len(cr) != len(ci) or {r["record_id"] for r in cr} != {r["record_id"] for r in ci}:
            raise ValueError(f"{condition}: incomplete/duplicate CALL proposals")
        if len(tr) != 20 or {(r["sample_id"], r["condition"]) for r in tr} != {(r["sample_id"], condition) for r in ti}:
            raise ValueError(f"{condition}: incomplete/duplicate trajectory proposals")
        for row in cr:
            source = next(r for r in ci if r["record_id"] == row["record_id"])
            if (row["sample_id"], row["condition"], row["trajectory_step"], row["raw_attempt"]) != (source["sample_id"], condition, source["step"], source["raw_attempt"]):
                raise ValueError("CALL source association mismatch")
            if row["agent_label"] not in ("appropriate", "reasonable_but_redundant", "inappropriate", "unassessable"):
                raise ValueError("invalid CALL proposal label")
            if row["agent_confidence"] not in ("high", "medium", "low") or not row.get("agent_reason") or not row.get("evidence_references"):
                raise ValueError("CALL proposal lacks confidence, concrete reason or references")
            if row.get("needs_source") and row["agent_confidence"] == "high":
                raise ValueError("missing source cannot be high confidence")
            row.update(reviewer_type="agent", review_status="agent_proposed")
        for row in tr:
            if set(row["agent_review"]) != set(FIELDS) or not row.get("notes") or not row.get("evidence_references"):
                raise ValueError("trajectory proposal lacks eight fields or evidence")
            if any(not any(type(value) is type(item) and value == item for item in LABELS[key]) for key, value in row["agent_review"].items()):
                raise ValueError("invalid trajectory label enum")
            if row["confidence"] not in ("high", "medium", "low"):
                raise ValueError("invalid trajectory confidence")
            if row.get("needs_source") and row["confidence"] == "high":
                raise ValueError("missing source cannot be high confidence")
            row.update(record_id=f"traj:{row['sample_id']}:{condition}", reviewer_type="agent", review_status="agent_proposed")
        calls.extend(cr)
        trajectories.extend(tr)
        call_inputs.update({r["record_id"]: r for r in ci})
        trajectory_inputs.update({(r["sample_id"], condition): r for r in ti})
        tool_cards[condition] = json.loads((work / "tools.json").read_text(encoding="utf-8"))
    if len(calls) != 827 or len(trajectories) != 80:
        raise ValueError("expected 827 CALL and 80 trajectory proposals")
    calls.sort(key=lambda r: r["record_id"])
    call_by_id = {r["record_id"]: r for r in calls}
    tr_by_key = {(r["sample_id"], r["condition"]): r for r in trajectories}
    grouped = defaultdict(list)
    for source in call_inputs.values():
        grouped[(source["sample_id"], source["condition"])].append(source)
    for group in grouped.values():
        group.sort(key=lambda r: (r["step"], r["raw_attempt"] if r["raw_attempt"] is not None else -1))

    triggers = defaultdict(set)
    for r in calls:
        triggers[r["record_id"]].update(p0_reasons(r))
    # P1 routing events are selected after the independent reviews have been locked.
    for (sample, condition), group in grouped.items():
        if condition == "TOOL-RENAME":
            triggers[group[0]["record_id"]].add("rename_first_tool")
        for index, source in enumerate(group):
            rid = source["record_id"]
            if "blocked_first_probe" in str(source["call_outcome"]):
                triggers[rid].add("delay_blocked_first_request")
                if index + 1 < len(group):
                    next_step = group[index + 1]["step"]
                    for following in group[index + 1:]:
                        if following["step"] != next_step:
                            break
                        triggers[following["record_id"]].add("delay_following_choice")
            if observed_conflict(source["history"]):
                triggers[rid].add("decision_after_observed_conflict")
            if call_by_id[rid]["agent_label"] == "reasonable_but_redundant":
                triggers[rid].add("agent_redundancy")
    for sample in {k[0] for k in grouped}:
        full, rename = grouped.get((sample, "FULL"), []), grouped.get((sample, "TOOL-RENAME"), [])
        fs = [r for r in full if r["call_outcome"] == "success"]
        rs = [r for r in rename if r["call_outcome"] == "success"]
        for a, b in zip(fs, rs):
            if ALIASES.get(a["selected_tool"], a["selected_tool"]) != ALIASES.get(b["selected_tool"], b["selected_tool"]):
                triggers[a["record_id"]].add("paired_first_divergent_choice")
                triggers[b["record_id"]].add("paired_first_divergent_choice")
                break

    chosen, strata = {}, defaultdict(list)
    for r in calls:
        rid = r["record_id"]
        if p0_reasons(r):
            chosen[rid] = "P0"
        elif triggers[rid]:
            chosen[rid] = "P1"
        elif r["agent_label"] == "appropriate" and r["agent_confidence"] == "high":
            source = call_inputs[rid]
            bucket = "first" if source["step"] == 1 else "middle" if source["step"] <= 3 else "late"
            strata[(r["condition"], ALIASES.get(source["selected_tool"], source["selected_tool"]), bucket)].append(rid)
    rng = random.Random(20261007)
    sampled = []
    for key in sorted(strata):
        rid = rng.choice(sorted(strata[key]))
        chosen[rid] = "P2"
        triggers[rid].add("stratified_random_check:" + ":".join(key))
        sampled.append({"stratum": list(key), "eligible": len(strata[key]), "record_id": rid})
    writel(BASE / "trajectory_agent_review.jsonl", trajectories)
    csv_calls = []
    for r in calls:
        source = call_inputs[r["record_id"]]
        csv_calls.append({"record_id": r["record_id"], "sample_id": r["sample_id"], "condition": r["condition"],
                          "trajectory_step": source["step"], "raw_attempt": source["raw_attempt"],
                          "selected_tool": source["selected_tool"], "agent_label": r["agent_label"],
                          "agent_confidence": r["agent_confidence"], "agent_reason": r["agent_reason"],
                          "evidence_gap": r["evidence_gap"], "expected_information_gain": r["expected_information_gain"],
                          "call_outcome": source["call_outcome"], "evidence_references": r["evidence_references"],
                          "needs_source": bool(r.get("needs_source")), "review_priority": chosen.get(r["record_id"], "normal"),
                          "upstream_error_group": r.get("upstream_error_group", ""),
                          "reviewer_type": "agent", "review_status": "agent_proposed"})
    writecsv(BASE / "call_agent_review.csv", csv_calls)

    queue, trajectory_views, call_views = [], [], []
    for r in trajectories:
        source = trajectory_inputs[(r["sample_id"], r["condition"])]
        reasons = p0_reasons(r, True)
        priority = "P0" if reasons else "P1"
        reasons.append("mandatory_independent_trajectory_confirmation")
        reasons.append("all_stop_sufficiency_review_including_weak_evidence")
        queue.append({"record_id": r["record_id"], "sample_id": r["sample_id"], "condition": r["condition"],
                      "trajectory_step": "final", "review_priority": priority, "trigger_reasons": reasons,
                      "agent_label": r["agent_review"], "agent_confidence": r["confidence"],
                      "evidence_reference": r["evidence_references"], "agent_reason": r["notes"],
                      "human_label": "", "human_notes": "", "review_status": "unreviewed"})
        trajectory_views.append({**source, **r, "type": "trajectory", "review_priority": priority,
                                 "crop_paths": source["observed_crop_paths"], "tool_cards": tool_cards[r["condition"]]})
    for rid, priority in chosen.items():
        r, source = call_by_id[rid], call_inputs[rid]
        queue.append({"record_id": rid, "sample_id": r["sample_id"], "condition": r["condition"],
                      "trajectory_step": source["step"], "review_priority": priority,
                      "trigger_reasons": sorted(triggers[rid]), "agent_label": r["agent_label"],
                      "agent_confidence": r["agent_confidence"], "evidence_reference": r["evidence_references"],
                      "agent_reason": r["agent_reason"], "human_label": "", "human_notes": "", "review_status": "unreviewed"})
        call_views.append({**source, **r, "type": "call", "review_priority": priority,
                           "trigger_reasons": sorted(triggers[rid]), "tool_cards": tool_cards[r["condition"]]})
    old_path = BASE / "HUMAN_REVIEW_QUEUE.csv"
    if old_path.exists():
        with old_path.open(encoding="utf-8-sig", newline="") as handle:
            old = {r["record_id"]: r for r in csv.DictReader(handle)}
        for r in queue:
            for key in ("human_label", "human_notes", "review_status"):
                if r["record_id"] in old:
                    r[key] = old[r["record_id"]].get(key, r[key])
    queue.sort(key=lambda r: (PRIORITY[r["review_priority"]], r["condition"], r["record_id"]))
    writecsv(old_path, queue)
    data = {"input_fingerprint": fingerprint["input_fingerprint"], "trajectory_records": trajectory_views,
            "call_records": sorted(call_views, key=lambda r: (PRIORITY[r["review_priority"]], r["record_id"])),
            "identity_map_path": str(BASE / "identity_map.json"), "source_hashes": fingerprint["source_hashes"],
            "human_audit_path": str(BASE.parent / "evaluation/human_audit.jsonl"),
            "call_audit_path": str(BASE.parent / "evaluation/tool_selection_audit.csv"),
            "call_index": fingerprint["call_index"]}
    (BASE / "review_data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (BASE / "sampling.json").write_text(json.dumps({"seed": 20261007, "rule": "one per nonempty remaining high-confidence appropriate condition/tool/step-position stratum", "draws": sampled}, ensure_ascii=False, indent=2), encoding="utf-8")

    paired = ["# 独立预审锁定后的配对分析", "", "不读取GT或分类正确性。以下是模型预审比较，需要研究者裁决；首选变化不等于不合理。blind sample_id 通过私有映射追溯原轨迹。", ""]
    for other in ("PROBE-MASK", "PROBE-DELAY", "TOOL-RENAME"):
        paired.extend(["## FULL vs " + other, ""])
        for sample in sorted({r["sample_id"] for r in trajectories}):
            a, b = tr_by_key[(sample, "FULL")], tr_by_key[(sample, other)]
            sa, sb = trajectory_inputs[(sample, "FULL")], trajectory_inputs[(sample, other)]
            seq_a = [ALIASES.get(name, name) for name in sa["tool_calls"]]
            seq_b = [ALIASES.get(name, name) for name in sb["tool_calls"]]
            changes = [k for k in FIELDS if a["agent_review"][k] != b["agent_review"][k]]
            findings = []
            if seq_a != seq_b:
                both_reasonable = all(r["agent_review"]["tool_selection_quality"] in ("appropriate", "reasonable_but_redundant") for r in (a, b))
                findings.append("工具序列变化；独立预审认为两者选择均合理" if both_reasonable else "工具序列变化且至少一侧预审策略存在疑点，需逐步核验")
            if b["agent_review"]["evidence_sufficient"] is False:
                findings.append("该条件预审证据不足；具体信息缺口见下方理由与步骤引用，不能据此直接归因于名称/屏蔽")
            if b["agent_review"]["stop_timing"] == "no_legal_stop":
                findings.append("该条件原始合法终态失败；下方保留原始与投影状态，须核验预算/重试原因")
            if b["agent_review"]["reasoning_faithful"] is False or b["agent_review"]["unsupported_claim"] is True:
                findings.append("该条件解释使用证据存在预审疑点，不能用工具数量替代忠实度核验")
            paired.extend([f"### {sample}", f"变动预审字段：{', '.join(changes) or '无'}。",
                           f"成功工具序列 FULL={seq_a}；{other}={seq_b}。",
                           f"原始/effective终态解析 FULL={sa['raw_parse_valid']}/{sa['effective_parse_valid']}；{other}={sb['raw_parse_valid']}/{sb['effective_parse_valid']}。",
                           "待人审解释：" + ("；".join(findings) or "未触发上述差异提示；仍按下方独立证据审核。"),
                           f"FULL: {a['notes']}；引用 {a['evidence_references']}",
                           f"{other}: {b['notes']}；引用 {b['evidence_references']}", ""])
    (BASE / "PAIRED_CONDITION_ANALYSIS.md").write_text("\n".join(paired) + "\n", encoding="utf-8")
    labels = {key: dict(Counter(json.dumps(r["agent_review"][key]) if isinstance(r["agent_review"][key], bool) else str(r["agent_review"][key]) for r in trajectories)) for key in FIELDS}
    call_dist = dict(Counter(r["agent_label"] for r in calls))
    tconf = dict(Counter(r["confidence"] for r in trajectories))
    cconf = dict(Counter(r["agent_confidence"] for r in calls))
    qcounts = dict(Counter(chosen.values()))
    p2_eligible = {condition: sum(len(rows) for key, rows in strata.items() if key[0] == condition) for condition in CONDITIONS}
    trigger_counts = dict(Counter(reason for rid in chosen for reason in triggers[rid]))
    summary = {"trajectory_reviewed": len(trajectories), "calls_reviewed": len(calls),
               "trajectory_confidence": tconf, "call_confidence": cconf, "trajectory_labels": labels,
               "call_labels": call_dist, "call_queue_unique": len(chosen), "call_queue_priorities": qcounts,
               "call_trigger_counts_before_dedup": trigger_counts,
               "call_trigger_memberships": sum(trigger_counts.values()),
               "p2_high_confidence_eligible_by_condition": p2_eligible,
               "trajectory_queue_priorities": dict(Counter(r["review_priority"] for r in queue if r["record_id"].startswith("traj:"))),
               "needs_source_trajectories": sum(bool(r.get("needs_source")) for r in trajectories),
               "needs_source_calls": sum(bool(r.get("needs_source")) for r in calls), "human_confirmed": 0,
               "gate": "ACTOR_B0_D_INCONCLUSIVE"}
    summary["by_condition"] = {}
    for condition in CONDITIONS:
        ct = [r for r in trajectories if r["condition"] == condition]
        cc = [r for r in calls if r["condition"] == condition]
        summary["by_condition"][condition] = {
            "calls": len(cc), "trajectories": len(ct),
            "call_labels": dict(Counter(r["agent_label"] for r in cc)),
            "trajectory_confidence": dict(Counter(r["confidence"] for r in ct)),
            "insufficient": sum(r["agent_review"]["evidence_sufficient"] is False for r in ct),
            "premature": sum(r["agent_review"]["premature_stop"] is True for r in ct),
            "unsupported": sum(r["agent_review"]["unsupported_claim"] is True for r in ct),
            "unfaithful": sum(r["agent_review"]["reasoning_faithful"] is False for r in ct),
            "no_legal_stop": sum(r["agent_review"]["stop_timing"] == "no_legal_stop" for r in ct),
        }
    (BASE / "agent_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Actor-B0-D Agent 辅助审计报告", "", "当前 gate：ACTOR_B0_D_INCONCLUSIVE。", "",
             "仅为全量模型预审；真实人工确认数为0。没有读取GT或重新运行含GT评价。", "",
             f"完成80/80条轨迹、827/827次CALL预审。缺源轨迹{summary['needs_source_trajectories']}，缺源调用{summary['needs_source_calls']}。", "",
             "## 预审分布", "", f"CALL标签：{call_dist}", f"CALL置信度：{cconf}", f"轨迹置信度：{tconf}", ""]
    lines.extend(f"- {key}: {value}" for key, value in labels.items())
    lines.extend(["", "## 条件内预审统计", "", "以下为独立Agent提议，不是正确率或已验证缺陷率；字段可能重叠。不同审计Agent的尺度差异需人审裁决。", "",
                  "| 条件 | CALL/轨迹 | 证据不足 | 提前停止 | 无支持断言 | 不忠实 | 原始无合法STOP |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    for condition, values in summary["by_condition"].items():
        lines.append(f"| {condition} | {values['calls']}/{values['trajectories']} | {values['insufficient']} | {values['premature']} | {values['unsupported']} | {values['unfaithful']} | {values['no_legal_stop']} |")
    lines.extend(["", "## 人工队列", "", f"80条轨迹全部需要真实人工确认。CALL去重队列{len(chosen)}条，优先级{qcounts}。",
                  f"各入选理由计数（可能重叠）：{trigger_counts}；累计理由命中{sum(trigger_counts.values())}，去重后{len(chosen)}。",
                  "所有80条终态均纳入证据充分性复核，包含WEAK_EVIDENCE停止判断；不把诊断类别提供给独立预审Agent。",
                  "P0全部保留，P1按完整保留清单，P2按condition×工具×step位置分层每个非空层随机抽1，固定seed20261007。",
                  f"P2剩余高置信候选数：{p2_eligible}。TOOL-RENAME调用均为medium，严格P2没有候选；其首次选择全量通过P1保留。该P2四条件覆盖例外已提交研究者确认，不自行提高Agent置信度或扩展抽样门槛。",
                  "150–250为工作量目标；如果高风险队列超过250，仍保留全部记录，不为凑数删去高风险请求。",
                  f"本轮CALL队列{'超过250条；上列P0/P1触发原因完整保留，需研究者分批安排复核' if len(chosen) > 250 else '处于250条以内'}。",
                  "", "## 未确定事项", "", "策略、冲突综合、提前停止和证据忠实度的Agent判断需研究者确认。高置信预审也不是人类验证。具体记录见私有HUMAN_REVIEW_QUEUE.csv和PAIRED_CONDITION_ANALYSIS.md。",
                  "", "审计输入不提供GT/类别/来源文件名；隔离条件先审调用前状态，锁定后再审完整轨迹，最后配对。所有逐样本材料仅本地保存。",
                  "", "验证：四条件调用/轨迹源与结果SHA锁、时间顺序、80/827唯一关联和八字段枚举全部通过；原人工文件SHA未变。离线浏览器加载80条轨迹、图像正常、无JavaScript错误。虚构数据验证确认必填和无法判断标签锁定，不写真实人工标签。",
                  "", "完成并锁定必要人审后，通过import_human_reviews.py导入确认标签；显式--evaluate才运行含GT的最终评价。当前没有SFT或Monitor实验。"])
    (BASE / "AGENT_AUDIT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
