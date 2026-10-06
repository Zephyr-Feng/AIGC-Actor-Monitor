"""工具注册表 + JSON Schema（M1）。

**这是工具定义的唯一真源。** `monitor/calibration.py` 从 here import，
避免出现"标定用的特征表"和"Actor 实际调用的工具"两套漂移的定义。

族级划分的依据见 calibration.py 头注释：19 个原始特征里有 2 对字面重复
（r=1.00000），归成 5 个语义可区分的族。不给 Actor 暴露近重复特征 ——
那样它的"引用"没有意义，S3 数"几条证据指向反方向"也会失真。

另有 1 个死特征被剔除：dct_block_consistency 在 E1 的 4 条件 × 2 组里
**恒等于 1.0**（实现饱和）。标定时已被零方差保护自动丢弃，所以剔除它
不改变任何 CV AUC；但留着会让 Actor 看到"1.0（参考 1.0 ~ 1.0）"这种
零信息读数，还可能诱发虚假引用。故一并从族定义里去掉。剩 16 维。

工具返回值设计见 evidence/schemas.py::ToolResult 的 docstring：
给原始值 + 自然图参考区间，**不给校准分数**。给分数等于把工具变成黑箱
分类器，Actor 的"加权"就没有讨论余地了。
"""
from __future__ import annotations

import re

FAMILIES: dict[str, dict] = {
    "freq_spectrum": {
        "label": "频域轮廓",
        "desc": "分析图像的频域能量分布。返回高/中/低频能量占比、频谱衰减斜率、"
                "角度方向方差、频谱一致性得分。生成模型常在上采样环节留下"
                "频谱衰减异常或方向性伪影。",
        "features": [
            "high_freq_energy_ratio",
            "mid_freq_energy_ratio",
            "low_freq_energy_ratio",
            "spectral_falloff_slope",
            "angular_variance",
            "spectral_consistency_score",
        ],
    },
    "texture_lbp": {
        "label": "纹理/LBP",
        "desc": "分析图像局部纹理统计。返回 LBP 直方图卡方距离、局部异常得分、"
                "边缘伪影得分。生成模型的纹理合成会偏离自然图像的局部二值模式分布。",
        "features": [
            "lbp_histogram_chi2",
            "lbp_chi2_natural_ref",
            "local_anomaly_score",
            "edge_artifact_score",
        ],
    },
    "compression_dct": {
        "label": "压缩史/DCT",
        "desc": "分析图像的压缩与分块痕迹。返回 DCT 系数峰度、"
                "高频置零率。用于判断图像经历过什么编码、以及是否存在"
                "不自然的块效应。",
        "features": [
            "dct_coeff_kurtosis",
            "dct_high_freq_zeros_ratio",
        ],
    },
    "noise_residual": {
        "label": "噪声残差",
        "desc": "分析图像的噪声残差分布（SRM 滤波）。返回残差均值、标准差、偏度。"
                "真实相机传感器噪声有其特征分布，生成图像常表现为过于干净"
                "或分布形状异常。",
        "features": [
            "noise_residual_mean",
            "noise_residual_std",
            "noise_residual_skew",
        ],
    },
    "color_stats": {
        "label": "颜色统计",
        "desc": "分析颜色通道之间的相关性。返回颜色异常得分。"
                "生成模型在颜色通道关系上可能偏离自然图像。",
        "features": [
            "color_abnormality_score",
        ],
    },
}

# 区域参数：两个有实际区别的取法。
#   center = 中心裁剪到 size×size（不重采样，保留原始像素统计）
#   full   = 整图缩放到 size×size（LANCZOS）
# 给 Actor 这个选择是有意义的：中心裁剪避开边缘，整图看全局布局。
REGIONS = ["center", "full"]

# 特征名 → 单位/量纲说明。工具输出里带上，让 Actor 知道数值怎么读。
FEATURE_UNITS: dict[str, str] = {
    "high_freq_energy_ratio": "[0,1] 能量占比",
    "mid_freq_energy_ratio": "[0,1] 能量占比",
    "low_freq_energy_ratio": "[0,1] 能量占比",
    "spectral_falloff_slope": "对数频谱斜率",
    "angular_variance": "角度方向方差",
    "spectral_consistency_score": "[0,1] 一致性",
    "lbp_histogram_chi2": "卡方距离",
    "lbp_chi2_natural_ref": "卡方距离（对自然图参考）",
    "local_anomaly_score": "[0,1] 异常度",
    "edge_artifact_score": "[0,1] 伪影度",
    "dct_coeff_kurtosis": "峰度",
    "dct_high_freq_zeros_ratio": "[0,1] 置零率",
    "noise_residual_mean": "残差均值",
    "noise_residual_std": "残差标准差",
    "noise_residual_skew": "残差偏度",
    "color_abnormality_score": "[0,1] 异常度",
}


_TOOL_CALL_BLOCK = re.compile(r"<tool_call>.*?</tool_call>", re.S)


def strip_tool_calls(text: str) -> str:
    """
    去掉 tool_call 标记块，只留模型自己写的散文。

    引用统计前**必须**先过这一道：`<tool_call>{"name": "freq_spectrum", ...}`
    里带着英文工具名和特征名，不剥的话每次工具调用都会自我认证成
    "引用了工具证据"，环1 的引用比例直接失真到 100%。
    """
    return _TOOL_CALL_BLOCK.sub("", text or "")


def tool_tokens() -> list[str]:
    """族 key + 中文标签 + 特征名。字面匹配用，调用方自己决定要不要过 strip。"""
    out: list[str] = []
    for k, spec in FAMILIES.items():
        out.extend([k, spec["label"], *spec["features"]])
    return out


# 引用识别用的词表（环1 引用比例统计）。
#
# 为什么不能直接用 tool_tokens()：族 key 和特征名是**英文标识符**，
# 模型在中文散文里根本不会写 "freq_spectrum"，只会写"频域"。所以这里
# 列的是它**实际会用的说法**。
#
# 刻意**不含** "纹理/边缘/噪声/压缩/颜色" —— 这些词既能指工具维度，
# 也能指内容语义（"这张图纹理很自然"），留着会让工具侧虚高。
# eval/m3_stats.py 的 SEMANTIC_TOKENS 同样回避了这些词，两边不重叠。
CITATION_TOKENS: list[str] = [
    "freq_spectrum", "texture_lbp", "compression_dct", "noise_residual",
    "color_stats",
    "频域", "频谱", "LBP", "lbp", "DCT", "dct", "噪声残差", "SRM",
    "光谱衰减", "能量占比", "卡方", "峰度", "置零率", "块间一致性",
    "高频能量", "中频能量", "低频能量", "角度方差", "频谱一致性",
]


def family_of(name: str) -> dict:
    if name not in FAMILIES:
        raise KeyError(f"未知工具 {name!r}，可用：{sorted(FAMILIES)}")
    return FAMILIES[name]


def all_features() -> list[str]:
    """按族顺序摊平的全部特征名（calibration.py 要用）。"""
    out: list[str] = []
    for spec in FAMILIES.values():
        out.extend(spec["features"])
    return out


def build_tool_schemas(families: list[str] | None = None) -> list[dict]:
    """
    生成喂给 chat template 的 tools 参数（OpenAI function-calling 格式）。

    families=None 时给全部 5 个。消融实验里可以只给子集。
    """
    keys = families if families is not None else list(FAMILIES)
    schemas = []
    for k in keys:
        spec = family_of(k)
        schemas.append({
            "type": "function",
            "function": {
                "name": k,
                "description": spec["desc"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "enum": REGIONS,
                            "description": "分析区域。center=中心裁剪（保留原始像素统计，"
                                           "适合看局部纹理）；full=整图缩放（看全局布局）。",
                        },
                    },
                    "required": ["region"],
                },
            },
        })
    return schemas


def describe_tools(families: list[str] | None = None) -> str:
    """纯文本版工具说明，给无视觉反事实轨迹用（不依赖 tools= 参数）。"""
    keys = families if families is not None else list(FAMILIES)
    lines = []
    for k in keys:
        spec = family_of(k)
        lines.append(f"- {k}（{spec['label']}）：{spec['desc']}\n"
                     f"  参数 region ∈ {{{', '.join(REGIONS)}}}")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    print(f"{len(FAMILIES)} 个工具，"
          f"{sum(len(s['features']) for s in FAMILIES.values())} 个特征\n")
    for k, s in FAMILIES.items():
        print(f"{k:<18s} {s['label']:<10s} {len(s['features'])} 维")
    print()
    print(json.dumps(build_tool_schemas(), ensure_ascii=False, indent=2)[:600])
