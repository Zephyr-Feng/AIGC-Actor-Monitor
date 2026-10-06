#!/usr/bin/env python3
"""Analyze frozen expert predictions on the six existing PROBE errors.

This script reads prediction artifacts only. It does not load models or infer.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROBE_ROOT = ROOT / "experiments/probe_dinov2"
TOOLBOX_ROOT = ROOT / "experiments/toolbox_screening"
OUT = TOOLBOX_ROOT / "analysis"
AUX_TOOLS = ("PatchCraft", "SAFE", "FSD", "AIDE")


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def keyed(rows: list[dict], path: Path) -> dict[str, dict]:
    result = {str(row["sample_id"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate sample_id in {path}")
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def same_number(first: str | float, second: str | float) -> bool:
    return math.isclose(float(first), float(second), rel_tol=1e-10, abs_tol=1e-12)


def label_of(prediction: int) -> str:
    return "fake" if int(prediction) else "real"


def main() -> None:
    manifest_path = PROBE_ROOT / "dataset_manifest.jsonl"
    manifest = jsonl(manifest_path)
    ids = [str(row["sample_id"]) for row in manifest]
    if len(ids) != 300 or len(set(ids)) != 300:
        raise ValueError(f"expected 300 unique frozen manifest IDs, found {len(ids)}")

    common = keyed(csv_rows(PROBE_ROOT / "results/analysis/aligned_predictions.csv"),
                   PROBE_ROOT / "results/analysis/aligned_predictions.csv")
    toolbox = keyed(csv_rows(TOOLBOX_ROOT / "analysis/aligned_predictions.csv"),
                    TOOLBOX_ROOT / "analysis/aligned_predictions.csv")
    if set(common) != set(ids) or set(toolbox) != set(ids):
        raise ValueError("PROBE/legacy-expert/PatchCraft aligned IDs do not exactly match frozen manifest")

    safe_threshold = float(json.loads(
        (PROBE_ROOT / "prior_calibrations/safe_threshold.json").read_text(encoding="utf-8")
    )["threshold"])
    calibration = json.loads(
        (PROBE_ROOT / "prior_calibrations/fsd_aide_calibration_report.json").read_text(encoding="utf-8")
    )

    rows: list[dict] = []
    for source in manifest:
        sid = str(source["sample_id"])
        old, added = common[sid], toolbox[sid]
        group, generator, truth = str(source["source_group"]), str(source["generator"]), str(source["label"])
        if truth not in {"real", "fake"}:
            raise ValueError(f"unexpected label for {sid}: {truth}")
        if (str(old["source_group"]) != group or str(old["generator"]) != generator
                or str(old["label"]) != truth):
            raise ValueError(f"common expert identity/label mismatch for {sid}")
        if (str(added["source_group_id"]) != group or str(added["generator"]) != generator
                or int(added["label"]) != int(truth == "fake")):
            raise ValueError(f"toolbox identity/label mismatch for {sid}")
        if str(added["path"]).replace("\\", "/") != str(source["relative_path"]):
            raise ValueError(f"image path mismatch for {sid}: {added['path']} vs {source['relative_path']}")

        # The toolbox table supplies frozen PROBE/PatchCraft/SAFE; the prior
        # common analysis supplies the frozen calibrated FSD/AIDE predictions.
        for key in ("probe_score", "probe_pred", "safe_score", "safe_pred"):
            if key in old and key in added:
                if key.endswith("_score") and not same_number(old[key], added[key]):
                    raise ValueError(f"frozen {key} mismatch between analyses for {sid}")
                if key.endswith("_pred") and int(old[key]) != int(added[key]):
                    raise ValueError(f"frozen {key} mismatch between analyses for {sid}")

        truth_id = int(truth == "fake")
        predictions = {
            "PROBE": int(added["probe_pred"]),
            "PatchCraft": int(added["patchcraft_pred"]),
            "SAFE": int(added["safe_pred"]),
            "FSD": int(old["fsd_pred"]),
            "AIDE": int(old["aide_pred"]),
        }
        scores = {
            "PROBE": float(added["probe_score"]),
            "PatchCraft": float(added["patchcraft_score"]),
            "SAFE": float(added["safe_score"]),
            "FSD": float(old["fsd_score"]),
            "AIDE": float(old["aide_score"]),
        }
        fixed_rules = {
            "PROBE": scores["PROBE"] > 0.5,
            "PatchCraft": scores["PatchCraft"] > 0.5,
            "SAFE": scores["SAFE"] >= safe_threshold,
            "FSD": scores["FSD"] >= 0.5,
            "AIDE": scores["AIDE"] >= 0.5,
        }
        for name in predictions:
            if predictions[name] != int(fixed_rules[name]):
                raise ValueError(f"{name} stored decision disagrees with frozen rule for {sid}")

        probe_correct = int(predictions["PROBE"] == truth_id)
        margin = abs(scores["PROBE"] - 0.5)
        if margin < 0.10:
            band = "near-threshold error"
        elif margin < 0.30:
            band = "moderate-confidence error"
        else:
            band = "high-confidence error"
        aux_correct = {name: int(predictions[name] == truth_id) for name in AUX_TOOLS}
        correcting = [name for name in AUX_TOOLS if aux_correct[name]]
        rigid_correct = int(added["rigid_correct"])
        rows.append({
            "image_id": sid,
            "path": str(source["relative_path"]),
            "source_group_id": group,
            "generator": generator,
            "ground_truth": truth,
            "probe_score": scores["PROBE"],
            "probe_prediction": label_of(predictions["PROBE"]),
            "probe_correct": probe_correct,
            "patchcraft_score": scores["PatchCraft"],
            "patchcraft_prediction": label_of(predictions["PatchCraft"]),
            "patchcraft_correct": aux_correct["PatchCraft"],
            "safe_score": scores["SAFE"],
            "safe_prediction": label_of(predictions["SAFE"]),
            "safe_correct": aux_correct["SAFE"],
            "fsd_score": scores["FSD"],
            "fsd_prediction": label_of(predictions["FSD"]),
            "fsd_correct": aux_correct["FSD"],
            "aide_score": scores["AIDE"],
            "aide_prediction": label_of(predictions["AIDE"]),
            "aide_correct": aux_correct["AIDE"],
            "correcting_tools": "|".join(correcting) if correcting else "none",
            "num_correcting_tools": len(correcting),
            "probe_margin_from_0_5": margin,
            "probe_confidence_band": band,
            "has_complementary_evidence": bool(correcting),
            "num_independent_correct_tools": len(correcting),
            "unrecoverable_by_current_tools": not bool(correcting),
            # Kept for the broader all-existing-tools answer; the prescribed
            # four-candidate recovery/oracle sets above remain unchanged.
            "rigid_correct_existing_result": rigid_correct,
            "provenance_actionable_existing_result": int(added["provenance_actionable"]),
        })

    failures = [row for row in rows if row["probe_correct"] == 0]
    if len(failures) != 6:
        raise ValueError(f"expected exactly six PROBE errors under frozen score > 0.5; found {len(failures)}")
    probe_correct_total = sum(row["probe_correct"] for row in rows)

    matrix_fields = [
        "image_id", "path", "source_group_id", "generator", "ground_truth",
        "probe_score", "probe_prediction", "probe_correct",
        "patchcraft_score", "patchcraft_prediction", "patchcraft_correct",
        "safe_score", "safe_prediction", "safe_correct",
        "fsd_score", "fsd_prediction", "fsd_correct",
        "aide_score", "aide_prediction", "aide_correct",
        "correcting_tools", "num_correcting_tools", "probe_margin_from_0_5",
        "probe_confidence_band", "has_complementary_evidence",
        "num_independent_correct_tools", "unrecoverable_by_current_tools",
    ]
    failure_matrix = [{key: row[key] for key in matrix_fields} for row in failures]
    write_csv(OUT / "probe_6_failure_matrix.csv", failure_matrix)

    recovery_rows = []
    recovery_sets: dict[str, set[str]] = {}
    unique_sets: dict[str, set[str]] = {}
    for tool in AUX_TOOLS:
        key = tool.lower()
        recovered = {row["image_id"] for row in failures if row[f"{key}_correct"] == 1}
        unique = {
            row["image_id"] for row in failures
            if row[f"{key}_correct"] == 1
            and all(row[f"{other.lower()}_correct"] == 0 for other in AUX_TOOLS if other != tool)
        }
        recovery_sets[tool], unique_sets[tool] = recovered, unique
        if tool == "PatchCraft":
            marginal_ids = recovered
            marginal_condition = "PROBE wrong; PatchCraft correct"
        elif tool == "SAFE":
            marginal_ids = {
                row["image_id"] for row in failures
                if row["patchcraft_correct"] == 0 and row["safe_correct"] == 1
            }
            marginal_condition = "PROBE and PatchCraft wrong; SAFE correct"
        else:
            marginal_ids = {
                row["image_id"] for row in failures
                if row["patchcraft_correct"] == 0 and row["safe_correct"] == 0
                and row[f"{key}_correct"] == 1
            }
            marginal_condition = f"PROBE, PatchCraft, and SAFE wrong; {tool} correct"
        recovery_rows.append({
            "tool": tool,
            "recovered": len(recovered),
            "total_probe_failures": len(failures),
            "recovery_rate": len(recovered) / len(failures),
            "recovered_image_ids": "|".join(sorted(recovered)) or "none",
            "unique_recovery": len(unique),
            "unique_recovery_image_ids": "|".join(sorted(unique)) or "none",
            "marginal_recovery_condition": marginal_condition,
            "marginal_recovery": len(marginal_ids),
            "marginal_recovery_image_ids": "|".join(sorted(marginal_ids)) or "none",
        })
    write_csv(OUT / "probe_failure_recovery.csv", recovery_rows)

    pairwise_rows = []
    pairwise_counts: dict[str, dict] = {}
    for i, first in enumerate(AUX_TOOLS):
        for second in AUX_TOOLS[i + 1:]:
            overlap = {row["image_id"] for row in failures
                       if row[f"{first.lower()}_correct"] and row[f"{second.lower()}_correct"]}
            first_only = {row["image_id"] for row in failures
                          if row[f"{first.lower()}_correct"] and not row[f"{second.lower()}_correct"]}
            second_only = {row["image_id"] for row in failures
                           if row[f"{second.lower()}_correct"] and not row[f"{first.lower()}_correct"]}
            neither = {row["image_id"] for row in failures
                       if not row[f"{first.lower()}_correct"] and not row[f"{second.lower()}_correct"]}
            result = {"overlap": len(overlap), "first_only": len(first_only),
                      "second_only": len(second_only), "neither": len(neither)}
            if sum(result.values()) != len(failures):
                raise ValueError(f"pairwise recovery counts do not partition six failures: {first}, {second}")
            pairwise_counts[f"{first} vs {second}"] = result
            pairwise_rows.append({
                "first_tool": first, "second_tool": second,
                "probe_failure_n": len(failures),
                "overlap": len(overlap), "first_only": len(first_only),
                "second_only": len(second_only), "neither": len(neither),
                "overlap_image_ids": "|".join(sorted(overlap)) or "none",
                "first_only_image_ids": "|".join(sorted(first_only)) or "none",
                "second_only_image_ids": "|".join(sorted(second_only)) or "none",
                "neither_image_ids": "|".join(sorted(neither)) or "none",
            })
    write_csv(OUT / "pairwise_recovery_overlap.csv", pairwise_rows)

    by_id = {row["image_id"]: row for row in rows}
    combos = {
        "PROBE": ("PROBE",),
        "PROBE + PatchCraft": ("PROBE", "PatchCraft"),
        "PROBE + SAFE": ("PROBE", "SAFE"),
        "PROBE + FSD": ("PROBE", "FSD"),
        "PROBE + AIDE": ("PROBE", "AIDE"),
        "PROBE + PatchCraft + SAFE": ("PROBE", "PatchCraft", "SAFE"),
        "PROBE + PatchCraft + FSD": ("PROBE", "PatchCraft", "FSD"),
        "PROBE + PatchCraft + AIDE": ("PROBE", "PatchCraft", "AIDE"),
        "PROBE + PatchCraft + SAFE + FSD + AIDE": ("PROBE", "PatchCraft", "SAFE", "FSD", "AIDE"),
    }
    oracle: dict[str, dict] = {}
    for name, tools in combos.items():
        correct_ids = []
        for row in rows:
            correct = []
            for tool in tools:
                field = "probe_correct" if tool == "PROBE" else f"{tool.lower()}_correct"
                correct.append(int(row[field]))
            if any(correct):
                correct_ids.append(row["image_id"])
        count = len(correct_ids)
        oracle[name] = {
            "experts": list(tools), "correct": count, "total": len(rows),
            "accuracy": count / len(rows),
            "gain_over_PROBE_correct_images": count - probe_correct_total,
            "gain_over_PROBE_percentage_points": (count - probe_correct_total) / len(rows) * 100,
            "additional_rescued_images": count - probe_correct_total,
            "additional_rescued_image_ids": "|".join(sorted(set(correct_ids) - {
                row["image_id"] for row in rows if row["probe_correct"]
            })) or "none",
            "diagnostic_only": True,
        }
    oracle_payload = {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "sample_count": len(rows),
        "probe_correct_baseline": probe_correct_total,
        "oracle_definition": "A sample is oracle-correct when any listed expert is correct; diagnostic upper bound only.",
        "score_thresholds": {
            "PROBE": "score > 0.5 (fixed)",
            "PatchCraft": "score > 0.5 (official fixed)",
            "SAFE": safe_threshold,
            "FSD": "calibrated p_fake >= 0.5 (prior disjoint calibration)",
            "AIDE": "calibrated p_fake >= 0.5 (prior disjoint calibration)",
        },
        "combination_results": oracle,
    }
    (OUT / "probe_failure_oracle.json").write_text(
        json.dumps(oracle_payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )

    failure_ids = {row["image_id"] for row in failures}
    unrecoverable = sorted(row["image_id"] for row in failures if row["unrecoverable_by_current_tools"])
    high_failures = [row for row in failures if row["probe_confidence_band"] == "high-confidence error"]
    high_correctors = {
        tool: sorted(row["image_id"] for row in high_failures if row[f"{tool.lower()}_correct"])
        for tool in AUX_TOOLS
    }
    pc_safe = pairwise_counts["PatchCraft vs SAFE"]
    marginal = {
        "safe_given_probe_patchcraft": next(r["marginal_recovery"] for r in recovery_rows if r["tool"] == "SAFE"),
        "safe_given_probe_patchcraft_image_ids": next(r["marginal_recovery_image_ids"] for r in recovery_rows if r["tool"] == "SAFE"),
        "fsd_given_probe_patchcraft_safe": next(r["marginal_recovery"] for r in recovery_rows if r["tool"] == "FSD"),
        "fsd_given_probe_patchcraft_safe_image_ids": next(r["marginal_recovery_image_ids"] for r in recovery_rows if r["tool"] == "FSD"),
        "aide_given_probe_patchcraft_safe": next(r["marginal_recovery"] for r in recovery_rows if r["tool"] == "AIDE"),
        "aide_given_probe_patchcraft_safe_image_ids": next(r["marginal_recovery_image_ids"] for r in recovery_rows if r["tool"] == "AIDE"),
    }
    rigid_rescued = sorted(row["image_id"] for row in failures if row["rigid_correct_existing_result"])
    provenance_actionable = sorted(row["image_id"] for row in rows if row["provenance_actionable_existing_result"])

    decisions = {
        "PatchCraft": "CONDITIONAL KEEP (evidence-only; not an independent final verdict)",
        "SAFE": ("CONDITIONAL KEEP" if marginal["safe_given_probe_patchcraft"] >= 1
                 else "DROP FROM MAIN TOOLBOX; retain as benchmark"),
        "FSD": ("CONDITIONAL KEEP" if marginal["fsd_given_probe_patchcraft_safe"] >= 1
                else "DROP FROM MAIN TOOLBOX"),
        "AIDE": ("CONDITIONAL KEEP" if marginal["aide_given_probe_patchcraft_safe"] >= 1
                 else "DROP FROM MAIN TOOLBOX"),
    }
    summary = {
        "analysis_scope": "Frozen 300-image PROBE failure complementarity; no model rerun or threshold tuning.",
        "manifest_sha256": oracle_payload["manifest_sha256"],
        "probe_total": len(rows),
        "probe_correct": probe_correct_total,
        "probe_errors": len(failures),
        "error_image_ids": sorted(failure_ids),
        "recovery": {tool.lower(): {"count": len(recovery_sets[tool]), "total": 6,
                                     "rate": len(recovery_sets[tool]) / 6,
                                     "image_ids": sorted(recovery_sets[tool])}
                     for tool in AUX_TOOLS},
        "unique_recovery": {tool.lower(): {"count": len(unique_sets[tool]),
                                            "image_ids": sorted(unique_sets[tool])}
                            for tool in AUX_TOOLS},
        "pairwise_recovery": pairwise_counts,
        "patchcraft_safe": {
            "overlap": pc_safe["overlap"], "patchcraft_only": pc_safe["first_only"],
            "safe_only": pc_safe["second_only"], "neither": pc_safe["neither"],
            "same_recovery_set": recovery_sets["PatchCraft"] == recovery_sets["SAFE"],
        },
        "marginal_recovery": marginal,
        "oracle": {
            "probe": oracle["PROBE"],
            "probe_patchcraft": oracle["PROBE + PatchCraft"],
            "probe_safe": oracle["PROBE + SAFE"],
            "probe_fsd": oracle["PROBE + FSD"],
            "probe_aide": oracle["PROBE + AIDE"],
            "probe_patchcraft_safe": oracle["PROBE + PatchCraft + SAFE"],
            "probe_patchcraft_fsd": oracle["PROBE + PatchCraft + FSD"],
            "probe_patchcraft_aide": oracle["PROBE + PatchCraft + AIDE"],
            "all_tools": oracle["PROBE + PatchCraft + SAFE + FSD + AIDE"],
        },
        "confidence_analysis": {
            "definition": "margin=abs(PROBE score-0.5); near <0.10, moderate [0.10,0.30), high >=0.30 (descriptive fixed bands).",
            "by_band": {
                band: {"count": sum(row["probe_confidence_band"] == band for row in failures),
                       "image_ids": sorted(row["image_id"] for row in failures if row["probe_confidence_band"] == band)}
                for band in ("near-threshold error", "moderate-confidence error", "high-confidence error")
            },
            "high_confidence_corrections": high_correctors,
        },
        "monitor_relevant": {
            "has_complementary_evidence_n": sum(bool(row["has_complementary_evidence"]) for row in failures),
            "unrecoverable_failures": unrecoverable,
            "scope_note": "num_independent_correct_tools counts the four auxiliary tools per protocol; it does not assert statistical independence.",
        },
        "unrecoverable_failures": unrecoverable,
        "other_preexisting_toolbox_results": {
            "RIGID_correct_on_probe_failures": len(rigid_rescued),
            "RIGID_correct_image_ids": rigid_rescued,
            "Provenance_actionable_overall_n": len(provenance_actionable),
            "Provenance_actionable_image_ids": provenance_actionable,
        },
        "decisions": decisions,
    }
    (OUT / "probe_failure_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )

    def ticks(tool: str, row: dict) -> str:
        return "✓" if row[f"{tool.lower()}_correct"] else "✗"

    conf_counts = summary["confidence_analysis"]["by_band"]
    report = [
        "# PROBE 六张误例互补性精查",
        "",
        "日期：2026-10-02  ",
        "状态：已完成；按方案停止。",
        "",
        "## 1. Data",
        "",
        f"复用同一冻结清单的 {len(rows)} 张图、{len({row['source_group_id'] for row in rows})} 个来源组；PROBE 错误 {len(failures)} 张。没有重跑模型、重算图像分数或调整阈值。所有结果按唯一 `sample_id` 对齐，并核对来源组、生成器、标签和图像相对路径。清单 SHA-256：`{oracle_payload['manifest_sha256']}`。",
        "",
        "判定方向均为 fake probability 越高越像 fake：PROBE/PatchCraft `>0.5`；SAFE 使用独立冻结阈值 `>=%.16g`；FSD/AIDE 使用先前独立校准的 p_fake `>=0.5`。" % safe_threshold,
        "",
        "## 2. Six Failure Matrix",
        "",
        "✓ 表示该辅助工具在 PROBE 错误图上判对。",
        "",
        "| # | Image ID | Generator / GT | PROBE score | PatchCraft | SAFE | FSD | AIDE | Correctors |",
        "|---:|---|---|---:|:---:|:---:|:---:|:---:|---|",
    ]
    for i, row in enumerate(failures, 1):
        report.append(
            f"| {i} | `{row['image_id']}` | {row['generator']} / {row['ground_truth']} | "
            f"{row['probe_score']:.6f} | {ticks('PatchCraft', row)} | {ticks('SAFE', row)} | "
            f"{ticks('FSD', row)} | {ticks('AIDE', row)} | {row['correcting_tools']} |"
        )
    report += [
        "",
        "## 3. Recovery",
        "",
        "| Tool | Recovered | Rate | Unique recovery¹ |",
        "|---|---:|---:|---:|",
    ]
    for row in recovery_rows:
        report.append(f"| {row['tool']} | {row['recovered']}/6 | {row['recovery_rate']:.4f} | {row['unique_recovery']} |")
    report += [
        "",
        "¹ Unique recovery means that tool alone is correct among PatchCraft/SAFE/FSD/AIDE for that PROBE error.",
        "",
        "## 4. Pairwise Complementarity",
        "",
        "| Pair | Overlap | First only | Second only | Neither |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in pairwise_rows:
        report.append(f"| {row['first_tool']} vs {row['second_tool']} | {row['overlap']} | {row['first_only']} | {row['second_only']} | {row['neither']} |")
    report += [
        "",
        f"PatchCraft 与 SAFE 的恢复集合{'完全相同' if summary['patchcraft_safe']['same_recovery_set'] else '并不完全相同'}："
        f"重合 {pc_safe['overlap']} 张，PatchCraft 独有 {pc_safe['first_only']} 张，SAFE 独有 {pc_safe['second_only']} 张，两者都未纠正 {pc_safe['neither']} 张。",
        "",
        "## 5. Oracle",
        "",
        "Oracle 表示组合里至少一个工具答对，是事后上界诊断，不是可部署系统性能。",
        "",
        "| Combination | Correct / 300 | Accuracy | Gain vs PROBE | Additional rescued |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, result in oracle.items():
        report.append(
            f"| {name} | {result['correct']}/300 | {result['accuracy']:.4f} | "
            f"{result['gain_over_PROBE_percentage_points']:+.2f} pp | {result['additional_rescued_images']} |"
        )
    report += [
        "",
        "## 6. Confidence Analysis",
        "",
        f"按固定描述性边界，near-threshold (<0.10) {conf_counts['near-threshold error']['count']} 张，"
        f"moderate ([0.10, 0.30)) {conf_counts['moderate-confidence error']['count']} 张，"
        f"high-confidence (>=0.30) {conf_counts['high-confidence error']['count']} 张。",
        "",
        "高置信误例的正确纠正工具：",
    ]
    if high_failures:
        for row in high_failures:
            report.append(f"- `{row['image_id']}` (margin {row['probe_margin_from_0_5']:.4f}): {row['correcting_tools'] or 'none'}")
    else:
        report.append("- 无高置信误例。")
    report += [
        "",
        "## 7. Toolbox Decision",
        "",
        f"- PatchCraft → **{decisions['PatchCraft']}**：六张中纠正 {len(recovery_sets['PatchCraft'])} 张；按原筛查结论仅作局部纹理证据。",
        f"- SAFE → **{decisions['SAFE']}**：在 PROBE+PatchCraft 之外边际恢复 {marginal['safe_given_probe_patchcraft']} 张。",
        f"- FSD → **{decisions['FSD']}**：在 PROBE+PatchCraft+SAFE 之外边际恢复 {marginal['fsd_given_probe_patchcraft_safe']} 张。",
        f"- AIDE → **{decisions['AIDE']}**：在 PROBE+PatchCraft+SAFE 之外边际恢复 {marginal['aide_given_probe_patchcraft_safe']} 张。",
        "",
        "## 8. Answers",
        "",
        f"1. PatchCraft 和 SAFE 是否纠正同样的 4 张？{'是' if summary['patchcraft_safe']['same_recovery_set'] else '否'}；具体交集与独有样本见上表及 pairwise CSV。",
        f"2. SAFE 在 PROBE+PatchCraft 之外额外救回 **{marginal['safe_given_probe_patchcraft']}** 张。",
        f"3. FSD/AIDE 是否额外恢复 PatchCraft+SAFE 都未恢复的样本？FSD **{marginal['fsd_given_probe_patchcraft_safe']}** 张，AIDE **{marginal['aide_given_probe_patchcraft_safe']}** 张。",
        f"4. 当前所有已有工具是否覆盖全部六个错误？**{'是' if not unrecoverable and not rigid_rescued else '否'}**。按协议的四个辅助工具，仍无人纠正：{', '.join(f'`{sid}`' for sid in unrecoverable) if unrecoverable else '无'}。既有 RIGID 在六张上新增纠正 {len(rigid_rescued)} 张；既有 Provenance actionable 覆盖 {len(provenance_actionable)}/300，因而不能补足未覆盖错误。",
        "",
        "统计中的 `num_independent_correct_tools` 按协议计数不同辅助工具的正确输出，不代表其误差在统计意义上独立。样本独立抽样单位为来源组；六张错误只作描述性个案分析。",
        "",
    ]
    (TOOLBOX_ROOT / "PROBE_FAILURE_COMPLEMENTARITY.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({
        "n": len(rows), "probe_errors": [r["image_id"] for r in failures],
        "recovery": summary["recovery"], "patchcraft_safe": summary["patchcraft_safe"],
        "marginal": marginal, "unrecoverable": unrecoverable, "rigid_correct": rigid_rescued,
        "outputs": [str(OUT / name) for name in (
            "probe_6_failure_matrix.csv", "probe_failure_recovery.csv",
            "pairwise_recovery_overlap.csv", "probe_failure_oracle.json", "probe_failure_summary.json")]
            + [str(TOOLBOX_ROOT / "PROBE_FAILURE_COMPLEMENTARITY.md")],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
