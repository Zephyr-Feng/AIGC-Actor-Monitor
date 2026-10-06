"""
feature_extractors/artifact_detector.py

伪影检测模块 (Artifact Detector) — 从多个维度检测 AI 生成图片的伪影痕迹。

检测维度
--------
1. SRM 噪声残差分析   — 固定高通滤波器提取噪声残差，统计分布异常
2. LBP 局部纹理分析    — 局部二值模式直方图，检测纹理分布异常
3. 梯度/边缘分析       — Sobel 梯度 + 边缘一致性检测
4. 颜色通道相关性      — RGB 通道间的统计关系异常
5. 逐块伪影热图        — 按 patch 打分生成空间伪影热图

参考:
- Fridrich & Kodovsky, "Rich Models for Steganalysis of Digital Images"
- Zhang et al., "Detecting Prohibited Objects with Spatial Rich Model"
- Nature Methods, "Local Binary Patterns" (Ojala et al.)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from evidence.schemas import ArtifactEvidence
from feature_extractors.base import BaseFeatureExtractor


# ============================================================
# 工具函数
# ============================================================

def _build_srm_filters(device: torch.device) -> torch.Tensor:
    """
    构建 SRM (Spatial Rich Model) 高通滤波器组，用于提取噪声残差。

    Returns
    -------
    filters : Tensor  (5, 1, 3, 3)
        5 个 3×3 高通滤波器。
    """
    # fmt: off
    filters = [
        #  中心点残差
        [[ 0,  0,  0], [ 0, -1,  0], [ 0,  0,  0]],
        #  水平一阶差分
        [[ 0,  0,  0], [ 0,  1, -1], [ 0,  0,  0]],
        #  垂直一阶差分
        [[ 0,  0,  0], [ 0, -1,  0], [ 0,  1,  0]],
        #  对角线一阶差分
        [[ 0,  0,  0], [ 0, -1,  0], [ 0,  0,  1]],
        # 拉普拉斯
        [[ 1,  2,  1], [ 2, -12, 2], [ 1,  2,  1]],
    ]
    # fmt: on
    t = torch.tensor(filters, dtype=torch.float32).unsqueeze(1)  # (5, 1, 3, 3)
    # 归一化使每个滤波器均值为 0
    t = t / (t.abs().sum(dim=(2, 3), keepdim=True) + 1e-10)
    return t.to(device)


def _build_sobel_kernels(device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    """Sobel 梯度算子 (1, 1, 3, 3)。"""
    sobel_x = torch.tensor([[[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]],
                           dtype=torch.float32).unsqueeze(0).to(device)
    sobel_y = torch.tensor([[[-1, -2, -1], [0, 0, 0], [1, 2, 1]]],
                           dtype=torch.float32).unsqueeze(0).to(device)
    return sobel_x, sobel_y


@torch.no_grad()
def _compute_lbp_map(gray: torch.Tensor) -> torch.Tensor:
    """
    计算局部二值模式 (LBP) 图谱。

    Parameters
    ----------
    gray : Tensor  (B, 1, H, W)
        灰度图，值 [0, 1]。

    Returns
    -------
    lbp : Tensor  (B, 1, H-2, W-2)
        LBP 编码图（值为 0-255）。
    """
    B, _, H, W = gray.shape
    # 8 邻域偏移
    offsets = [(-1, -1), (-1, 0), (-1, 1),
               (0, -1),           (0, 1),
               (1, -1),  (1, 0),  (1, 1)]

    center = gray[:, :, 1:-1, 1:-1]        # (B, 1, H-2, W-2)
    lbp = torch.zeros_like(center, dtype=torch.long)

    for i, (dr, dc) in enumerate(offsets):
        neighbors = gray[:, :, 1 + dr: H - 1 + dr, 1 + dc: W - 1 + dc]
        bit = (neighbors >= center).long()  # 阈值化
        lbp += bit * (1 << i)

    return lbp.float()


def _chi_square_distance(hist_a: torch.Tensor, hist_b: torch.Tensor) -> torch.Tensor:
    """卡方距离。"""
    return 0.5 * ((hist_a - hist_b) ** 2 / (hist_a + hist_b + 1e-10)).sum()


# ============================================================
# 主模块
# ============================================================

class ArtifactDetector(BaseFeatureExtractor):
    """
    伪影检测模块。

    Parameters
    ----------
    lbp_bins : int
        LBP 直方图 bin 数（默认 256，对应完整 8 位 LBP）。
    patch_size : int
        伪影热图的 patch 尺寸（默认 64）。
    device : str | torch.device
        运行设备。
    """

    def __init__(
        self,
        lbp_bins: int = 256,
        patch_size: int = 64,
        device: str | torch.device = "cpu",
    ):
        super().__init__()
        self.lbp_bins = lbp_bins
        self.patch_size = patch_size
        self.device = torch.device(device)

        # ---- 可注册的滤波器 (buffer, 不参与训练) ----
        self.register_buffer("srm_filters", _build_srm_filters(self.device))
        sobel_x, sobel_y = _build_sobel_kernels(self.device)
        self.register_buffer("sobel_x", sobel_x)
        self.register_buffer("sobel_y", sobel_y)

        # ---- 自然图像 LBP 参考直方图（默认均匀分布作为基线） ----
        # 在实际使用时可用大量自然图统计替换
        self.register_buffer(
            "_lbp_reference",
            torch.ones(lbp_bins, device=self.device) / lbp_bins,
        )

    # ──────────────────────────────────────────────
    # 子模块：SRM 噪声残差
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _extract_noise_residual(self, gray: torch.Tensor) -> torch.Tensor:
        """
        SRM 高通滤波器提取噪声残差。

        Returns
        -------
        residual : Tensor  (B, 5, H, W)
            5 个滤波器的噪声残差图。
        """
        # group conv: 每个滤波器在单通道灰度图上卷积
        # gray: (B, 1, H, W), srm: (5, 1, 3, 3)
        residual = F.conv2d(gray, self.srm_filters, padding=1)  # (B, 5, H, W)
        return residual

    # ──────────────────────────────────────────────
    # 子模块：LBP 纹理分析
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _analyze_lbp(self, gray: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        LBP 纹理分析。

        Returns
        -------
        lbp_map : Tensor  (B, 1, H-2, W-2)
        chi2_dist : Tensor  (B,)
            每个样本的 LBP 直方图卡方距离。
        """
        lbp_map = _compute_lbp_map(gray)  # (B, 1, H', W')
        B = lbp_map.shape[0]

        chi2_list = []
        for i in range(B):
            hist = torch.histc(lbp_map[i], bins=self.lbp_bins, min=0, max=255)
            hist = hist / (hist.sum() + 1e-10)
            chi2_list.append(_chi_square_distance(hist, self._lbp_reference))

        return lbp_map, torch.stack(chi2_list)

    # ──────────────────────────────────────────────
    # 子模块：梯度 / 边缘分析
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _analyze_gradient(self, gray: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        梯度分析。

        Returns
        -------
        grad_mag : Tensor  (B, 1, H, W)
            梯度幅值图。
        consistency : Tensor  (B,)
            梯度一致性得分（越低越一致）。
        """
        pad = 1
        gx = F.conv2d(gray, self.sobel_x, padding=pad)
        gy = F.conv2d(gray, self.sobel_y, padding=pad)
        grad_mag = torch.sqrt(gx ** 2 + gy ** 2 + 1e-10)  # (B, 1, H, W)

        # 梯度一致性: 局部梯度方向方差
        # 将梯度方向分 bin，计算局部直方图的峰度
        B, _, H, W = grad_mag.shape
        angle = torch.atan2(gy, gx)  # [-π, π]

        # 将方向离散化为 8 个 bin
        n_bins = 8
        bin_idx = ((angle / np.pi + 1) * (n_bins / 2)).long().clamp(0, n_bins - 1)

        consistencies = []
        for i in range(B):
            # 用 16×16 块内的方向直方图计算一致性
            k = 16
            histograms: list[float] = []
            for row in range(0, H - k + 1, k // 2):
                for col in range(0, W - k + 1, k // 2):
                    patch_bins = bin_idx[i, 0, row:row + k, col:col + k]
                    # 使用注意力加权的方向分布
                    weights = grad_mag[i, 0, row:row + k, col:col + k]
                    hist = torch.zeros(n_bins, device=self.device)
                    for b in range(n_bins):
                        mask = (patch_bins == b)
                        hist[b] = weights[mask].sum()
                    hist = hist / (hist.sum() + 1e-10)
                    # 用最大 bin 比例衡量一致性
                    histograms.append(hist.max().item())

            consistencies.append(1.0 - float(np.mean(histograms)))

        return grad_mag, torch.tensor(consistencies, device=self.device)

    # ──────────────────────────────────────────────
    # 子模块：颜色通道相关性
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _analyze_color_correlation(self, rgb: torch.Tensor) -> torch.Tensor:
        """
        颜色通道相关性异常分析。

        Returns
        -------
        abnormality : Tensor  (B,)
            颜色异常得分 [0, 1]。
        """
        B, C, H, W = rgb.shape
        scores = []
        for i in range(B):
            img = rgb[i]  # (3, H, W)
            # 展平每个通道
            r = img[0].reshape(-1)
            g = img[1].reshape(-1)
            b = img[2].reshape(-1)

            # 通道间相关系数
            corr_rg = torch.corrcoef(torch.stack([r, g]))[0, 1]
            corr_rb = torch.corrcoef(torch.stack([r, b]))[0, 1]
            corr_gb = torch.corrcoef(torch.stack([g, b]))[0, 1]

            # 自然图像中 RGB 通道通常高度相关
            # AI 生成图像的通道间相关性可能异常（过低或过高）
            mean_corr = (corr_rg + corr_rb + corr_gb) / 3
            # 理想自然图约 0.9 左右，偏离越远分数越高
            score = 1.0 - min(1.0, mean_corr.abs().item() / 0.95)
            scores.append(score)

        return torch.tensor(scores, device=self.device)

    # ──────────────────────────────────────────────
    # 子模块：逐块伪影热图
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _compute_patch_artifact_map(
        self, noise_residual: torch.Tensor
    ) -> list[np.ndarray]:
        """
        基于噪声残差统计量生成逐块伪影热图。

        Parameters
        ----------
        noise_residual : Tensor  (B, 5, H, W)

        Returns
        -------
        heatmaps : list[np.ndarray (H', W')]
            每个样本的伪影热图（得分越高越异常）。
        """
        B, F, H, W = noise_residual.shape
        P = self.patch_size
        heatmaps = []

        for i in range(B):
            # 聚合所有滤波器通道的残差幅值
            res = noise_residual[i].abs().mean(dim=0)  # (H, W)
            # 分块
            h_patches = max(1, H // P)
            w_patches = max(1, W // P)
            h_remain = H - h_patches * P
            w_remain = W - w_patches * P
            start_h = h_remain // 2
            start_w = w_remain // 2

            scores = np.zeros((h_patches, w_patches), dtype=np.float32)
            for ph in range(h_patches):
                for pw in range(w_patches):
                    patch = res[start_h + ph * P: start_h + (ph + 1) * P,
                                start_w + pw * P: start_w + (pw + 1) * P]
                    # 用 patch 内噪声幅值的均值 + 方差作为异常得分
                    scores[ph, pw] = (patch.mean().item() +
                                      0.5 * patch.std().item())

            # 归一化到 [0, 1]
            if scores.max() > scores.min():
                scores = (scores - scores.min()) / (scores.max() - scores.min())
            heatmaps.append(scores)

        return heatmaps

    # ──────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def extract_evidence(self, images: torch.Tensor) -> list[ArtifactEvidence]:
        """
        提取伪影检测证据。

        Parameters
        ----------
        images : Tensor  (B, 3, H, W)
            RGB 图像，值范围 [0, 1]。

        Returns
        -------
        evidences : list[ArtifactEvidence]
            每个样本的证据。
        """
        images = images.to(self.device)
        B, C, H, W = images.shape
        gray = images.mean(dim=1, keepdim=True)  # (B, 1, H, W)

        # ---- 1) 噪声残差 ----
        residual = self._extract_noise_residual(gray)  # (B, 5, H, W)

        # ---- 2) LBP 纹理分析 ----
        _, lbp_chi2 = self._analyze_lbp(gray)  # (B,)

        # ---- 3) 梯度分析 ----
        grad_mag, grad_consistency = self._analyze_gradient(gray)

        # ---- 4) 颜色相关性 ----
        color_scores = self._analyze_color_correlation(images)

        # ---- 5) 热图 ----
        heatmaps = self._compute_patch_artifact_map(residual)

        # ---- 组装证据 ----
        evidences = []
        for i in range(B):
            noise_stats = residual[i].reshape(5, -1)

            ev = ArtifactEvidence(
                local_anomaly_score=float(1.0 / (1.0 + np.exp(
                    -lbp_chi2[i].cpu().item() * 2 + 3
                ))),
                edge_artifact_score=float(grad_consistency[i].cpu().item()),
                texture_abnormality_score=float(
                    1.0 / (1.0 + np.exp(-lbp_chi2[i].cpu().item() * 2 + 3))
                ),
                color_abnormality_score=float(color_scores[i].cpu().item()),

                noise_residual_mean=float(noise_stats.mean().cpu().item()),
                noise_residual_std=float(noise_stats.std().cpu().item()),
                noise_residual_skew=float(
                    (noise_stats - noise_stats.mean()).pow(3).mean().cpu().item()
                    / (noise_stats.std().cpu().item() ** 3 + 1e-10)
                ),

                lbp_histogram_chi2=float(lbp_chi2[i].cpu().item()),
                gradient_consistency=float(grad_consistency[i].cpu().item()),

                patch_artifact_map=heatmaps[i],
            )
            evidences.append(ev)

        return evidences
