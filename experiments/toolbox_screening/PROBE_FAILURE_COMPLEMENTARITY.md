# PROBE 六张误例互补性精查

日期：2026-10-02  
状态：已完成；按方案停止。

## 1. Data

复用同一冻结清单的 300 张图、100 个来源组；PROBE 错误 6 张。没有重跑模型、重算图像分数或调整阈值。所有结果按唯一 `sample_id` 对齐，并核对来源组、生成器、标签和图像相对路径。清单 SHA-256：`61d9455417f5d388edd663ff8497c641db58e3ee3349fda94e64c01b77b2d465`。

判定方向均为 fake probability 越高越像 fake：PROBE/PatchCraft `>0.5`；SAFE 使用独立冻结阈值 `>=0.9561132788658143`；FSD/AIDE 使用先前独立校准的 p_fake `>=0.5`。

## 2. Six Failure Matrix

✓ 表示该辅助工具在 PROBE 错误图上判对。

| # | Image ID | Generator / GT | PROBE score | PatchCraft | SAFE | FSD | AIDE | Correctors |
|---:|---|---|---:|:---:|:---:|:---:|:---:|---|
| 1 | `r0670f47ft:flux` | flux / fake | 0.342577 | ✓ | ✗ | ✗ | ✗ | PatchCraft |
| 2 | `r01a5f38at:flux` | flux / fake | 0.032174 | ✗ | ✓ | ✓ | ✗ | SAFE|FSD |
| 3 | `r06743f8ft:sd3_5` | sd3_5 / fake | 0.274584 | ✓ | ✓ | ✓ | ✗ | PatchCraft|SAFE|FSD |
| 4 | `r0b13d2a2t:flux` | flux / fake | 0.294667 | ✓ | ✓ | ✗ | ✗ | PatchCraft|SAFE |
| 5 | `r1cd8d9a4t:flux` | flux / fake | 0.310751 | ✗ | ✓ | ✗ | ✓ | SAFE|AIDE |
| 6 | `r17b2f789t:flux` | flux / fake | 0.027159 | ✓ | ✗ | ✗ | ✓ | PatchCraft|AIDE |

## 3. Recovery

| Tool | Recovered | Rate | Unique recovery¹ |
|---|---:|---:|---:|
| PatchCraft | 4/6 | 0.6667 | 1 |
| SAFE | 4/6 | 0.6667 | 0 |
| FSD | 2/6 | 0.3333 | 0 |
| AIDE | 2/6 | 0.3333 | 0 |

¹ Unique recovery means that tool alone is correct among PatchCraft/SAFE/FSD/AIDE for that PROBE error.

## 4. Pairwise Complementarity

| Pair | Overlap | First only | Second only | Neither |
|---|---:|---:|---:|---:|
| PatchCraft vs SAFE | 2 | 2 | 2 | 0 |
| PatchCraft vs FSD | 1 | 3 | 1 | 1 |
| PatchCraft vs AIDE | 1 | 3 | 1 | 1 |
| SAFE vs FSD | 2 | 2 | 0 | 2 |
| SAFE vs AIDE | 1 | 3 | 1 | 1 |
| FSD vs AIDE | 0 | 2 | 2 | 2 |

PatchCraft 与 SAFE 的恢复集合并不完全相同：重合 2 张，PatchCraft 独有 2 张，SAFE 独有 2 张，两者都未纠正 0 张。

## 5. Oracle

Oracle 表示组合里至少一个工具答对，是事后上界诊断，不是可部署系统性能。

| Combination | Correct / 300 | Accuracy | Gain vs PROBE | Additional rescued |
|---|---:|---:|---:|---:|
| PROBE | 294/300 | 0.9800 | +0.00 pp | 0 |
| PROBE + PatchCraft | 298/300 | 0.9933 | +1.33 pp | 4 |
| PROBE + SAFE | 298/300 | 0.9933 | +1.33 pp | 4 |
| PROBE + FSD | 296/300 | 0.9867 | +0.67 pp | 2 |
| PROBE + AIDE | 296/300 | 0.9867 | +0.67 pp | 2 |
| PROBE + PatchCraft + SAFE | 300/300 | 1.0000 | +2.00 pp | 6 |
| PROBE + PatchCraft + FSD | 299/300 | 0.9967 | +1.67 pp | 5 |
| PROBE + PatchCraft + AIDE | 299/300 | 0.9967 | +1.67 pp | 5 |
| PROBE + PatchCraft + SAFE + FSD + AIDE | 300/300 | 1.0000 | +2.00 pp | 6 |

## 6. Confidence Analysis

按固定描述性边界，near-threshold (<0.10) 0 张，moderate ([0.10, 0.30)) 4 张，high-confidence (>=0.30) 2 张。

高置信误例的正确纠正工具：
- `r01a5f38at:flux` (margin 0.4678): SAFE|FSD
- `r17b2f789t:flux` (margin 0.4728): PatchCraft|AIDE

## 7. Toolbox Decision

- PatchCraft → **CONDITIONAL KEEP (evidence-only; not an independent final verdict)**：六张中纠正 4 张；按原筛查结论仅作局部纹理证据。
- SAFE → **CONDITIONAL KEEP**：在 PROBE+PatchCraft 之外边际恢复 2 张。
- FSD → **DROP FROM MAIN TOOLBOX**：在 PROBE+PatchCraft+SAFE 之外边际恢复 0 张。
- AIDE → **DROP FROM MAIN TOOLBOX**：在 PROBE+PatchCraft+SAFE 之外边际恢复 0 张。

## 8. Answers

1. PatchCraft 和 SAFE 是否纠正同样的 4 张？否；具体交集与独有样本见上表及 pairwise CSV。
2. SAFE 在 PROBE+PatchCraft 之外额外救回 **2** 张。
3. FSD/AIDE 是否额外恢复 PatchCraft+SAFE 都未恢复的样本？FSD **0** 张，AIDE **0** 张。
4. 当前所有已有工具是否覆盖全部六个错误？**是**。按协议的四个辅助工具，仍无人纠正：无。既有 RIGID 在六张上新增纠正 0 张；既有 Provenance actionable 覆盖 0/300，因而不能补足未覆盖错误。

统计中的 `num_independent_correct_tools` 按协议计数不同辅助工具的正确输出，不代表其误差在统计意义上独立。样本独立抽样单位为来源组；六张错误只作描述性个案分析。
