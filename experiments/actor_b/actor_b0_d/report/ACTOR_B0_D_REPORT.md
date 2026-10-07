# Actor-B0-D：Evidence Sufficiency & Tool Strategy Gate

Final decision:
ACTOR_B0_D_INCONCLUSIVE

本报告给出四条件自动评价结果。方案第 8 节要求至少完成一轮真实人工复核；固定的 20 张图、四条件共 80 行目前全部未审，827 次工具调用的人工选择标签也未填。因此当前证据不足以作 PASS 或 SFT_JUSTIFIED 决策。自动指标中有需要审阅的策略信号，但不能代替人工判断。

## A. 冻结配置

- 模型：Qwen3-VL-8B-Instruct，revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b。
- B0-C canonical prompt、cards、schema、generation 合并 SHA-256：739abe138a0a40b1c21a77308565165bb309a0f45d28f1cf2d0da5354e8da1ea。
- 工具调用上限 4，Actor 步数上限 6；greedy decoding，seed 20261006，max new tokens 768；三条件使用相同模型、运行器和输入顺序。
- PROBE-MASK 使用冻结 runner 9d9fd8a8d867433d7675d5bf64ddef58b8f702c1ef5a1f1c87fb5509eefbae62。
- PROBE-DELAY 为 B0-C canonical prompt hash。TOOL-RENAME 仅使用替代名称/相应冻结 tool cards，condition prompt hash 8906bcd750c705821b5c38d76fa2897f57ff513014751a71e1d36d217dddaf57；运行器 hash 与其他新条件相同。
- 保留 raw STOP verdict 为 real/fake；只对非法 verdict 使用冻结的 same-model projection。没有增加 detector 推理、crop 生成、SFT 或 prompt 修补。
- 新 GPU 条件已结束；远端 GPU 为 0 MiB / 0%，轨迹及 runtime 均已取回，SHA-256 与远端一致。

## B. 诊断数据

- 四条件均为同一批 60 张图，20 个来源组，原样本顺序一致。四条件共 240 条轨迹。它们是 B0-C 同 cohort 的配对诊断结果，不是独立 held-out 泛化结果。
- GT 只用于离线指标；Actor 输入 manifest 只包含 sample ID、相对图像路径和图像 SHA-256。
- 类别配额为 EASY_AGREEMENT 12、PROBE_FAILURE_COMPLEMENTARY 困难代理 12、TOOL_DISAGREEMENT 16、WEAK_EVIDENCE 10、DIFFICULT_SOLVABLE 10。此 cohort 实际为 real 20、fake 40。
- 与历史 PROBE 错误图片的重叠为 0。PROBE 类是用户批准的困难代理，不是真实历史错误复现。为 Monitor 保留的 74 个来源组未参与。
- 来源组和类别定义详见 data/SELECTION_REPORT.md。

## C. 总体任务表现

所有数值只描述这个目的性抽样诊断集。Accuracy 将无效轨迹计为错误；balanced accuracy 只在有效终态中计算。Specificity 表示 real recall（fake 为正类）。

| 条件 | raw 合法终态 | 最小策略后合法 | 无效率 | Accuracy（无效计错） | 有效集 balanced accuracy | Specificity | Fake recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| FULL | 55/60 | 60/60 | 0/60 | 0.750 | 0.713 | 0.600 | 0.825 |
| PROBE-MASK | 57/60 | 60/60 | 0/60 | 0.700 | 0.650 | 0.500 | 0.800 |
| PROBE-DELAY | 52/60 | 60/60 | 0/60 | 0.783 | 0.763 | 0.700 | 0.825 |
| TOOL-RENAME | 59/60 | 59/60 | 1/60 | 0.633 | 0.627 | 0.579 | 0.675 |

PROMPT-only 条件外的最小 STOP 投影修复：MASK 3 条、DELAY 8 条；所有原本合法的 raw verdict 均保持原样。TOOL-RENAME 的一条失败未被投影掩盖：该轨迹成功调用 4 个工具、耗尽工具预算后又两次请求重复工具，均被拒绝，最终没有合法 STOP。FULL 的 5 条非法 STOP 按已冻结最小策略修复。

Accuracy 变化仅为背景描述。同一批 60 图、20 个来源组及类别不平衡限制了总体解释；这些数值不能单独决定 SFT。

## D. 工具选择行为

| 条件 | 首次选择的工具 | 成功工具调用均值/图 | 单工具 STOP |
|---|---|---:|---:|
| FULL | PROBE 28；provenance 32 | 3.15 | 0/60 |
| PROBE-MASK | local texture 48；provenance 12 | 2.98 | 0/60 |
| PROBE-DELAY | 首步被禁止的 PROBE 请求 28；local texture 28；provenance 32 | 3.23 | 0/60 |
| TOOL-RENAME | tool_alpha（映射到原 global/PROBE）60 | 3.72 | 0/59 有效轨迹 |

FULL 的 28/28 PROBE-first 轨迹均没有在 PROBE 后立即 STOP。PROBE-MASK 未出现无效终态；首选工具转向可用的 local texture/provenance。PROBE-DELAY 对 28 次首步 PROBE 请求均返回条件阻止，随后各轨迹选择其他来源；这 28 次不计 parser 失败。

工具调用没有重复成功调用。一次重复请求失败发生在 TOOL-RENAME 的终态失败轨迹中。工具调用次数本身不代表用了独立或充分的证据；最终推理忠实度仍待人审。

## E. 冲突处理

缓存工具输出按预定规则标记 36/60 张有方向冲突；定义不使用 Actor verdict。实际冲突后跟进计数如下：

| 条件 | 缓存冲突 | Actor 实际观察到冲突 | 后续调用独立工具 | 观察到冲突且仍有工具/预算可跟进 | 其中实际跟进 |
|---|---:|---:|---:|---:|---:|
| FULL | 36 | 12 | 3 | 4 | 3/4 |
| PROBE-MASK | 36 | 36 | 27 | 27 | 27/27 |
| PROBE-DELAY | 36 | 17 | 5 | 9 | 5/9 |
| TOOL-RENAME | 36 | 32 | 20 | 20 | 20/20 |

最后两列以当前条件仍可调用的工具为界；“后续独立工具”排除两种刚产生方向冲突的工具。此机会计数是对冻结轨迹的描述性核对，不另设阈值。ALL-frozen-conflicts 分母包含 Actor 尚未同时观察两种方向证据的轨迹，因而不可直接解释为“看到冲突后选择忽略”。其中 8 条 FULL、9 条 MASK、8 条 DELAY、12 条 RENAME 在观察到冲突时已没有可用独立工具或已到 4-call 上限。

## F. 证据充分性与提前 STOP

自动轨迹中四条件均没有单工具 STOP。每个有效 final output 声明的已调用 evidence sources 均可由脚本计数；FULL 平均每个 STOP 引用 4.13 种独立 evidence type，MASK 3.92，DELAY 4.23，RENAME 4.34（含原图 visual 类型）。这些是结构化引用数量，不能证明 Actor 的解释真的由引用内容支持。

过早 STOP、证据是否足够和停止时机需要查看图像、当时可用工具、完整轨迹和终态解释。固定人审尚未完成，所以这些指标目前没有数值，不能写成零问题。

## G. PROBE 捷径分析

- FULL 首次调用 PROBE 为 28/60；其中首次成功 PROBE 后立即 STOP 为 0/28。
- PROBE-MASK 的 60 条均产生合法终态，工具调用均值从 FULL 的 3.15 降到 2.98；diagnostic accuracy 下降 5.0 个百分点，不能视作崩溃。
- PROBE-DELAY 中有 28 次首步 PROBE 请求被条件阻止；随后每条轨迹均先选择其他可用工具，0 条非法终态。
- 上述结果不显示“调用一次 PROBE 就停止”的 shortcut。DELAY 下重复提出首步 PROBE 说明其起始策略可能依赖该工具；仍需和中性改名结果及人审的证据选择质量一起解释。

## H. TOOL-RENAME 稳健性

仅替换工具名后，首次选择从 FULL 的 PROBE 28/60、provenance 32/60，变为 tool_alpha（映射至原 global/PROBE）60/60。相对 FULL 的最大 first-tool share 漂移为 53.3 个百分点；最终 raw parse 从 55/60 变为 59/60，但有效终态从 60/60 降至 59/60；balanced accuracy 降 8.6 个百分点，平均成功调用增加 0.57 次/图。

这是明显的工具名/描述敏感信号，值得重点复核。该条件保留了调用必要的功能描述；因此这些变化不能单凭首选工具分布解释为工具语义完全不可识别，也不能直接推出 SFT。需要人工检查匿名名称下各次工具选择是否确实对应当时未解决的 evidence gap，并检查那条无效轨迹的行动序列。

## I. Evidence faithfulness

截至本报告，human_audit.jsonl 的 80 行里完成 0 行；evidence_sufficient、verdict_consistent、unsupported_claim、reasoning_faithful 等人工指标均为未测量。tool_selection_audit.csv 的 827 次调用也有 0 行人工标签。自动解析只统计输出中引用的来源是否出现在已成功调用列表中，不会验证语义支持、证据强度、方向归因或是否虚构观察。

请依据 evaluation/HUMAN_AUDIT_GUIDE.md 审阅固定盲审包和调用表。审计集固定覆盖 5 EASY、5 冲突、5 PROBE 困难代理、5 WEAK 样本；不要使用 GT 判断理由是否忠实。

## J. 失败分类

1. Raw schema/终态格式：FULL 5、MASK 3、DELAY 8、RENAME 1 条 raw 终态不合法。冻结的最小策略分别把 FULL/MASK/DELAY 恢复至 60/60；RENAME 的 1 条为预算耗尽后的重复调用拒绝，没有合法 STOP。
2. PROBE 起始依赖：DELAY 有 28 次首步 PROBE 请求，但全都在条件门禁后转用其他工具，无不可用工具调用。
3. 名称敏感策略：RENAME 首次工具选择集中到匿名 tool_alpha，最终性能和合法终态率较 FULL 下降。
4. 冲突跟进：机会调整后的计数显示 MASK 27/27、RENAME 20/20、FULL 3/4、DELAY 5/9 在可继续取证时选了后续独立工具。还需人审判断这些调用是否合适以及证据综合是否忠实。
5. 证据充分性、支持结论的事实依据和是否过早停止：待人工审计，不作自动错误分类。

## K. SFT gate 决策

ACTOR_B0_D_INCONCLUSIVE

方案明确要求至少一轮完整人审。当前 80 条终态审计与 827 条调用审计均为零完成，因此尚不能按预定 gate 判 PASS 或 SFT_JUSTIFIED。RENAME 的首选工具完全集中、性能下降，以及 DELAY 的首步 PROBE 请求，为需人工核实的信号；PROBE-MASK 的终态和冲突跟进表现则没有显示因隐藏 PROBE 而崩溃。此次 cohort 重用 B0-C，PROBE 类也是困难代理，结论只适用于这轮诊断。

完成固定人审后，结合行为缺陷是否跨样本重复并且结构性，再更新 gate。本轮没有训练 SFT，没有启动 Monitor 实验。若复核后判定现有 Actor 足够，下一步进入 Monitor-0 设计；若人审确认稳定策略缺陷，再列出 SFT target 并等用户批准训练方案。
