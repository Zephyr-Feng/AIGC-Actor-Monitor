"""
feature_extractors/base.py

所有特征提取器的抽象基类。
"""

from abc import ABC, abstractmethod
from typing import Any

import torch
import torch.nn as nn


class BaseFeatureExtractor(nn.Module, ABC):
    """
    特征提取器基类。

    所有具体的特征提取器（伪影、频谱、噪声一致性等）
    都继承该类，必须实现 `extract_evidence()` 方法。
    """

    def __init__(self):
        super().__init__()

    @abstractmethod
    def extract_evidence(self, images: torch.Tensor) -> dict[str, Any]:
        """
        对输入图像批次提取特征证据。

        Parameters
        ----------
        images : torch.Tensor
            (B, C, H, W) 的 RGB 图像张量，值范围 [0, 1]。

        Returns
        -------
        dict[str, Any]
            包含提取到的全部证据的字典。
        """
        ...

    def forward(self, images: torch.Tensor) -> dict[str, Any]:
        """forward 直接转发到 extract_evidence。"""
        return self.extract_evidence(images)
