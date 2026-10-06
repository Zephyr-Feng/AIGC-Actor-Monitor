# 异构取证工具筛选实验报告

日期：2026-10-02  
状态：完成；按本报告决策停止扩展实验。

## 1. 实验设置

复用既有冻结测试集和 PROBE 结果，没有重新抽取或重生成图像。测试集包含 100 个来源组、300 张 PNG：RAISE 真图 100 张、FLUX 假图 100 张、SD3.5 假图 100 张。冻结清单 SHA-256 为 `61d9455417f5d388edd663ff8497c641db58e3ee3349fda94e64c01b77b2d465`。逐图输入哈希核验通过。

测试标签只在所有推理结束后用于描述性评估、错误互补和 oracle 上界分析；没有用测试标签选择模型、阈值、预处理或超参数。PROBE 采用已冻结的分数和 `score > 0.5` 决策。PatchCraft 使用官方固定 `sigmoid score > 0.5`。RIGID 没有可直接迁移的固定阈值，因此从此前未使用且与测试组不重叠的 30 个来源组（90 张图，seed `20261002`）选择阈值；校准 manifest SHA-256 为 `6b986d1bc1cb88188c40e3c289e1e77830b6278755d1d12bcb43bb5f793822e0`，最终相似度阈值为 `0.9698531627655029`。

## 2. 官方实现与运行

- **PROBE-DINOv2**：复用既有 300 行逐图结果，没有重跑。
- **PatchCraft**：使用作者 ModelScope 测试代码和 `RPTC.pth`，源修订 `bbbce9dfb36d86c36fc49585d2e24962644f296c`，checkpoint SHA-256 `c1c9612cc47215d7c4cbdc5ddff52a4312519d697fd0830ce478f63f58e733fd`。保持 seed 42、官方默认参数、官方 patch 预处理和 sigmoid 分数；先完成每生成器 5 张的 sanity，再推理 300 张。两次运行均无非有限分数。
- **RIGID**：使用 [IBM/RIGID](https://github.com/IBM/RIGID) 官方实现设置，源修订 `55af3cc2dc17f1f47aaba4720195eaca10226ca4`；使用 [DINOv2](https://github.com/facebookresearch/dinov2) ViT-L/14 官方仓库修订 `7764ea0f912e53c92e82eb78a2a1631e92725fc8` 和官方 checkpoint（SHA-256 `d5383ea8f4877b2472eb973e0fd72d557c7da5d3611bd527ceeb1d7162cbf428`）。沿用 224×224 resize、ImageNet normalization、normalized tensor 中 λ=0.05 的一次高斯扰动和原图/扰动图特征余弦相似度；低相似度表示更像合成图。90 张校准图和 300 张测试图均无非有限分数。
- **Provenance Inspector**：使用 [c2patool 0.28.1](https://github.com/contentauth/c2patool) 和 [ExifTool 13.59](https://exiftool.org/) 检查 C2PA、EXIF、XMP、IPTC 与 PNG 元数据。c2patool 官方 release archive SHA-256 为 `66f6fadff747a6f22e7473663dd5b35a358ddc9f43eadc8993414e1bae98de61`。该 Linux 包需要 glibc 2.39，而克隆实例系统是 Ubuntu 22.04 / glibc 2.35；从 [Ubuntu Noble libc6 官方包](https://packages.ubuntu.com/noble/libc6) 解包 glibc 2.39 到实验专用目录并通过 loader 启动，没有替换系统 libc。包 SHA-256 为 `ff5557d99b51f761c4b7c92368b9cc45565eda17df9bf9eb4b134d09825008be`。官方 C.jpg 样例解析出一个 manifest，状态为签名证书未受信任；该样例仅验证解析链路，没有作为真实来源证据。正式数据扫描 300/300，无工具错误。c2patool 对无凭据文件返回 `No claim found`，按正常“没有 manifest”记录，不计为工具失败。

运行环境、权重来源、逐图 raw 输出和失败尝试均保存在 `logs/`、各工具 `raw_outputs/` 或 `raw/` 目录中。此前 c2patool/glibc 不兼容的 metadata-only 结果留在 `provenance/c2pa_unavailable_attempt/`，正式结果使用兼容 wrapper 重跑生成。

## 3. 整体结果

所有指标均为图像级描述性结果；样本的独立抽样单位是 100 个来源组。`AP` 为 average precision。

| 工具 | Accuracy | Balanced accuracy | ROC-AUC | AP |
|---|---:|---:|---:|---:|
| PROBE-DINOv2 | 0.980 | 0.985 | 0.9998 | 0.9999 |
| PatchCraft | 0.600 | 0.4775 | 0.4911 | 0.6658 |
| RIGID | 0.3533 | 0.4975 | 0.4496 | 0.6538 |

PatchCraft 的固定官方阈值在 100 张真图上产生 89 个假阳性，虽检出 169/200 张假图，但整体 balanced accuracy 和 AUC 均接近随机。分生成器配对的 balanced accuracy 为 RAISE–FLUX 0.425、RAISE–SD3.5 0.530；错误主要来自真图假阳性。

RIGID 的独立校准 balanced accuracy 为 0.5083。冻结测试集 balanced accuracy 为 0.4975、ROC-AUC 为 0.4496；配对 balanced accuracy 为 RAISE–FLUX 0.520、RAISE–SD3.5 0.475。官方特征稳定性分数在本数据上的阈值方向没有形成可用区分。

| 配对组 | 工具 | Accuracy | Balanced accuracy | ROC-AUC | AP |
|---|---|---:|---:|---:|---:|
| RAISE–FLUX | PROBE | 0.975 | 0.975 | 0.9996 | 0.9996 |
| RAISE–FLUX | PatchCraft | 0.425 | 0.425 | 0.3841 | 0.4294 |
| RAISE–FLUX | RIGID | 0.520 | 0.520 | 0.5698 | 0.5749 |
| RAISE–SD3.5 | PROBE | 0.995 | 0.995 | 1.0000 | 1.0000 |
| RAISE–SD3.5 | PatchCraft | 0.530 | 0.530 | 0.5980 | 0.5735 |
| RAISE–SD3.5 | RIGID | 0.475 | 0.475 | 0.3294 | 0.4056 |

## 4. 与 PROBE 的互补性

PROBE 在 300 张图中错 6 张。PatchCraft 在这 6 张里纠正 4 张（66.7%）；PROBE 与 PatchCraft 错误指示相关系数为 −0.019，预测不一致 122/300 张。尽管固定阈值单独表现差，局部纹理输出包含不同信号；PROBE + PatchCraft 的 oracle 上界为 298/300（相对 PROBE +4 张，+1.33 个百分点）。这只是“至少一个工具答对”的诊断上界，不能作为可部署组合性能。

RIGID 纠正 0/6 张 PROBE 错误；PROBE + RIGID 的 oracle 上界仍为 294/300。RIGID 的输出在本数据上没有提供有效错误恢复。

复用既有 SAFE 冻结分数与独立校准阈值（阈值 `0.9561132788658143`，未重跑或重调），SAFE 同样纠正了 4/6 张 PROBE 错误。SAFE 与 PatchCraft 的恢复数相同，但本轮不重新研究 SAFE。

## 5. Provenance 覆盖

测试集的 300 张图中，c2patool 均未发现 C2PA manifest；ExifTool 对 EXIF、XMP、IPTC、相机型号、软件标记的覆盖均为 0/300。所有逐图输出因此为 inconclusive，actionable 证据为 0/300。缺少 metadata 不能推断真实或合成来源。官方 C2PA 正向样例证明读取路径可用，但其签名证书不受信任，不能视为 trusted provenance。

## 6. 成本与错误

| 工具 | 测试图片数 | 推理/扫描时间 | 每图时间 | 峰值显存 | 工具错误 |
|---|---:|---:|---:|---:|---:|
| PatchCraft | 300 | 46.15 s | 0.154 s | 3689 MiB | 0 |
| RIGID | 300 | 12.60 s | 0.042 s | 4698 MiB | 0 |
| Provenance Inspector | 300 | 42.07 s | 0.140 s | CPU | 0 |

## 7. 最终工具组合决策

| 工具 | 决策 | 后续角色 |
|---|---|---|
| PROBE-DINOv2 | **KEEP** | 强全局取证基准，当前主判别器。 |
| PatchCraft | **CONDITIONAL** | 可作为局部纹理/残差信号提示；不得独立输出真假结论。若作为后续证据工具，需显式处理其极高真图假阳性。 |
| RIGID | **DROP** | 本次冻结域上区分度近随机且未纠正 PROBE 错误，不进入当前 toolbox。 |
| Provenance Inspector | **CONDITIONAL** | 仅在存在 C2PA 或可解释来源元数据时提供非像素证据；无 metadata 必须保持 inconclusive。 |
| SAFE（既有结果） | **CONDITIONAL** | 仅复用冻结分数作为可选 learned signal；本轮未重跑，后续是否纳入需与 PatchCraft 按相同准入标准比较。 |

## 8. 结果文件

- 逐图分数：[`PatchCraft predictions.csv`](patchcraft/predictions.csv)、[`RIGID predictions.csv`](rigid/predictions.csv)、[`Provenance results.csv`](provenance/provenance_results.csv)
- 对齐与互补性：[`aligned_predictions.csv`](analysis/aligned_predictions.csv)、[`metrics.json`](analysis/metrics.json)、[`metrics_by_generator.csv`](analysis/metrics_by_generator.csv)、[`error_overlap.csv`](analysis/error_overlap.csv)、[`probe_failure_analysis.csv`](analysis/probe_failure_analysis.csv)、[`complementarity.json`](analysis/complementarity.json)
- 原始逐图报告：[`PatchCraft raw`](patchcraft/raw_outputs/full_raw_scores.jsonl)、[`RIGID raw`](rigid/raw_outputs/full_raw_scores.jsonl)、[`Provenance raw`](provenance/raw/provenance_raw.jsonl)
- RIGID 阈值冻结：[`calibration_threshold.json`](rigid/calibration_threshold.json)，校准逐图分数在 [`calibration_predictions.csv`](rigid/calibration_predictions.csv)
- 环境和日志：[`logs/`](logs/)

限制：本次只有 100 个来源组；PROBE 在当前测试集的 accuracy 为 0.98，错误分析只覆盖 6 张误例；Provenance 数据覆盖为零。因此 PatchCraft/Provenance 决策是有约束的条件保留，不能据此外推到具有真实相机来源信息或其他生成器的图像。
