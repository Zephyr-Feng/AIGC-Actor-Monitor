"""
evidence/schemas.py

结构化证据数据模型。
每个特征提取模块输出一个 Evidence dataclass，
最终由 Evidence Aggregator (Model B) 综合判断。
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ──────────────────────────────────────────────
# 伪影检测证据
# ──────────────────────────────────────────────

@dataclass
class ArtifactEvidence:
    """
    伪影检测模块输出的全部证据。

    Fields
    ------
    local_anomaly_score : float
        局部纹理异常得分 [0, 1]，越高越可能是 AI 生成
    edge_artifact_score : float
        边缘/边界伪影得分 [0, 1]
    texture_abnormality_score : float
        纹理分布异常得分 [0, 1]
    color_abnormality_score : float
        颜色通道相关性异常得分 [0, 1]

    noise_residual_mean : float
        SRM 噪声残差均值
    noise_residual_std : float
        SRM 噪声残差标准差
    noise_residual_skew : float
        噪声残差偏度（AI 图常在偏度上异常）

    lbp_histogram_chi2 : float
        LBP 直方图与自然图像参考分布的卡方距离
    gradient_consistency : float
        梯度幅值一致性指标

    patch_artifact_map : Optional[np.ndarray]
        逐块的伪影热图 (H', W')，用于可视化
    """
    local_anomaly_score: float = 0.0
    edge_artifact_score: float = 0.0
    texture_abnormality_score: float = 0.0
    color_abnormality_score: float = 0.0

    noise_residual_mean: float = 0.0
    noise_residual_std: float = 0.0
    noise_residual_skew: float = 0.0

    lbp_histogram_chi2: float = 0.0
    gradient_consistency: float = 0.0

    patch_artifact_map: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        """转为 JSON 可序列化的字典（排除大数组）。"""
        d = {k: float(v) if isinstance(v, (np.floating,)) else v
             for k, v in self.__dict__.items()
             if k != "patch_artifact_map"}
        if self.patch_artifact_map is not None:
            d["patch_artifact_map_shape"] = self.patch_artifact_map.shape
        return d


# ──────────────────────────────────────────────
# 频谱分析证据
# ──────────────────────────────────────────────

@dataclass
class FrequencyEvidence:
    """
    频谱分析模块输出的全部证据。

    Fields
    ------
    high_freq_energy_ratio : float
        高频能量占比 [0, 1]
    mid_freq_energy_ratio : float
        中频能量占比
    low_freq_energy_ratio : float
        低频能量占比
    spectral_falloff_slope : float
        频谱衰减斜率（AI 图常衰减异常）
    angular_variance : float
        角度方向频谱方差（各向异性指标）

    dct_coeff_kurtosis : float
        DCT 系数峰度（AI 图峰度常偏低）
    dct_block_consistency : float
        DCT 块间一致性指标
    dct_high_freq_zeros_ratio : float
        DCT 高频置零率（JPEG 压缩伪影指标）

    spectral_consistency_score : float
        全局频谱一致性得分 [0, 1]
    fft_radial_profile : Optional[np.ndarray]
        径向频谱轮廓 (n_rings,)
    fft_angular_profile : Optional[np.ndarray]
        角度频谱轮廓 (n_angles,)
    dct_coeff_histogram : Optional[np.ndarray]
        DCT 系数直方图
    """
    high_freq_energy_ratio: float = 0.0
    mid_freq_energy_ratio: float = 0.0
    low_freq_energy_ratio: float = 0.0
    spectral_falloff_slope: float = 0.0
    angular_variance: float = 0.0

    dct_coeff_kurtosis: float = 0.0
    dct_block_consistency: float = 0.0
    dct_high_freq_zeros_ratio: float = 0.0

    spectral_consistency_score: float = 0.0

    fft_radial_profile: Optional[np.ndarray] = None
    fft_angular_profile: Optional[np.ndarray] = None
    dct_coeff_histogram: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        d = {k: float(v) if isinstance(v, (np.floating,)) else v
             for k, v in self.__dict__.items()
             if k not in ("fft_radial_profile", "fft_angular_profile",
                          "dct_coeff_histogram")}
        for arr_name in ("fft_radial_profile", "fft_angular_profile",
                         "dct_coeff_histogram"):
            arr = getattr(self, arr_name, None)
            if arr is not None:
                d[f"{arr_name}_shape"] = arr.shape
        return d


# ──────────────────────────────────────────────
# 隐空间证据（新）
# ──────────────────────────────────────────────

@dataclass
class SignedDistanceEvidence:
    """
    隐空间有符号距离证据。

    来自 MLLM 中间层 hidden states 的线性探测结果。

    Fields
    ------
    angle : str
        对应的 forensic 分析角度（spatial / physical / semantic / color_lighting）。
    angle_label : str
        角度中文标签。
    layer_idx : int
        使用的最佳层索引。
    layer_accuracy : float
        该层探测准确率。
    signed_distance : float
        到超平面的有符号距离。
        正数 → 接近 real；负数 → 接近 fake。
    evidence_strength : float
        证据强度 = |signed_distance|，越大越可靠。
    fake_probability : float
        预测为 AI 生成的概率 [0, 1]。
    """
    angle: str
    angle_label: str
    layer_idx: int = -1
    layer_accuracy: float = 0.0
    signed_distance: float = 0.0
    evidence_strength: float = 0.0
    fake_probability: float = 0.0

    def to_dict(self) -> dict:
        return {
            "angle": self.angle,
            "angle_label": self.angle_label,
            "layer_idx": self.layer_idx,
            "layer_accuracy": self.layer_accuracy,
            "signed_distance": self.signed_distance,
            "evidence_strength": self.evidence_strength,
            "fake_probability": self.fake_probability,
        }


# ──────────────────────────────────────────────
# 文本分析证据（新）
# ──────────────────────────────────────────────

@dataclass
class ForensicTextAnalysis:
    """
    多角度文本分析输出。

    Fields
    ------
    angle : str
        分析角度名称。
    angle_label : str
        分析角度中文标签。
    raw_text : str
        MLLM 生成的原始文本分析。
    summary : str
        总结句：是否判断为 AI 生成。
    confidence : float
        该角度分析的置信度 [0, 1]。
    """
    angle: str
    angle_label: str
    raw_text: str = ""
    summary: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "angle": self.angle,
            "angle_label": self.angle_label,
            "raw_text": self.raw_text,
            "summary": self.summary,
            "confidence": self.confidence,
        }


# ──────────────────────────────────────────────
# 综合检测报告
# ──────────────────────────────────────────────

@dataclass
class DetectionReport:
    """
    Model B (Evidence Aggregator) 最终输出的解释性诊断检测报告。

    Fields
    ------
    is_ai_generated : bool
        最终判断是否 AI 生成。
    confidence : float
        综合置信度 [0, 1]。
    explanation : str
        可解释性的诊断文本。
    key_evidence : list[str]
        关键证据摘要列表。

    artifact_evidence : Optional[ArtifactEvidence]
    frequency_evidence : Optional[FrequencyEvidence]
    signed_distances : list[SignedDistanceEvidence]
        各角度的隐空间证据。
    forensic_texts : list[ForensicTextAnalysis]
        各角度的文本分析。
    layer_accuracy_curve : Optional[dict[int, float]]
        逐层探测准确率曲线（用于分析）。
    """
    is_ai_generated: bool = False
    confidence: float = 0.0
    explanation: str = ""
    key_evidence: list[str] = field(default_factory=list)

    artifact_evidence: Optional[ArtifactEvidence] = None
    frequency_evidence: Optional[FrequencyEvidence] = None
    signed_distances: list[SignedDistanceEvidence] = field(default_factory=list)
    forensic_texts: list[ForensicTextAnalysis] = field(default_factory=list)
    layer_accuracy_curve: Optional[dict[int, float]] = None

    def to_dict(self) -> dict:
        return {
            "is_ai_generated": self.is_ai_generated,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "key_evidence": self.key_evidence,
            "artifact_evidence": (self.artifact_evidence.to_dict()
                                  if self.artifact_evidence else None),
            "frequency_evidence": (self.frequency_evidence.to_dict()
                                   if self.frequency_evidence else None),
            "signed_distances": [s.to_dict() for s in self.signed_distances],
            "forensic_texts": [t.to_dict() for t in self.forensic_texts],
            "layer_accuracy_curve": self.layer_accuracy_curve,
        }


# ══════════════════════════════════════════════
# Agent 轨迹数据模型（M1）
#
# 与上面那批的区别：上面是"聚合器"架构的证据模型（已封存于 _legacy），
# 这批是 Actor 的 tool-call 轨迹。Monitor 的三类信号全部从轨迹里读。
# ══════════════════════════════════════════════


@dataclass
class ToolResult:
    """
    一次工具调用的结果。

    **values 必须是原始数值，不能只给自然语言摘要** —— S3 "证据-结论落差"
    要靠原始值反查每条证据指向哪个方向，摘要会把这个信息抹掉。

    Fields
    ------
    tool : str
        工具族 key（freq_spectrum / texture_lbp / ...）。
    label : str
        工具族中文标签。
    args : dict
        Actor 传进来的参数，原样记录（用于复现与归因）。
    values : dict[str, float]
        该族全部原始特征值。
    ref : dict[str, (float, float)]
        自然图参考区间 (p05, p95)，**会展示给 Actor**。
        只给参考区间不给校准分数 —— 给分数等于把工具变成黑箱分类器，
        Actor 的"加权"就没有讨论余地了。
    calibrated : dict
        按 M2 标定算出的族分数与方向。**只给 Monitor，不给 Actor**。
    ok / error / elapsed_ms
        执行状态。
    """
    tool: str
    label: str = ""
    args: dict = field(default_factory=dict)
    values: dict = field(default_factory=dict)
    ref: dict = field(default_factory=dict)
    calibrated: dict = field(default_factory=dict)
    ok: bool = True
    error: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "label": self.label,
            "args": self.args,
            "values": self.values,
            "ref": self.ref,
            "calibrated": self.calibrated,
            "ok": self.ok,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


@dataclass
class Turn:
    """
    轨迹中的一轮。

    Actor 一轮里可能并发发多个 tool_call（Qwen3-VL 支持），所以
    tool_calls 与 tool_results 都是列表，按顺序对应。

    probe : S2 隐空间判据，挂在该轮 assistant 的 hidden state 上。
    injected : 该轮之前 Monitor 注入的内容（检测与干预同源，注入也记在轨迹里，
               否则事后无法区分"它自己想通的"和"被提示的"）。
    """
    index: int
    role: str = "assistant"
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    probe: Optional[dict] = None
    injected: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "role": self.role,
            "text": self.text,
            "tool_calls": self.tool_calls,
            "tool_results": [t.to_dict() for t in self.tool_results],
            "probe": self.probe,
            "injected": self.injected,
        }


@dataclass
class Intervention:
    """
    Monitor 的一次注入。

    signal : "S1" 无视觉反事实 / "S2" 隐空间判据 / "S3" 证据落差
    strength : 剂量档位（剂量-反应实验的自变量，见 CLAUDE.md 7.1）
    text : 实际注入的文本，原样记录 —— 泄漏对照要按字面比对
    """
    signal: str
    strength: int = 0
    text: str = ""
    payload: dict = field(default_factory=dict)
    turn_index: int = -1

    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "strength": self.strength,
            "text": self.text,
            "payload": self.payload,
            "turn_index": self.turn_index,
        }


@dataclass
class Trajectory:
    """
    一个 episode 的完整轨迹。

    vision=False 的那条是 **独立 rollout**，不是让 Actor"假装没看见" ——
    S1 的全部效力来自它真的没有图像输入（见 CLAUDE.md 十）。

    落盘为 JSONL，7.4 的 Monitor 独立评估要复用同一批轨迹。
    """
    episode_id: str
    image_path: str
    vision: bool = True
    turns: list[Turn] = field(default_factory=list)
    verdict: Optional[str] = None          # "real" | "fake"
    confidence: float = 0.0
    evidence_cited: list[str] = field(default_factory=list)
    interventions: list[Intervention] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "image_path": self.image_path,
            "vision": self.vision,
            "turns": [t.to_dict() for t in self.turns],
            "verdict": self.verdict,
            "confidence": self.confidence,
            "evidence_cited": self.evidence_cited,
            "interventions": [i.to_dict() for i in self.interventions],
            "meta": self.meta,
        }

    def tool_call_count(self) -> int:
        return sum(len(t.tool_calls) for t in self.turns)

    def all_tool_results(self) -> list[ToolResult]:
        return [r for t in self.turns for r in t.tool_results]
