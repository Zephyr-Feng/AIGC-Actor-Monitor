"""Render observed forensic measurements for the Chinese Actor prompt."""

from __future__ import annotations

from agent.tools import FAMILIES, FEATURE_UNITS


FEATURE_LABELS = {
    "high_freq_energy_ratio": "高频能量占比",
    "mid_freq_energy_ratio": "中频能量占比",
    "low_freq_energy_ratio": "低频能量占比",
    "spectral_falloff_slope": "频谱衰减斜率",
    "angular_variance": "频谱方向方差",
    "spectral_consistency_score": "频谱一致性得分",
    "lbp_histogram_chi2": "LBP 直方图距离",
    "lbp_chi2_natural_ref": "相对自然图的 LBP 距离",
    "local_anomaly_score": "局部纹理异常度",
    "edge_artifact_score": "边缘伪影度",
    "dct_coeff_kurtosis": "DCT 系数峰度",
    "dct_high_freq_zeros_ratio": "DCT 高频置零率",
    "noise_residual_mean": "噪声残差均值",
    "noise_residual_std": "噪声残差标准差",
    "noise_residual_skew": "噪声残差偏度",
    "color_abnormality_score": "颜色异常度",
}

FORMAL_FAMILIES = ("texture_lbp", "compression_dct", "noise_residual")

FORMAL_NOTICE = (
    "以下是这张图实际取得的三类取证工具读数。真图参考区间来自另取的 100 张真图，"
    "仅描述该样本的 5%～95% 范围：落在区间内不能证明是真图，落在区间外也不能证明是 AI 生成。"
    "只有读数确实超出区间时才能称其相对区间偏高或偏低；不要引用未列出的读数。"
)


def format_tool_results(
    results: list[dict], refs: dict | None = None,
    *, families: tuple[str, ...] | None = None, notice: str | None = None,
) -> str:
    """Show raw observed values and optional real-image ranges, never old classifier scores."""
    lines = [
        notice or (
            "以下是这张图实际取得的取证工具读数。参考区间仅描述真图样本的分布，"
            "不能单独决定真假；不要引用未列出的读数。"
        )
    ]
    for result in results:
        tool = result["tool"]
        if families is not None and tool not in families:
            continue
        lines.append(f"【{FAMILIES[tool]['label']}】")
        if not result["ok"]:
            lines.append(f"未取得读数：{result['error']}")
            continue
        for feature, value in result["values"].items():
            unit = FEATURE_UNITS.get(feature, "")
            line = f"{FEATURE_LABELS[feature]}：{value:.6f} {unit}".rstrip()
            if refs and feature in refs:
                low, high = refs[feature]
                line += f"；真图参考区间：{low:.6f}～{high:.6f}"
            lines.append(line)
    return "\n".join(lines)


def format_formal_tool_results(results: list[dict], refs: dict) -> str:
    """Render the three user-selected families for paired Actor collection."""
    return format_tool_results(
        results, refs, families=FORMAL_FAMILIES, notice=FORMAL_NOTICE
    )
