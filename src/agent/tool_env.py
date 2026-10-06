"""工具执行环境（M1）。

把 eval/tool_reliability.py 里的图像加载/编码逻辑抽出来给 Actor 用，
并补上两个 E1 没做的部分：

  1. `region` 参数 —— center 与 full 的区别是**要不要重采样**。
     center 纯裁剪，保留原始像素统计（噪声/压缩痕迹完好）；
     full   整图缩放，会破坏这些痕迹但能看到全局布局。
     这是 Actor 必须权衡的真实取舍，不是凑数的参数。

  2. 自然图参考区间 (`ref`) —— 展示给 Actor 看"自然图的正常范围是多少"。
     只给区间不给校准分数：给分数等于把工具变成黑箱分类器，
     Actor 的"加权"就没有讨论余地了。校准分数单独存在
     ToolResult.calibrated 里，**只给 Monitor 用**。

特征缓存按 (路径, region, size) 落盘：5 个工具共用一次提取，
避免 Actor 连调 5 个工具时把同一张图算 5 遍。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from evidence.schemas import ToolResult
from agent.tools import FAMILIES, FEATURE_UNITS, family_of

# ── 路径 ──
DATA_ROOT = Path("/root/autodl-tmp")
CACHE_DIR = DATA_ROOT / "cache" / "agent_tools"
CALIB_PATH = DATA_ROOT / "checkpoints" / "tool_calibration.json"
REF_PATH = DATA_ROOT / "checkpoints" / "tool_refs.json"
# E1 跑出来的自然图 LBP 参考（每个编码条件一个）
LBP_REF_DIR = DATA_ROOT / "cache" / "coco_official_vs_sdxl"

DEFAULT_SIZE = 256

# 模块级单例。torch 模型构造有开销，Actor 一个 episode 会调很多次。
_EXTRACTORS: dict = {}
_CALIB: dict | None = None
_REFS: dict | None = None
_LBP_REF: np.ndarray | None = None
_LBP_TRIED = False


# ══════════════════════════════════════════════
# 图像加载
# ══════════════════════════════════════════════

def load_image(path: str | Path, region: str = "center", size: int = DEFAULT_SIZE):
    """
    读图 → RGB → (size, size)。返回 PIL.Image 或 None。

    center : 短边不足 size 时才 LANCZOS 缩放，否则**纯裁剪不重采样**。
             原始像素统计完好 —— 噪声残差、DCT 块效应这些工具都依赖它。
    full   : 整图按长边缩放到 size（LANCZOS），再中心裁剪。
             必然重采样，会抹掉一部分低层痕迹，但保留全局构图。
    """
    from PIL import Image

    if region not in ("center", "full"):
        raise ValueError(f"未知 region {region!r}，只支持 center / full")

    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size

            if region == "full":
                scale = size / max(w, h)
                nw, nh = max(size, int(round(w * scale))), max(size, int(round(h * scale)))
                im = im.resize((nw, nh), Image.LANCZOS)
                w, h = im.size
            else:  # center
                short = min(w, h)
                if short < size:
                    scale = size / short
                    im = im.resize((max(size, int(round(w * scale))),
                                    max(size, int(round(h * scale)))),
                                   Image.LANCZOS)
                    w, h = im.size

            left, top = (w - size) // 2, (h - size) // 2
            return im.crop((left, top, left + size, top + size))
    except Exception:
        return None


def to_tensor(im):
    """PIL.Image → (1, 3, H, W) float32 张量，值域 [0, 1]。"""
    import torch
    arr = np.asarray(im, dtype=np.uint8)
    t = torch.from_numpy(arr.copy()).permute(2, 0, 1).float().div_(255.0)
    return t.unsqueeze(0)


def to_gray(images):
    return images.mean(dim=1, keepdim=True)


# ══════════════════════════════════════════════
# 懒加载
# ══════════════════════════════════════════════

def get_extractors():
    """构造一次，全局复用。CPU —— 工具层不吃卡，卡留给 Actor。"""
    if not _EXTRACTORS:
        import torch
        from feature_extractors.artifact_detector import ArtifactDetector
        from feature_extractors.frequency_analyzer import FrequencyAnalyzer

        torch.set_num_threads(min(2, max(1, (os.cpu_count() or 2) // 2)))
        _EXTRACTORS["artifact"] = ArtifactDetector(device="cpu")
        _EXTRACTORS["freq"] = FrequencyAnalyzer(device="cpu")
    return _EXTRACTORS["artifact"], _EXTRACTORS["freq"]


def get_calib() -> dict:
    """M2 标定结果。用来算 ToolResult.calibrated（只给 Monitor）。"""
    global _CALIB
    if _CALIB is None:
        _CALIB = (json.loads(CALIB_PATH.read_text())
                  if CALIB_PATH.exists() else {})
    return _CALIB


def get_refs() -> dict:
    """自然图参考区间 {feature: [p05, p95]}，展示给 Actor。"""
    global _REFS
    if _REFS is None:
        _REFS = (json.loads(REF_PATH.read_text())
                 if REF_PATH.exists() else {})
    return _REFS


def get_lbp_ref():
    """
    自然图 LBP 直方图（natural 条件）。没有就返回 None ——
    此时 texture_lbp 少一维 lbp_chi2_natural_ref，ToolResult.values 会缺这个 key。
    Actor 侧不用关心，缺了就是缺了；但标定/统计那边要能容忍。
    """
    global _LBP_REF, _LBP_TRIED
    if not _LBP_TRIED:
        _LBP_TRIED = True
        p = LBP_REF_DIR / "lbp_ref_natural.npy"
        if p.exists():
            try:
                _LBP_REF = np.load(p)
            except Exception:
                _LBP_REF = None
    return _LBP_REF


# ══════════════════════════════════════════════
# 特征提取
# ══════════════════════════════════════════════

def _extract_all(path: str, region: str, size: int) -> dict | None:
    """一张图的全部 19 个原始特征。返回 None 表示读图失败。"""
    import torch
    from feature_extractors.artifact_detector import (
        _chi_square_distance, _compute_lbp_map)

    im = load_image(path, region, size)
    if im is None:
        return None

    det, freq = get_extractors()
    img = to_tensor(im)
    with torch.no_grad():
        a = det.extract_evidence(img)[0]
        f = freq.extract_evidence(img)[0]

        vals: dict[str, float] = {}
        for spec in FAMILIES.values():
            for feat in spec["features"]:
                if hasattr(a, feat):
                    vals[feat] = float(getattr(a, feat))
                elif hasattr(f, feat):
                    vals[feat] = float(getattr(f, feat))

        # 自然图参考版 LBP chi2 —— 只有拿到参考才算得了
        lbp_ref = get_lbp_ref()
        if lbp_ref is not None:
            hist = torch.histc(_compute_lbp_map(to_gray(img)),
                               bins=len(lbp_ref), min=0, max=255)
            hist = hist / (hist.sum() + 1e-10)
            ref_t = torch.from_numpy(lbp_ref.astype(np.float32))
            vals["lbp_chi2_natural_ref"] = float(
                _chi_square_distance(hist, ref_t).item())

    return vals


# ── 特征缓存 ──

def _cache_key(path: str, region: str, size: int) -> str:
    h = hashlib.sha1(f"{path}|{region}|{size}".encode())
    return h.hexdigest()[:20]


def _cache_get(path: str, region: str, size: int) -> dict | None:
    p = CACHE_DIR / f"{_cache_key(path, region, size)}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())["values"]
        except Exception:
            return None
    return None


def _cache_put(path: str, region: str, size: int, values: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = CACHE_DIR / f"{_cache_key(path, region, size)}.json"
        p.write_text(json.dumps({"path": path, "region": region,
                                 "size": size, "values": values},
                                ensure_ascii=False))
    except Exception:
        pass  # 缓存写失败不该影响主流程


def clear_cache() -> int:
    if not CACHE_DIR.exists():
        return 0
    n = 0
    for p in CACHE_DIR.glob("*.json"):
        p.unlink()
        n += 1
    return n


# ══════════════════════════════════════════════
# 工具调用
# ══════════════════════════════════════════════

def _calibrate(family: str, values: dict) -> dict:
    """
    按 M2 标定算该族的分数与方向。**只给 Monitor，不展示给 Actor。**

    分数 > 0 偏向 fake。标定只在 ID（COCO real + SDXL fake）上拟合过，
    正类是 SDXL —— 对没见过的生成器，这个方向的可靠性本身是要打问号的，
    这正是 OOD 上要观察的东西。
    """
    calib = get_calib().get("tools", {}).get(family)
    if not calib:
        return {}

    feats = calib["features"]
    if any(f not in values for f in feats):
        return {}

    x = np.array([values[f] for f in feats], float)
    z = (x - np.array(calib["mean"])) / np.array(calib["std"])
    score = float(z @ np.array(calib["coef"]) + calib["intercept"])
    return {
        "score": round(score, 4),
        "direction": "fake" if score > 0 else "real",
        "abs_score": round(abs(score), 4),
        "cv_auc": calib["cv_auc"],
        "fitted_on": "ID (COCO real + SDXL fake)",
    }


def run_tool(family: str, path: str, region: str = "center",
             size: int = DEFAULT_SIZE, use_cache: bool = True) -> ToolResult:
    """
    执行一个工具族，返回 ToolResult。

    绝不抛异常 —— 工具失败也是一种要记录的信息（Actor 可能引用了它，
    Monitor 的 S3 需要知道哪些证据实际没拿到）。失败时 ok=False 且 values 为空。
    """
    t0 = time.time()
    try:
        spec = family_of(family)
    except KeyError as e:
        return ToolResult(tool=family, ok=False, error=str(e),
                          args={"region": region})

    res = ToolResult(tool=family, label=spec["label"],
                     args={"region": region, "size": size})

    values = _cache_get(path, region, size) if use_cache else None
    if values is None:
        try:
            values = _extract_all(path, region, size)
        except Exception as e:
            res.ok = False
            res.error = f"{type(e).__name__}: {e}"
            res.elapsed_ms = (time.time() - t0) * 1000
            return res
        if values is not None and use_cache:
            _cache_put(path, region, size, values)

    if values is None:
        res.ok = False
        res.error = f"读图失败: {path}"
        res.elapsed_ms = (time.time() - t0) * 1000
        return res

    feats = spec["features"]
    res.values = {f: values[f] for f in feats if f in values}
    missing = [f for f in feats if f not in values]

    refs = get_refs()
    res.ref = {f: refs[f] for f in feats if f in refs}

    res.calibrated = _calibrate(family, res.values)

    if missing:
        # 不算硬失败：缺的是可选特征（多半是 LBP 参考没生成）
        res.error = f"缺少特征 {missing}（不阻塞）"

    res.elapsed_ms = (time.time() - t0) * 1000
    return res


def format_result(res: ToolResult) -> str:
    """
    工具结果 → 给 Actor 看的文本。

    保留**原始数值**（CLAUDE.md 十六：禁止只给自然语言摘要，S3 依赖原始值）。
    附上自然图参考区间，但**不给校准分数**。
    """
    if not res.ok:
        return f"[{res.tool}] 执行失败：{res.error}"

    lines = [f"[{res.tool} · {res.label}] region={res.args.get('region')}"]
    for feat, v in res.values.items():
        unit = FEATURE_UNITS.get(feat, "")
        rng = res.ref.get(feat)
        ref_s = ""
        if rng:
            ref_s = f"   (自然图参考 {rng[0]:.4f} ~ {rng[1]:.4f})"
        lines.append(f"  {feat:<30s} = {v:>12.6f}  {unit}{ref_s}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    fam = sys.argv[1] if len(sys.argv) > 1 else "freq_spectrum"
    img = sys.argv[2] if len(sys.argv) > 2 else None
    if not img:
        print("用法: python -m agent.tool_env <family> <image> [region]")
        print(f"可用族: {sorted(FAMILIES)}")
        raise SystemExit(1)
    reg = sys.argv[3] if len(sys.argv) > 3 else "center"
    r = run_tool(fam, img, reg)
    print(format_result(r))
    print(f"\ncalibrated（只给 Monitor）: {r.calibrated}")
    print(f"耗时 {r.elapsed_ms:.0f} ms")
