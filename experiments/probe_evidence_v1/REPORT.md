# PROBE Evidence-Only v1 实验报告

**日期：2026-10-06**  
**结论：PASS（Evidence v1 工程与证据完整性通过）**

## 结论摘要

冻结的 PROBE-DINOv2 现在可同时保留内部 classifier audit，并向后续 Actor 提供不含分类结论的 patch representation evidence。全部 300 张 eval 成功处理，官方分类分支与旧结果逐项完全一致；100 张独立冻结的 RAISE 参考图构成 600 patch bank；300 份 JSON 和 300 份文本 Evidence Card 均无禁用结论字段。60/60 个 crop 像素重建一致。完整重复运行后，400 份特征、300 张的 top-3 区域排序和整图统计完全相同。

本阶段没有运行 Actor、SFT、Monitor 或 Evidence v2。按计划停止于 Evidence v1 报告。

## A. Evidence 分支是否保持原 PROBE baseline？

通过。Stage A 按冻结分数 CSV 的样本顺序运行 300 张 eval：

- 样本顺序：300/300 一致。
- 分类标签：300/300 一致。
- 最大 image probability 绝对误差：`0.0`（要求 `<1e-5`）。
- patch 数：100 张各 6 个，200 张各 9 个。
- 官方 patch 输入生成器与新实现抽查同一图像，patch tensor 形状均为 `(6, 3, 336, 336)`，逐元素相同，最大差异为 0。

classifier audit（patch logits、image logit、概率、预测）单独保存于 `audit/`，不写入 Actor-facing evidence 文件。

## B. Authentic-reference deviation 是否稳定？

- 参考集：更早冻结的 `stage1-safe-independent-20260929` calibration split 中 100 张 RAISE 真图。Actor-0 清单选择脚本已排除所有旧来源组。
- 与 Actor-0 dev 的 60 个来源组、eval 的 100 个来源组交集均为 0。
- Reference bank：600 个 patch，1024 维 L2-normalized CLS features。
- 固定 cosine distance、`k=20`。计算 reference patch 的 calibration distance 时排除了所有同来源组参考 patch。
- 600 个 source-group-excluded calibration distance：min `0.1515`，mean `0.2709`，median `0.2499`，p95 `0.4390`，max `0.5314`。

## C. Eval representation deviation 描述统计

固定门槛为 calibration real patch 距离分布的第 95 百分位。以下统计在所有 evidence 输出冻结后计算，仅作分层描述，没有据此改参数。

| 组别 | 图数 | max deviation percentile 均值/中位数 | atypical fraction 均值/中位数 |
| --- | ---: | ---: | ---: |
| RAISE | 100 | 75.87 / 80.00 | 0.057 / 0.000 |
| FLUX | 100 | 99.99 / 100.00 | 0.902 / 1.000 |
| SD3.5 | 100 | 100.00 / 100.00 | 0.964 / 1.000 |

高 percentile 是相对当前真实参考集表征距离的位置，不是假图概率。部分 FLUX/SD3.5 percentile 在 100 饱和；观察到这一点后没有修改门槛或重选参考集。

## D. 空间结构

| 组别 | none | isolated | clustered | dispersed |
| --- | ---: | ---: | ---: | ---: |
| RAISE | 79 | 15 | 6 | 0 |
| FLUX | 0 | 1 | 99 | 0 |
| SD3.5 | 0 | 0 | 100 | 0 |

图块使用四邻接；`clustered` 定义为最大连通块至少 2 个 patch，且占异常 patch 总数至少一半。以上仅是被冻结评估集上的类别条件描述，不能解释为真假判断或跨域表现。

## E. Top regions 与 crops

- 每张 eval 生成 top-3 regions、patch map 数据、JSON card、文本 card 和对应 crop。
- 20 张固定种子随机样本的 60 个 crop，逐像素对照 `processed image + bbox`，60/60 完全一致。
- 30 张固定种子的定性 audit（每组 10 张）均查看原图和 top-3 crops；另外完整检查了 4 个 classifier 错例的 deviation map。
- 未发现 bbox 错位、patch 顺序错误或 padding/crop 对不上。少数 crop 覆盖天空、水面、草地、边缘或画框等场景区域；偏离不等于物理伪造痕迹。
- 重复运行中 400/400 feature files 最大绝对差为 `0.0`；300/300 top-3 patch 排序一致，百分位在 `1e-6` 内，整图统计完全相同。

定性记录见 [qualitative audit](analysis/qualitative_audit.md)；30 张接触表和错误例视觉图在 `visual_audit/`。

## F. PROBE 原始四张误例

| 样本 | 冻结 classifier 错误 | atypical fraction | 空间模式 | 视觉摘要 |
| --- | --- | ---: | --- | --- |
| `r0d0ff43at:raise` | 输出 fake | 0.500 (3/6) | isolated | sepia 雕塑图，三个分离区域偏离较高 |
| `r000da54ft:flux` | 输出 real | 0.556 (5/9) | clustered | 樱花近景与草地/球场区域广泛偏离 |
| `r0cea5432t:flux` | 输出 real | 0.889 (8/9) | clustered | 水面、天鹅与倒影区域广泛偏离 |
| `r1882b6e6t:flux` | 输出 real | 1.000 (9/9) | clustered | 画框、画面天空、山体与建筑均偏离 |

三个 FLUX 错例并非由一个极端 patch 单独拉动；真实 RAISE 错例同样出现了三个高偏离 patch。Neutral deviation 可提供进一步核查的理由，但不足以单独区分图像来源或决定下一工具。逐例回答见 [PROBE_FAILURE_EVIDENCE_ANALYSIS.md](analysis/PROBE_FAILURE_EVIDENCE_ANALYSIS.md)。

## G. Actor-facing conclusion leakage

为全部 300 份 JSON 和 300 份文本卡搜索了 `real`、`fake`、`probability`、`verdict`、`prediction`、`classifier_score`、`patch_logits` 和 `image_logit`：命中 **0**。Classifier 标签、概率与 logits 仅存在 `audit/` 内部文件。

## H. 是否值得进入 Evidence v2？

**PASS：值得把本 v1 作为后续独立方案的基础。** 它达成了本轮目标：稳定、可定位、可复算、无结论泄漏的 representation evidence。评测分层结果显示参考域外 patch 较多，但定性检查也发现真实罕见内容会出现高偏离，因此本证据不能替代 classifier 或其他专家。Actor 效用尚未测试；本轮不启动 Actor 或 v2。

## 运行环境与复现记录

- Instance: `autodl-container-40dd41ad1f-569df20a`，NVIDIA GeForce RTX 4090 24,564 MiB；driver `595.71.05`。
- Python 3.12.3；PyTorch `2.12.1+cu130`；torchvision `0.27.1+cu130`；Transformers `4.50.3`；NumPy `2.5.3`；Pillow `12.2.0`；PyTorch CUDA runtime `13.0`。
- PROBE checkpoint SHA-256、数据 manifests、参数与迁移核验见 `config/` 和 [MIGRATION.md](MIGRATION.md)。
- 首轮及重复运行日志在服务器 `/root/autodl-tmp/probe-evidence-v1/logs/`。任务完成时无实验进程，GPU 显存回到 1 MiB。

## 输出位置

完整逐图输出已从 AutoDL 回传至本地 [`results/output/`](results/output/)，包含 `audit/`、`work/`、`reference_bank/`、`evidence/`、`analysis/`、`config/`。原始归档为 [`probe_evidence_v1_output.tar`](results/probe_evidence_v1_output.tar)，SHA-256 为 `9a41d831ca614acbed92d704fb19a69cc0b316c111d4a2a434c4c638f4af5369`；回传前已与服务器 SHA-256 核对一致，解压后计数核验通过。服务器原始输出仍位于 `/root/autodl-tmp/probe-evidence-v1/output/`，日志在 `/root/autodl-tmp/probe-evidence-v1/logs/`。本地 `experiments/probe_evidence_v1/` 同时保存实现脚本、冻结参数、manifest、报告和视觉审计材料。
