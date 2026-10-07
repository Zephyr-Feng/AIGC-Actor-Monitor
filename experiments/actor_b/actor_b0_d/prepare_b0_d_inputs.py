#!/usr/bin/env python3
"""Build a disjoint, outcome-stratified Actor-B0-D manifest from frozen B0-C inputs.

The source cohort is reused as an intentionally diagnostic set. Ground truth and
category metadata are written only to local evaluation files; actor_input_manifest
contains only opaque sample ID, relative image path, and image SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "experiments/actor_b/heldout_confirmation"
ACTOR0 = ROOT / "experiments/actor0/analysis/system_predictions.csv"
OUTPUT = Path(__file__).resolve().parent / "data"

CATEGORY_ORDER = (
    "EASY_AGREEMENT",
    "PROBE_FAILURE_COMPLEMENTARY",
    "TOOL_DISAGREEMENT",
    "WEAK_EVIDENCE",
    "DIFFICULT_SOLVABLE",
)
QUOTAS = {
    "EASY_AGREEMENT": {"real": 6, "fake": 6},
    "PROBE_FAILURE_COMPLEMENTARY": {"real": 3, "fake": 9},
    "TOOL_DISAGREEMENT": {"real": 4, "fake": 12},
    "WEAK_EVIDENCE": {"real": 2, "fake": 8},
    "DIFFICULT_SOLVABLE": {"real": 5, "fake": 5},
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Dinic:
    def __init__(self, count: int) -> None:
        self.graph: list[list[list[int]]] = [[] for _ in range(count)]

    def add_edge(self, start: int, end: int, capacity: int) -> list[int]:
        forward = [end, capacity, len(self.graph[end]), capacity]
        backward = [start, 0, len(self.graph[start]), 0]
        self.graph[start].append(forward)
        self.graph[end].append(backward)
        return forward

    def max_flow(self, source: int, sink: int) -> int:
        total = 0
        while True:
            level = [-1] * len(self.graph)
            level[source] = 0
            queue = [source]
            for node in queue:
                for target, capacity, _, _ in self.graph[node]:
                    if capacity and level[target] < 0:
                        level[target] = level[node] + 1
                        queue.append(target)
            if level[sink] < 0:
                return total
            cursor = [0] * len(self.graph)

            def send(node: int, amount: int) -> int:
                if node == sink:
                    return amount
                while cursor[node] < len(self.graph[node]):
                    edge = self.graph[node][cursor[node]]
                    target, capacity, reverse, _ = edge
                    if capacity and level[target] == level[node] + 1:
                        pushed = send(target, min(amount, capacity))
                        if pushed:
                            edge[1] -= pushed
                            self.graph[target][reverse][1] += pushed
                            return pushed
                    cursor[node] += 1
                return 0

            while pushed := send(source, 1_000_000):
                total += pushed


def canonical_direction(tool_row: dict) -> str | None:
    tool = tool_row["tool"]
    signal = tool_row.get("signal")
    if tool == "complementary_forensic_analyzer":
        return signal if signal in ("real", "fake") else None
    if tool == "local_texture_analyzer":
        return {"real_like": "real", "synthetic_like": "fake"}.get(signal)
    return None


def eligible_sets(manifest: list[dict], tool_rows: list[dict], trajectories: list[dict],
                  old_image_only_errors: set[str]) -> tuple[dict[str, set[str]], dict[str, dict]]:
    labels = {row["sample_id"]: row["label"] for row in manifest}
    tools_by_id = {row["sample_id"]: {tool["tool"]: tool for tool in row["tools"]}
                   for row in tool_rows}
    traj_by_id = {row["sample_id"]: row for row in trajectories}
    if set(tools_by_id) != set(labels) or set(traj_by_id) != set(labels):
        raise ValueError("B0-C manifest, tool results, and trajectories are not aligned")

    evidence: dict[str, dict] = {}
    for sample_id in labels:
        rows = tools_by_id[sample_id]
        complementary = rows["complementary_forensic_analyzer"]
        local = rows["local_texture_analyzer"]
        global_obs = rows["global_forensic_analyzer"]["observations"]
        evidence[sample_id] = {
            "complementary_direction": canonical_direction(complementary),
            "local_direction": canonical_direction(local),
            "complementary_strength": complementary.get("strength"),
            "local_strength": local.get("strength"),
            "probe_max_deviation_percentile": global_obs.get("max_deviation_percentile"),
        }

    real_ids = [sample_id for sample_id, label in labels.items() if label == "real"]
    high_probe_real = set(sorted(
        real_ids,
        key=lambda sample_id: (
            -float(evidence[sample_id]["probe_max_deviation_percentile"]),
            stable_key(sample_id),
        ),
    )[:4])

    candidates = {category: set() for category in CATEGORY_ORDER}
    for sample_id, item in evidence.items():
        left = item["complementary_direction"]
        right = item["local_direction"]
        if left not in ("real", "fake") or right not in ("real", "fake"):
            raise ValueError("a frozen direction tool lacks a supported signal")
        same = left == right
        conflict = not same
        strengths = (item["complementary_strength"], item["local_strength"])

        if same and all(value in ("high", "moderate") for value in strengths):
            candidates["EASY_AGREEMENT"].add(sample_id)
        if sample_id in high_probe_real or (
            labels[sample_id] == "fake" and conflict
            and float(item["probe_max_deviation_percentile"]) >= 95
        ):
            candidates["PROBE_FAILURE_COMPLEMENTARY"].add(sample_id)
        if conflict:
            candidates["TOOL_DISAGREEMENT"].add(sample_id)
        if "low" in strengths or all(value != "high" for value in strengths):
            candidates["WEAK_EVIDENCE"].add(sample_id)

        direction_supports_gt = left == labels[sample_id] or right == labels[sample_id]
        if direction_supports_gt and (
            not traj_by_id[sample_id].get("final_correct", False)
            or sample_id in old_image_only_errors
        ):
            candidates["DIFFICULT_SOLVABLE"].add(sample_id)

    return candidates, evidence


def assign_categories(manifest: list[dict], candidates: dict[str, set[str]]) -> dict[str, str]:
    labels = {row["sample_id"]: row["label"] for row in manifest}
    assignment: dict[str, str] = {}
    for label in ("real", "fake"):
        samples = sorted((sample_id for sample_id, value in labels.items() if value == label),
                         key=stable_key)
        categories = list(CATEGORY_ORDER)
        source = 0
        sample_start = 1
        category_start = sample_start + len(samples)
        sink = category_start + len(categories)
        flow = Dinic(sink + 1)
        sample_nodes = {sample_id: sample_start + index for index, sample_id in enumerate(samples)}
        category_nodes = {category: category_start + index for index, category in enumerate(categories)}
        edges: dict[tuple[str, str], list[int]] = {}
        for sample_id in samples:
            flow.add_edge(source, sample_nodes[sample_id], 1)
            eligible = sorted(
                (category for category in categories if sample_id in candidates[category]),
                key=lambda category: stable_key(category + sample_id),
            )
            for category in eligible:
                edges[(sample_id, category)] = flow.add_edge(
                    sample_nodes[sample_id], category_nodes[category], 1
                )
        for category in categories:
            flow.add_edge(category_nodes[category], sink, QUOTAS[category][label])
        expected = sum(QUOTAS[category][label] for category in categories)
        actual = flow.max_flow(source, sink)
        if actual != expected:
            raise ValueError(f"non-overlapping {label} quota infeasible: {actual}/{expected}")
        for (sample_id, category), edge in edges.items():
            if edge[3] == 1 and edge[1] == 0:
                if sample_id in assignment:
                    raise AssertionError("sample assigned to multiple categories")
                assignment[sample_id] = category
    if set(assignment) != set(labels):
        raise ValueError("category assignment did not cover all 60 samples")
    return assignment


def reason_for(sample_id: str, category: str, label: str, item: dict,
               evidence: dict, b0c_correct: bool, image_only_wrong: bool) -> str:
    left = evidence["complementary_direction"]
    right = evidence["local_direction"]
    left_strength = evidence["complementary_strength"]
    right_strength = evidence["local_strength"]
    deviation = float(evidence["probe_max_deviation_percentile"])
    if category == "EASY_AGREEMENT":
        return (f"冻结方向工具同向（{left}），两侧强度均为 high/moderate；" 
                "用于检查充分证据下能否及时停止。")
    if category == "PROBE_FAILURE_COMPLEMENTARY":
        if label == "real":
            return (f"real 样本中 Evidence-only PROBE 最大偏离排名前 4（percentile={deviation:g}）；"
                    "作为非方向性高偏离近似挑战，非历史 PROBE 分类错误。")
        return (f"Evidence-only PROBE 最大偏离 percentile={deviation:g}，且两类方向工具相反；"
                "用于检查非方向观察与互补证据的整合，非历史 PROBE 分类错误。")
    if category == "TOOL_DISAGREEMENT":
        return f"冻结互补取证与局部纹理方向相反（{left_strength}/{right_strength}）；冲突由工具输出定义。"
    if category == "WEAK_EVIDENCE":
        return (f"方向工具强度为 {left_strength}/{right_strength}；至少一侧为 low，"
                "或两侧均未达 high，用于证据不足/质量不稳定诊断。")
    reason = "B0-C 原始终态不正确或无效" if not b0c_correct else "Actor-0 image-only 历史判断错误"
    if not image_only_wrong and not b0c_correct:
        reason = "B0-C 原始终态不正确或无效"
    return f"{reason}，且现有方向工具至少一侧与 GT 同向，作为困难但有可用证据链的样本。"


def write_selection_report(path: Path, manifest: list[dict], assigned: dict[str, str],
                           evidence: dict[str, dict], historical_probe_errors: set[str],
                           tools_summary: dict) -> None:
    groups = {row["source_group"] for row in manifest}
    rows_by_id = {row["sample_id"]: row for row in manifest}
    lines = [
        "# Actor-B0-D 诊断样本选择报告",
        "",
        "## 数据来源与边界",
        "",
        "本清单复用 Actor-B0-C 已冻结的 60 张 eval 图及其 20 个来源组，每组 3 张；不新增图片、不抽取预留给 Monitor 的来源组。",
        "这是一份新建的诊断 manifest，但样本不是独立于 B0-C 的新 held-out 集。所有结果仅用于本轮配对策略诊断，不作总体准确率或独立泛化估计。",
        f"历史 PROBE 分类错误共 {len(historical_probe_errors)} 张；与当前 60 张交集为 {len(historical_probe_errors & set(rows_by_id))} 张。按用户确认，PROBE 类由 Evidence-only 困难近似样本组成，不宣称包含旧分类错误例。",
        f"未触碰 B0-C 已标记为 Monitor test 预留的 74 个来源组。当前 cohort 的四条件重复测量按 sample 配对，并按 {len(groups)} 个 source_group 作为区组解释；图像不视为独立同分布抽样。",
        "",
        "## 预注册分层规则",
        "",
        "类别互斥且合计 60。方向标签只从冻结的局部纹理与互补取证 signal 映射得到；global PROBE 的 Evidence-only 偏离不产生方向。GT 仅用于离线类别/最终指标，不写入 actor_input_manifest，也不进入 Actor 对话。",
        "",
        "- **EASY_AGREEMENT（12）**：局部纹理与互补取证方向相同，且两者 strength 均为 high 或 moderate。",
        "- **PROBE_FAILURE_COMPLEMENTARY（12）**：real 子类从 real 图中按 frozen Evidence-only `max_deviation_percentile` 排名前 4 形成 false-alarm-like 近似挑战，实际分配 3 张；fake 子类从 PROBE 偏离 percentile ≥95 且两个方向工具冲突者中分配 9 张。没有可用的历史 PROBE classifier 错误图。",
        "- **TOOL_DISAGREEMENT（16）**：局部纹理与互补取证给出相反方向；标签不依赖 Actor verdict。",
        "- **WEAK_EVIDENCE（10）**：两个方向工具至少一方 strength 为 low，或两方均未达 high；代表证据不足或强度不稳定。",
        "- **DIFFICULT_SOLVABLE（10）**：B0-C raw verdict 错误/无效，或历史 image-only baseline 错误；同时至少一个方向工具与 GT 同向，作为有可用互补线索的困难样本。",
        "",
        "同一行可能满足多项候选规则；用确定性最大流在候选集合中互斥分配，以满足固定总数及 easy/difficult 的 1:1 标签建议。类别间的实际标签数见表。算法以 SHA-256 对样本键排序，且保留源 manifest 的原始运行顺序。",
        "",
        "## 分层结果",
        "",
        "| 类别 | n | real | fake | source groups |",
        "|---|---:|---:|---:|---:|",
    ]
    for category in CATEGORY_ORDER:
        selected = [row for row in manifest if assigned[row["sample_id"]] == category]
        lines.append(
            f"| {category} | {len(selected)} | "
            f"{sum(row['label'] == 'real' for row in selected)} | "
            f"{sum(row['label'] == 'fake' for row in selected)} | "
            f"{len({row['source_group'] for row in selected})} |"
        )
    lines.extend([
        "| **合计** | **60** | **20** | **40** | **20** |",
        "",
        "## 可复现输入",
        "",
        f"- B0-C source manifest SHA-256: `{tools_summary['manifest_sha256']}`",
        f"- B0-C frozen tool-results SHA-256: `{tools_summary['tool_results_sha256']}`",
        f"- B0-C raw trajectories SHA-256: `{tools_summary['trajectories_sha256']}`",
        "- Actor-facing manifest: `actor_input_manifest.jsonl`，只含 sample_id、relative_path、image SHA-256；不含 GT、source_group、generator 或诊断类别。",
        "- Diagnostic manifest: `diagnostic_manifest.jsonl`，含 GT 与类别，仅供本地离线评测。",
        "- Human audit set: 每个 easy、conflict、PROBE-proxy、weak 类别固定抽 5 张，优先跨 source_group 覆盖；四 condition 共 80 份人工审核记录。",
        "",
        "## 限制",
        "",
        "此诊断样本按既有工具输出和 B0-C/Actor-0 历史困难情况分层，具有结果导向的目的性抽样；balanced accuracy 等只作该挑战集上的背景描述。PROBE 类是近似压力测试，不可写成真实 PROBE 错误复现。来源组内三种 generator 相关，统计解释以配对和组级描述为主。",
        "",
        "## 工作流参考",
        "",
        "本地元数据盘点采用可复现、限制输出的研究 Agent 工作流；该文献不作为图像取证或工具策略假设的科学证据：Kassis et al. (2026), *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*, arXiv:2609.00065, https://arxiv.org/abs/2609.00065.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=SOURCE)
    parser.add_argument("--actor0-predictions", type=Path, default=ACTOR0)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()

    manifest_path = args.source_dir / "input/heldout_manifest.jsonl"
    tools_path = args.source_dir / "input/heldout_tool_results.jsonl"
    trajectories_path = args.source_dir / "outputs/trajectories.jsonl"
    summary_path = args.source_dir / "input/selection_summary.json"
    manifest = read_jsonl(manifest_path)
    tool_rows = read_jsonl(tools_path)
    trajectories = read_jsonl(trajectories_path)
    source_summary = read_json(summary_path)
    if len(manifest) != 60 or len({row["source_group"] for row in manifest}) != 20:
        raise ValueError("expected the frozen B0-C 60-sample / 20-source-group cohort")
    if source_summary.get("remaining_eval_groups_reserved_for_monitor_test") != 74:
        raise ValueError("Monitor-reserved source-group count differs from the approved split")
    if len(tool_rows) != 60 or len(trajectories) != 60:
        raise ValueError("B0-C inputs/trajectories are incomplete")
    if [row["sample_id"] for row in trajectories] != [row["sample_id"] for row in manifest]:
        raise ValueError("B0-C trajectory order differs from manifest order")

    with args.actor0_predictions.open(encoding="utf-8-sig", newline="") as stream:
        old_predictions = list(csv.DictReader(stream))
    image_only_errors = {
        row["sample_id"] for row in old_predictions
        if row["system"] == "B0_image_only" and row["correct"] == "0"
    }
    historical_probe_errors = {
        row["sample_id"] for row in csv.DictReader(
            (ROOT / "experiments/actor0/analysis/probe_failure_analysis.csv").open(
                encoding="utf-8-sig", newline=""
            )
        )
    }

    candidates, evidence = eligible_sets(manifest, tool_rows, trajectories, image_only_errors)
    assignment = assign_categories(manifest, candidates)
    label_by_id = {row["sample_id"]: row["label"] for row in manifest}
    for category, label_counts in QUOTAS.items():
        actual = Counter(label_by_id[sample_id] for sample_id in assignment
                         if assignment[sample_id] == category)
        if actual != Counter(label_counts):
            raise AssertionError(f"label quota mismatch for {category}")

    trajectory_by_id = {row["sample_id"]: row for row in trajectories}
    diagnostic_rows = []
    actor_rows = []
    reason_counts = Counter()
    for source_row in manifest:
        sample_id = source_row["sample_id"]
        category = assignment[sample_id]
        reason = reason_for(
            sample_id, category, source_row["label"], source_row, evidence[sample_id],
            bool(trajectory_by_id[sample_id].get("final_correct")),
            sample_id in image_only_errors,
        )
        reason_counts[category] += 1
        diagnostic_rows.append({
            "sample_id": sample_id,
            "gt": source_row["label"],
            "source_group": source_row["source_group"],
            "generator": source_row["generator"],
            "diagnostic_category": category,
            "selection_reason": reason,
            "image_sha256": source_row["sha256"],
        })
        actor_rows.append({
            "sample_id": sample_id,
            "relative_path": source_row["relative_path"],
            "sha256": source_row["sha256"],
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "diagnostic_manifest.jsonl", diagnostic_rows)
    write_jsonl(args.output_dir / "actor_input_manifest.jsonl", actor_rows)

    def file_sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    write_selection_report(
        args.output_dir / "SELECTION_REPORT.md", manifest, assignment, evidence,
        historical_probe_errors,
        {
            "manifest_sha256": file_sha(manifest_path),
            "tool_results_sha256": file_sha(tools_path),
            "trajectories_sha256": file_sha(trajectories_path),
        },
    )

    # Fix a 5-per-category, group-spread audit subset before any B0-D condition runs.
    audit_categories = (
        "EASY_AGREEMENT", "TOOL_DISAGREEMENT",
        "PROBE_FAILURE_COMPLEMENTARY", "WEAK_EVIDENCE",
    )
    audit = []
    for category in audit_categories:
        candidates_for_audit = [row for row in diagnostic_rows
                                if row["diagnostic_category"] == category]
        candidates_for_audit.sort(key=lambda row: stable_key(category + row["sample_id"]))
        used_groups: set[str] = set()
        chosen = []
        for row in candidates_for_audit:
            if row["source_group"] not in used_groups:
                chosen.append(row)
                used_groups.add(row["source_group"])
            if len(chosen) == 5:
                break
        if len(chosen) != 5:
            raise ValueError(f"cannot form five group-distinct audit samples for {category}")
        audit.extend({"sample_id": row["sample_id"], "diagnostic_category": category}
                     for row in chosen)
    write_jsonl(args.output_dir / "manual_audit_samples.jsonl", audit)
    print(json.dumps({
        "samples": len(diagnostic_rows),
        "source_groups": len({row["source_group"] for row in manifest}),
        "category_counts": dict(reason_counts),
        "historical_probe_errors_in_cohort": len(historical_probe_errors & set(label_by_id)),
        "actor_input_has_gt": any("gt" in row or "label" in row for row in actor_rows),
        "manual_audit_samples": len(audit),
        "diagnostic_manifest_sha256": file_sha(args.output_dir / "diagnostic_manifest.jsonl"),
        "actor_input_manifest_sha256": file_sha(args.output_dir / "actor_input_manifest.jsonl"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
