# Actor-0：Prompt-only 自主取证 Agent 实验报告

日期：2026-10-03  
状态：完成；Actor-0 评测、轨迹分析与人工审计已完成。按方案在此停止，未训练 Actor、未开展 Monitor 实验。

## 结论摘要

冻结的 Actor-0 在独立评测集上完成了 300/300 条自主轨迹，决策步骤和最终 verdict 均可解析；它能够在遇到工具分歧时继续取证，也忠实复述了观察到的工具信号。但它有明显的 PROBE 单工具捷径，遇到证据不足时偶尔提前停止，且不能消除大部分工具冲突。它不是 PROBE-DINOv2 的替代品，作为后续研究基线 **CONDITIONAL KEEP**。

| 系统 | Accuracy | Balanced accuracy | Specificity | Fake recall | 无效/未解析 | 平均工具调用 |
|---|---:|---:|---:|---:|---:|---:|
| Image-only MLLM | 0.6067 | 0.7050 | 1.000 | 0.410 | 0/300 | 0.00 |
| PROBE only | 0.9867 | 0.9875 | 0.990 | 0.985 | 0/300 | 1.00 |
| Forced all-tools | 0.9133 | 0.9275 | 0.970 | 0.885 | 19/300 | 4.00 |
| Actor-0 autonomous | 0.9500 | 0.9400 | 0.910 | 0.970 | 0/300 | 2.58 |

Accuracy 将无效输出计为错误；召回率分母包含该类所有样本。评测样本为 100 个不重叠来源组，每组含 1 张 RAISE 真图、1 张 FLUX 假图和 1 张 SD3.5 假图。图像级指标是描述性结果，来源组是抽样单位。

## 1. 数据、模型与冻结条件

- 复用当前项目的 B-Free/RAISE 数据及既有来源组清单，未另建数据副本。Dev 为 60 个来源组/180 张图；eval 为 100 个独立来源组/300 张图。两组与先前已用的 530 个来源组及彼此均不重叠，按 70/30 横幅/竖幅来源组分层；原始 PNG 字节不变。
- Dev manifest SHA-256：`b5529fc7f4abc2c0f2a279133c69258027f3a8c218199b53b1ce9c6ea92ebb84`。Eval manifest SHA-256：`fffd5736418a4cfd36b85f95b571a4347608851d607db9a5b86010f6ce1a857c`。
- 模型：`Qwen/Qwen3-VL-8B-Instruct`，模型和 processor revision 均为 `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`；bfloat16，CUDA 设备。环境为 Python 3.12.3、PyTorch 2.12.1+cu130、Transformers 4.57.4、CUDA 13.0。
- 固定生成：greedy decoding、seed 20261002、每步最多 512 新 token、最多 6 步/4 次工具调用。评测期间没有改变模型、提示词、工具卡、分数、阈值或图像预处理。eval 标签未进入 Actor 提示词或工具输入。
- 四项语义工具：`global_forensic_analyzer`=PROBE-DINOv2；`local_texture_analyzer`=PatchCraft；`complementary_forensic_analyzer`=SAFE（冻结阈值 `0.9561132788658143`）；`provenance_inspector`=c2patool + ExifTool。Provenance 缺少 C2PA/元数据时只能返回 inconclusive。RIGID 基于前一轮工具筛选结果未纳入本轮 Actor 工具集。

## 2. Prompt 调试与评测执行

1. v1 在 dev 调试中因 512-token 截断出现不完整 JSON，停止并保留原始日志。
2. v2 完成 180 张 dev，但未过冻结门槛：749 个决策回合中有效回合率 97.06%，final verdict 可解析率 95.56%，完整轨迹可解析率 92.22%。
3. v3 仅澄清结构约束：STOP 必须在同一 JSON 中给出完整字段，final verdict 只能是 real/fake，冲突以低置信度和不确定性字段表达。没有改模型、工具、阈值、分数、token 上限或预处理。v3 dev 为 180/180 条完整可解析轨迹、653/653 回合有效。冻结 prompt SHA-256：`a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`。
4. 冻结记录中 prompt 名称被 freeze 脚本硬编码为 `actor0-v1`；内容哈希与实际 v3 提示词一致，因此以 SHA-256 作为身份标识。错误模型快照路径的一次尝试在处理样本前退出，没有覆盖结果；日志已保留。
5. 独立 eval 的 image-only、forced-all、autonomous 各有 300 条记录。SSH 会话在自主轨迹约第 247 条时中断；使用同一冻结配置、同一输出目录的 resume 续跑，跳过已完成记录并补齐剩余样本。300/300 逐图文件和聚合文件均通过远端 SHA 清单核对，没有改变冻结条件或重新选择结果。

PROBE、PatchCraft、SAFE 和 Provenance 的逐图结果先于 Actor 运行保存。PatchCraft 官方流程第一次导入时暴露了三个依赖缺失问题，失败日志均保留；仅补装 `imageio==2.37.2` 与 `scikit-image==0.24.0`（cv2 已存在），随后 480/480 图完成且分数有限。PatchCraft 运行峰值显存约 3688 MiB；Provenance 在 CPU 上扫描 480 张，工具错误 0、可用来源证据 0。SAFE 使用已有独立校准阈值，没有在 eval 上调阈值。

## 3. 评测结果与推理成本

| 条件 | 正确数 | Accuracy | Balanced accuracy | Specificity | Fake recall | 平均 wall time/图 | 平均工具调用 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Image-only MLLM | 182/300 | 0.6067 | 0.7050 | 1.000 | 0.410 | 4.28 s | 0 |
| PROBE only | 296/300 | 0.9867 | 0.9875 | 0.990 | 0.985 | 复用既有逐图分数 | 1 |
| Forced all-tools | 274/300 | 0.9133 | 0.9275 | 0.970 | 0.885 | 4.78 s | 4 |
| Actor-0 autonomous | 285/300 | 0.9500 | 0.9400 | 0.910 | 0.970 | 20.90 s | 2.58 |

Actor 平均每图记录耗时 20.90 秒，中位数 21.94 秒，p95 为 33.62 秒；300 张累计样本记录耗时 6,270.86 秒。时间包含多轮 Qwen 调用，工具调用数只是成本代理，并不等于统一的算力成本。Forced-all 的 19 个未解析终结输出按方案记错；没有对 eval 输出做格式修复或二次推理。

PROBE 在 300 张中错 4 张，Actor 在这 4 张中仅纠正 1 张、仍错 3 张；追加工具实际挽回 1 张，另有 1 张在 global 结果后过早停止。Actor 的 fake recall 比 PROBE 高 1.5 个百分点，但 specificity 低 8 个百分点、accuracy 低 3.67 个百分点。其总体改进主要相对弱的 image-only/forced-all 条件，未超过 PROBE 基准。

## 4. 必答分析

### A. Actor 能不能稳定自主调用工具？

**PARTIALLY**。形式稳定性良好：eval 300/300 条 Actor 轨迹均有可解析的最终 verdict，决策回合解析率 100%，无非法工具请求或强制终止。行为稳定性不足：37.33% 的样本只调用 global 工具；分层人工审计中，20/50 例有工具选择/证据充分性/停止理由问题。该 50 例是按错误、冲突、调用数等分层抽样，不能把 40% 当成全 eval 的错误率。

### B. Actor 是否形成 PROBE/global shortcut？

是。global-only stop rate 为 **112/300（37.33%）**。287 个高 strength global 观察中，39.02% 在 global 后停止；13 个中/低 strength 观察全部继续调用至少一个工具。工具 strength 是固定原始分数的描述性极值区间，不是校准概率。人工审计将单一、未校准 global 分数后直接高置信停止列为过程风险。

### C. Actor 是否 tool spam？

没有出现无效或重复工具请求；平均调用 **2.58**、中位数 3、四工具全调比例 **36.0%**。自动行为规则标记 8/300 个潜在过度搜索例（2.67%）。这不是普遍工具 spam，但全调成本仍高于自适应调用所需，且单工具停止形成另一端的证据不足风险。

### D. Actor 是否正确处理冲突？

检测到 **128** 个冲突样本，**126/128（98.44%）** 在首个冲突后继续取证。所有 128/128 最终仍以未解决冲突停止；这通常伴随 low/moderate confidence 与保留不确定性，说明 Actor 能暴露冲突，但工具不能解决冲突。Provenance 在本数据没有可用元数据，不能用来裁决真假。人工审计中，已观察到的冲突均在 STOP 前被识别；另有 4 个分层样本在仍有相关工具可用时提前停止，细节见审计表。

### E. Actor 是否正确理解工具结果？

自动语义检查在 1,644 条工具提及中标记 **0 个信号方向错误**；50/50 人工审计的结构化证据摘要均与观测的工具名、signal 和 score 一致。该自动检查是文本模式审计，不是完整自然语言理解评测。另有 **6/169（3.55%）** 次 Provenance inconclusive 后被 Actor 不当用作证据的情况，说明“缺少元数据不等于 fake”仍需加强。

### F. Actor 的自主策略是否优于简单 baselines？

| Baseline/策略 | Accuracy | Balanced accuracy | Fake recall | Specificity | 平均工具调用 |
|---|---:|---:|---:|---:|---:|
| Image-only MLLM | 0.6067 | 0.7050 | 0.410 | 1.000 | 0 |
| PROBE only | **0.9867** | **0.9875** | 0.985 | **0.990** | 1 |
| Forced all-tools | 0.9133 | 0.9275 | 0.885 | 0.970 | 4 |
| Actor-0 autonomous | 0.9500 | 0.9400 | **0.970** | 0.910 | 2.58 |

Actor 明显强于 image-only，但弱于 PROBE 和 forced-all 的 balanced accuracy；forced-all 还存在 19 个格式无效输出。Actor 用更少工具达成 95% accuracy，但无法证明其自主路由优于 PROBE-only；它提高假图召回的同时引入更多真图误报，且与 PROBE 的错误互补性很弱。

### G. Actor 最主要的 failure modes

1. **单一 global 信号后高置信停止**：112/300 条轨迹只调用 PROBE；分层审计中单一 global 例普遍没有独立佐证，却将未校准的原始分数用于高置信结论。
2. **已知冲突下仍遗漏相关工具**：审计例 `r1b61c7b1t:raise`、`r1ef15cb3t:raise`、`r0cea5432t:flux`、`r170b020bt:raise` 在冲突未解时分别有 Provenance、SAFE 或 Provenance 可继续调用，却已停止。
3. **来源元数据缺失的误用**：6 个 Provenance inconclusive 案例被当成真假证据；正确行为应保持 inconclusive。
4. **无法解决专家冲突**：128 个冲突案例全部带着未解决分歧停止。Actor 能记录分歧，但没有证据表明它能推断哪个检测器在当前样本上更可靠。

### H. 是否需要 SFT？

**SFT OPTIONAL**。v3 的结构澄清已使输出格式达到 100%，所以不需要为修复 JSON 解析而训练。若后续目标要求可靠调度，应把单工具停止、停止时置信度和 Provenance 缺失的处理作为候选训练行为，并用新的独立验证流程评估；本轮没有训练 Actor，也没有把 SFT 作为已验证的解决方案。

## 5. 工具去留与 PROBE 互补性

Actor-0 继续作为受限研究基线 **CONDITIONAL KEEP**，PROBE 保持主判别器 **KEEP**。候选工具的独立筛选结论沿用已完成的[异构取证工具筛选报告](../toolbox_screening/REPORT.md)：

| 工具 | 当前决策 | 已观察结果与角色 |
|---|---|---|
| PROBE-DINOv2 | **KEEP** | 独立筛选集 accuracy 0.980 / balanced accuracy 0.985；Actor eval 为 0.9867 / 0.9875。主判别器。 |
| PatchCraft | **CONDITIONAL KEEP** | 独立筛选集 accuracy 0.600、balanced accuracy 0.4775、AUC 0.4911；虽纠正 4/6 个 PROBE 错例，但真图假阳性很高。只作为局部纹理补充信号。 |
| RIGID | **DROP** | 独立筛选集 accuracy 0.3533、balanced accuracy 0.4975、AUC 0.4496；未纠正任何 PROBE 错例，不进入 Actor 工具集。 |
| Provenance Inspector | **CONDITIONAL KEEP** | 独立筛选集及本轮 Actor 数据均无 actionable C2PA/EXIF/XMP/IPTC 证据；只在出现可验证来源凭据时提供非像素证据。缺失元数据必须保持 inconclusive。 |
| SAFE | **CONDITIONAL KEEP** | 仅复用既有独立校准阈值和分数，没有在本轮重新筛选。作为 PatchCraft 之外的 learned complementary signal。 |

在 Actor 使用的四个 PROBE 错例中，额外工具仅纠正 1 张。因此，即使 PatchCraft 在此前六错互补性精查中具有不同错误，也不能据此认为当前 Actor 已能稳定把互补工具转化为 PROBE 错例恢复。

## 6. 限制与可复现文件

- 本次 eval 只有 100 个来源组、两类生成器假图和 RAISE 真图；指标不代表其他相机来源、生成器或后处理链。Provenance 覆盖为零，不能评估 metadata-present 案例的裁决效用。
- 置信区间与显著性推断未作为主要分析；50 例人工审计按行为类别分层，不用于估计错误发生率。结论也不依赖手工复核后的测试标签来调参。
- v3 freeze 记录的名称标签有硬编码错误，冻结哈希和 eval runtime 的 prompt SHA 一致；评测会话中断后通过同配置续跑，所有逐图和聚合文件哈希与远端清单一致。

主要输出：

- [冻结数据、配置与工具卡](data/)；[v3 frozen prompt](config/system_prompt.txt)；[prompt SHA-256](config/prompt_sha256.txt)。
- [最终指标](analysis/final_metrics.json)、[工具使用与行为指标](analysis/tool_usage_metrics.json)、[逐图预测](analysis/system_predictions.csv)。
- [人工审计表](analysis/qualitative_audit.csv)、[审计规则](analysis/qualitative_audit_review/review_protocol.md)、[50 例证据包](analysis/qualitative_audit_review/evidence_bundle.md)、[接触表目录](analysis/qualitative_audit_review/)。
- [逐图 Actor 轨迹](../../runs/actor0-bfree-20261002/trajectories/trajectories.jsonl)、[image-only 输出](../../runs/actor0-bfree-20261002/baselines/image_only_evaluation.jsonl)、[forced-all 输出](../../runs/actor0-bfree-20261002/baselines/forced_all_evaluation.jsonl)。
- [PROBE/PatchCraft/SAFE/Provenance raw 分数、日志、逐图 SHA 清单及远端传输核验](../../runs/actor0-bfree-20261002/)。
- [Actor-0 README](README.md)；此前候选工具的[筛选报告](../toolbox_screening/REPORT.md)和[PROBE 六错互补性分析](../toolbox_screening/PROBE_FAILURE_COMPLEMENTARITY.md)。
