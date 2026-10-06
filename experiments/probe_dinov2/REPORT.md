# PROBE-DINOv2 在 B-Free 上的四专家对照结果

**日期：** 2026-10-01  
**状态：** 评分与分析完成  
**结论范围：** 对冻结的 100 个 B-Free 来源组做一次描述性评估；不据此单独冻结专家栈或进入 Stage 2。

## 实验与样本

按预先冻结的种子 `20261001`，从此前未用的 600 个来源组中分层抽取 70 个横幅组、30 个竖幅组。每组含一张 RAISE 真图、一张 FLUX 假图和一张 SD3.5 假图，共 300 张原始 PNG。此前 Stage 1 的 200 组和 SAFE 独立校准/筛查的 200 组均排除；本次未动用其余 500 组。清单 SHA-256 为 `61d9455417f5d388edd663ff8497c641db58e3ee3349fda94e64c01b77b2d465`。

PROBE 使用公开 DINOv2-with-registers-large 检测器，严格加载 442 个 checkpoint 键；保留官方 336×336 非重叠滑窗、ImageNet 归一化、patch 平均 logit 和 sigmoid 分数流程。PROBE 主阈值固定为 `score > 0.5`。FSD、AIDE 与 SAFE 在同一批图上重新评分；采用先前互不重叠校准集冻结的阈值/校准，没有在本测试集调参。

## 总体结果

| 专家 | Accuracy | Balanced accuracy | ROC AUC | AP | Specificity | 假图召回 |
|---|---:|---:|---:|---:|---:|---:|
| PROBE-DINOv2 | **0.980** | **0.985** | **0.9998** | **0.9999** | **1.000** | **0.970** |
| FSD（既有校准） | 0.520 | 0.583 | 0.6903 | 0.7300 | 0.770 | 0.395 |
| AIDE（既有校准） | 0.650 | 0.580 | 0.5720 | 0.7087 | 0.370 | 0.790 |
| SAFE（既有阈值） | 0.440 | 0.543 | 0.6775 | 0.7495 | 0.850 | 0.235 |

样本中真/假比例为 1:2，因此 Accuracy 和 AP 受类别比例影响；balanced accuracy、specificity、假图召回及完整混淆矩阵一并给出。PROBE 的混淆矩阵为 TN=100、FP=0、FN=6、TP=194。其余专家的固定操作点详见上表及 `results/analysis/metrics.json`。

### 按生成器拆分

每个对照均包含 100 张 RAISE 真图和 100 张对应生成器假图。

| 专家 | RAISE vs FLUX：Accuracy / AUC / AP / FLUX 召回 | RAISE vs SD3.5：Accuracy / AUC / AP / SD3.5 召回 |
|---|---:|---:|
| PROBE-DINOv2 | **0.975 / 0.9996 / 0.9996 / 0.950** | **0.995 / 1.000 / 1.000 / 0.990** |
| FSD（既有校准） | 0.555 / 0.6725 / 0.5717 / 0.340 | 0.610 / 0.7081 / 0.6000 / 0.450 |
| AIDE（既有校准） | 0.575 / 0.4842 / 0.4658 / 0.780 | 0.585 / 0.6598 / 0.6371 / 0.800 |
| SAFE（既有阈值） | 0.540 / 0.7174 / 0.6281 / 0.230 | 0.545 / 0.6376 / 0.5848 / 0.240 |

逐生成器的完整指标见 [`metrics_by_generator.csv`](results/analysis/metrics_by_generator.csv)。

## 错误互补性与组合诊断

PROBE 有 6 张错判。仅作条件描述：在这 6 张上，FSD 和 AIDE 各纠正 2 张，SAFE 纠正 4 张。三位旧专家至少一位判对 285/300（95.0%）；四专家至少一位判对 299/300（99.67%）。这个 oracle 上限假定事后知道每张图的真值，不能作为可部署性能。

预先定义的四专家多数票（2:2 平票交给 PROBE）accuracy 为 0.933、balanced accuracy 为 0.950，specificity 为 1.000、假图召回为 0.900，低于 PROBE 单独的固定阈值结果。简单多数投票没有显示出增益。PROBE 在本测试集上搜索得到的诊断阈值 `0.274584` 对应 accuracy 0.993、balanced accuracy 0.995；由于用测试标签选阈值，该数字**不是有效测试结果**，只表明分数排序接近完美。

## 解释与边界

在本次冻结样本和官方阈值下，PROBE 明显优于 FSD、AIDE、SAFE，且错误有一定互补性；但多数票没有提升。该结果可支持把 PROBE 作为独立候选进入后续讨论，不能证明它已适合部署，也不能证明加入 Monitor 或改动 `E_base` 后会有收益。

统计单位是 100 个来源组，而表格报告的是 300 张图的描述性指标；未做来源组级置信区间或显著性检验。因此不能把 300 张当作完全独立样本，也不应过度解读极高的 AUC/AP。类别构成为每组三张中的一真两假，整体 AP 依赖该抽样比例。

PROBE 论文在 AIGI-Quality-Paradox 中报告了 FLUX 和 SD3；所以本实验检验的是向不同 B-Free 数据构造、RAISE 真图来源、配对来源组和 SD3.5 输出的迁移，**不是对 FLUX/SD3 生成器家族的全新未见泛化测试**。训练数据与本次图像是否存在逐图重叠，当前没有独立审计证据。新结果也不替代此前 Stage 1/SAFE 的原筛查结论；新旧实验的样本和问题不同。

## 复现文件

- 实验设计、来源、预处理和固定阈值：[README.md](README.md)
- 300 张冻结清单：[dataset_manifest.jsonl](dataset_manifest.jsonl)
- 逐图 PROBE 分数：[results/probe_predictions.csv](results/probe_predictions.csv)
- 四专家对齐分数：[results/analysis/aligned_predictions.csv](results/analysis/aligned_predictions.csv)
- 汇总指标、阈值与 oracle/投票诊断：[results/analysis/metrics.json](results/analysis/metrics.json)
- 逐生成器指标：[results/analysis/metrics_by_generator.csv](results/analysis/metrics_by_generator.csv)
- 错误重叠：[results/analysis/error_overlap.csv](results/analysis/error_overlap.csv)
- 运行日志：[results/logs](results/logs/)
- 环境与权重摘要：[environment.txt](environment.txt)、[checkpoint_info.txt](checkpoint_info.txt)

没有更改 MVP 主方案、Actor、`E_base`/`E_extra` 或 Stage 2 状态；没有在本轮运行测试套件。

## 文献与数据来源

- Cao et al., “Where Detectors Fail: Probing Generative Space for Generalizable AI-Generated Image Detection,” ICML 2026. [PMLR](https://proceedings.mlr.press/v306/cao26s.html), [official code](https://github.com/Amamiya-C/PROBE-AIGI-Detection).
- [B-Free extended Synthbuster](https://github.com/grip-unina/B-Free); [RAISE dataset](https://loki.disi.unitn.it/RAISE/). 数据按 B-Free/RAISE 的非商业及署名条件用于信息性研究，原有 notices 保留。
