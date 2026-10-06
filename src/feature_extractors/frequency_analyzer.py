"""
feature_extractors/frequency_analyzer.py

频谱分析模块 (Frequency Analyzer) — 从频域角度检测 AI 生成图片的痕迹。

检测维度
--------
1. FFT 径向频谱轮廓    — 按频率半径的平均幅值分布
2. FFT 角度频谱轮廓    — 按方向角度的频谱能量分布
3. 频谱衰减斜率         — 功率谱随频率的衰减特征（AI 图常异常）
4. DCT 块分析          — 分块 DCT 系数的统计特征
5. 频谱一致性           — 局部区域之间的频谱一致性

参考:
- Durall et al., "Combining FFT and Spectral Analysis for GAN Detection"
- Frank et al., "Leveraging Frequency Analysis for Deep Fake Image Recognition"
- Wang et al., "CNN-generated images are surprisingly easy to spot... for now"
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from evidence.schemas import FrequencyEvidence
from feature_extractors.base import BaseFeatureExtractor


# ============================================================
# 工具函数
# ============================================================

def _fft_2d_centered(x: torch.Tensor) -> torch.Tensor:
    """
    2D FFT 并将零频移到中心。

    Parameters
    ----------
    x : Tensor  (B, 1, H, W)
        灰度图。

    Returns
    -------
    spectrum : Tensor  (B, 1, H, W)
        幅值谱（对数尺度）。
    """
    B, _, H, W = x.shape

    # torch.fft.fft2 输出 shape (B, 1, H, W//2+1) for real input
    # 使用 fftn/ifftn 或手动 shift
    spectrum = torch.fft.fft2(x)  # (B, 1, H, W)
    spectrum = torch.fft.fftshift(spectrum, dim=(-2, -1))
    magnitude = spectrum.abs() + 1e-10
    return magnitude


def _radial_profile(
    spectrum: torch.Tensor,
    n_rings: int = 50,
) -> torch.Tensor:
    """
    计算径向频谱轮廓（从中心到边缘的幅值分布）。

    Parameters
    ----------
    spectrum : Tensor  (B, 1, H, W)
    n_rings : int
        径向环数。

    Returns
    -------
    profile : Tensor  (B, n_rings)
    """
    B, _, H, W = spectrum.shape
    cy, cx = H // 2, W // 2
    max_radius = min(cy, cx)

    # 距离网格
    y, x = torch.meshgrid(
        torch.arange(H, device=spectrum.device, dtype=torch.float32),
        torch.arange(W, device=spectrum.device, dtype=torch.float32),
        indexing="ij",
    )
    dist = torch.sqrt((y - cy) ** 2 + (x - cx) ** 2)  # (H, W)

    # 分配到 n_rings 个环
    ring_width = max_radius / n_rings
    ring_idx = (dist / ring_width).long().clamp(0, n_rings - 1)  # (H, W)

    profiles = []
    for i in range(B):
        profile = torch.zeros(n_rings, device=spectrum.device)
        counts = torch.zeros(n_rings, device=spectrum.device)
        for r in range(n_rings):
            mask = (ring_idx == r)
            profile[r] = spectrum[i, 0, mask].mean()
            counts[r] = mask.sum()
        # 确保有值的 bins
        profile[counts > 0] /= (counts[counts > 0] / counts[counts > 0].max())
        profiles.append(profile)

    return torch.stack(profiles)


def _angular_profile(
    spectrum: torch.Tensor,
    n_angles: int = 36,
    inner_radius: int = 5,
) -> torch.Tensor:
    """
    计算角度频谱轮廓（沿方向的能量分布）。

    Parameters
    ----------
    spectrum : Tensor  (B, 1, H, W)
    n_angles : int
        角度方向数。
    inner_radius : int
        排除中心的直流/极低频区域。

    Returns
    -------
    profile : Tensor  (B, n_angles)
    """
    B, _, H, W = spectrum.shape
    cy, cx = H // 2, W // 2
    max_radius = min(cy, cx)

    y, x = torch.meshgrid(
        torch.arange(H, device=spectrum.device, dtype=torch.float32),
        torch.arange(W, device=spectrum.device, dtype=torch.float32),
        indexing="ij",
    )
    dist = torch.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    angle = torch.atan2(y - cy, x - cx)  # [-π, π]

    # 角度区间
    angle_bin = ((angle / np.pi + 1) * (n_angles / 2)).long().clamp(0, n_angles - 1)

    profiles = []
    for i in range(B):
        profile = torch.zeros(n_angles, device=spectrum.device)
        counts = torch.zeros(n_angles, device=spectrum.device)
        for a in range(n_angles):
            mask = (angle_bin == a) & (dist > inner_radius)
            if mask.sum() > 0:
                profile[a] = spectrum[i, 0, mask].mean()
                counts[a] = mask.sum()
        profiles.append(profile)

    return torch.stack(profiles)


def _dct_2d_block(x: torch.Tensor, block_size: int = 8) -> torch.Tensor:
    """
    对图像进行分块 DCT（近似 DCT-II）。

    Parameters
    ----------
    x : Tensor  (B, 1, H, W)
    block_size : int
        DCT 块大小（默认 8，兼容 JPEG）。

    Returns
    -------
    dct_coeffs : Tensor  (B, 1, H//block_size * W//block_size, block_size, block_size)
    """
    B, _, H, W = x.shape
    # pad 使尺寸可整除
    pad_h = (block_size - H % block_size) % block_size
    pad_w = (block_size - W % block_size) % block_size
    x = F.pad(x, (0, pad_w, 0, pad_h), mode="reflect")

    # 分块 unfold
    patches = F.unfold(x, kernel_size=block_size, stride=block_size)  # (B, 1*K*K, N)
    N = patches.shape[-1]
    patches = patches.view(B, 1, block_size, block_size, N)  # (B, 1, K, K, N)

    # 对每个块做 DCT
    # 使用矩阵乘法实现 DCT-II
    dct_coeffs = []
    for i in range(B):
        block_dcts = []
        for n in range(N):
            block = patches[i, 0, :, :, n]  # (K, K)
            block_dct = _dct_2d_single(block)
            block_dcts.append(block_dct)
        dct_coeffs.append(torch.stack(block_dcts))
    return torch.stack(dct_coeffs)


def _dct_2d_single(block: torch.Tensor) -> torch.Tensor:
    """
    对单个 (K, K) 块执行 DCT-II 变换。
    """
    K = block.shape[0]
    n = torch.arange(K, device=block.device, dtype=torch.float32)
    k = torch.arange(K, device=block.device, dtype=torch.float32).unsqueeze(1)
    # DCT 矩阵: C[k, n] = cos(π * k * (2n + 1) / (2 * K))
    C = torch.cos(np.pi * k * (2 * n + 1) / (2 * K))
    C[0] *= 1.0 / np.sqrt(2)
    C *= np.sqrt(2.0 / K)
    return C @ block @ C.T


def _fit_spectral_slope(
    radial_profile: torch.Tensor,
    fit_range: tuple[int, int] = (5, -5),
) -> torch.Tensor:
    """
    在径向频谱轮廓的对数域拟合衰减斜率。

    Returns
    -------
    slopes : Tensor  (B,)
    """
    B, n_rings = radial_profile.shape
    start, end = fit_range
    if end < 0:
        end = n_rings + end

    x = torch.arange(start, end, device=radial_profile.device, dtype=torch.float32)
    slopes = []
    for i in range(B):
        y = torch.log(radial_profile[i, start:end] + 1e-10)
        # 线性回归: slope = cov(x, y) / var(x)
        x_mean = x.mean()
        y_mean = y.mean()
        slope = ((x - x_mean) * (y - y_mean)).sum() / ((x - x_mean) ** 2).sum()
        slopes.append(slope)
    return torch.stack(slopes)


# ============================================================
# 主模块
# ============================================================

class FrequencyAnalyzer(BaseFeatureExtractor):
    """
    频谱分析模块。

    Parameters
    ----------
    n_rings : int
        径向频谱环数。
    n_angles : int
        角度方向数。
    dct_block_size : int
        DCT 块大小（默认 8）。
    device : str | torch.device
    """

    def __init__(
        self,
        n_rings: int = 50,
        n_angles: int = 36,
        dct_block_size: int = 8,
        device: str | torch.device = "cpu",
    ):
        super().__init__()
        self.n_rings = n_rings
        self.n_angles = n_angles
        self.dct_block_size = dct_block_size
        self.device = torch.device(device)

    # ──────────────────────────────────────────────
    # 子模块：FFT 频谱分析
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _analyze_fft(
        self, gray: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        FFT 频谱分析。

        Returns
        -------
        radial : Tensor  (B, n_rings)
        angular : Tensor  (B, n_angles)
        slopes : Tensor  (B,)
        angular_var : Tensor  (B,)
        """
        # 使用窗口减少频谱泄漏
        window = torch.hann_window(gray.shape[-1], device=self.device) * \
                 torch.hann_window(gray.shape[-2], device=self.device).unsqueeze(1)
        windowed = gray * window.view(1, 1, gray.shape[-2], gray.shape[-1])

        spectrum = _fft_2d_centered(windowed)  # (B, 1, H, W)

        # 径向轮廓
        radial = _radial_profile(spectrum, self.n_rings)  # (B, n_rings)

        # 角度轮廓
        angular = _angular_profile(spectrum, self.n_angles)

        # 频谱衰减斜率
        slopes = _fit_spectral_slope(radial)

        # 角度方差（各向异性指标）
        angular_var = angular.var(dim=1)

        return radial, angular, slopes, angular_var

    # ──────────────────────────────────────────────
    # 子模块：DCT 分析
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _analyze_dct(
        self, gray: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        DCT 块分析。

        Returns
        -------
        kurtosis : Tensor  (B,)
            所有 DCT 系数的峰度。
        block_consistency : Tensor  (B,)
            块间一致性得分。
        high_freq_zeros_ratio : Tensor  (B,)
            高频分量置零率（JPEG 压缩痕迹）。
        """
        B, _, H, W = gray.shape
        K = self.dct_block_size

        # 对每个通道做 DCT（这里用 grayscale）
        dct_coeffs = _dct_2d_block(gray, K)  # (B, 1, N, K, K)
        N = dct_coeffs.shape[2]

        kurtosis_list = []
        consistency_list = []
        zeros_ratio_list = []

        for i in range(B):
            coeffs = dct_coeffs[i]  # (N, K, K)

            # 展平所有系数
            flat = coeffs.reshape(-1)
            # 峰度
            mean = flat.mean()
            std = flat.std() + 1e-10
            kurt = ((flat - mean) ** 4).mean() / (std ** 4) - 3
            kurtosis_list.append(kurt.item())

            # 块间一致性：DC 系数的方差比 AC 系数的方差
            dc_vals = coeffs[:, 0, 0]  # (N,)
            ac_vals = coeffs[:, 0, 1:]  # (N, K*K-1)
            dc_var = dc_vals.var()
            ac_means = ac_vals.mean(dim=0)
            # 一致性 = DC 方差 / AC 均值方差（越小越一致）
            consist = dc_var / (ac_means.var() + 1e-10)
            consistency_list.append(min(1.0, consist.item() / 10.0))

            # 高频置零率（块内高频系数的零值比例）
            # 取块中右下角 1/4 区域作为"高频"
            hf_start = K // 2
            hf_coeffs = coeffs[:, hf_start:, hf_start:]  # (N, hf, hf)
            zeros_ratio = (hf_coeffs.abs() < 1e-6).float().mean().item()
            zeros_ratio_list.append(zeros_ratio)

        return (
            torch.tensor(kurtosis_list, device=self.device),
            torch.tensor(consistency_list, device=self.device),
            torch.tensor(zeros_ratio_list, device=self.device),
        )

    # ──────────────────────────────────────────────
    # 子模块：频谱一致性
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def _compute_spectral_consistency(
        self, gray: torch.Tensor
    ) -> torch.Tensor:
        """
        局部区域的频谱一致性检测。
        AI 图往往局部频谱高度均匀（缺少自然图的局部变化）。

        Returns
        -------
        consistency : Tensor  (B,)
            一致性得分（越低越自然，越高越可疑）。
        """
        B, _, H, W = gray.shape
        # 将图像分成 4×4 网格，在每个区域计算频谱
        n_grid = 4
        scores = []
        for i in range(B):
            region_radials = []
            for row in range(n_grid):
                for col in range(n_grid):
                    rh = H // n_grid
                    rw = W // n_grid
                    patch = gray[i, :,
                            row * rh: (row + 1) * rh,
                            col * rw: (col + 1) * rw]
                    # 窗口
                    win = torch.hann_window(patch.shape[-1], device=self.device) * \
                          torch.hann_window(patch.shape[-2], device=self.device).unsqueeze(1)
                    patch_win = patch * win.view(1, patch.shape[-2], patch.shape[-1])
                    spec = _fft_2d_centered(patch_win.unsqueeze(0))  # (1, 1, h, w)
                    radial = _radial_profile(spec, n_rings=20).squeeze(0)  # (20,)
                    # 归一化
                    radial = radial / (radial.sum() + 1e-10)
                    region_radials.append(radial)

            # 计算区域间的频谱相似度
            n_regions = len(region_radials)
            sims = []
            for j in range(n_regions):
                for k in range(j + 1, n_regions):
                    rj = region_radials[j]
                    rk = region_radials[k]
                    # 余弦相似度
                    sim = (rj * rk).sum() / (rj.norm() * rk.norm() + 1e-10)
                    sims.append(sim.item())

            # 一致性得分 = 平均相似度
            # AI 图往往区域间频谱更一致（相似度更高）
            consistency = float(np.mean(sims))
            scores.append(consistency)

        return torch.tensor(scores, device=self.device)

    # ──────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────

    @torch.no_grad()
    def extract_evidence(self, images: torch.Tensor) -> list[FrequencyEvidence]:
        """
        提取频谱分析证据。

        Parameters
        ----------
        images : Tensor  (B, 3, H, W)
            RGB 图像，值范围 [0, 1]。

        Returns
        -------
        evidences : list[FrequencyEvidence]
        """
        images = images.to(self.device)
        B = images.shape[0]
        gray = images.mean(dim=1, keepdim=True)  # (B, 1, H, W)

        # ---- 1) FFT 分析 ----
        radial, angular, slopes, angular_var = self._analyze_fft(gray)

        # ---- 2) DCT 分析 ----
        dct_kurt, dct_consist, dct_zeros = self._analyze_dct(gray)

        # ---- 3) 频谱一致性 ----
        spec_consist = self._compute_spectral_consistency(gray)

        # ---- 计算能量比 ----
        high_cut = self.n_rings * 2 // 3
        low_cut = self.n_rings // 3
        total_energy = radial.sum(dim=1) + 1e-10
        low_energy = radial[:, :low_cut].sum(dim=1)
        mid_energy = radial[:, low_cut:high_cut].sum(dim=1)
        high_energy = radial[:, high_cut:].sum(dim=1)

        # ---- 组装证据 ----
        evidences = []
        for i in range(B):
            ev = FrequencyEvidence(
                high_freq_energy_ratio=float((high_energy[i] / total_energy[i]).cpu()),
                mid_freq_energy_ratio=float((mid_energy[i] / total_energy[i]).cpu()),
                low_freq_energy_ratio=float((low_energy[i] / total_energy[i]).cpu()),
                spectral_falloff_slope=float(slopes[i].cpu()),
                angular_variance=float(angular_var[i].cpu()),

                dct_coeff_kurtosis=float(dct_kurt[i].cpu()),
                dct_block_consistency=float(dct_consist[i].cpu()),
                dct_high_freq_zeros_ratio=float(dct_zeros[i].cpu()),

                spectral_consistency_score=float(spec_consist[i].cpu()),

                fft_radial_profile=radial[i].cpu().numpy(),
                fft_angular_profile=angular[i].cpu().numpy(),
            )
            evidences.append(ev)

        return evidences
