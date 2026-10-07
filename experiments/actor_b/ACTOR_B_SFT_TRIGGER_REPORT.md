# Actor-B1 SFT 触发报告（2026-10-07）

**状态：`ACTOR_B1_SFT_REQUIRED`。本报告仅触发后续方案讨论，不启动训练。** 依据用户批准的[决策规则](../../docs/ACTOR_B_SCHEMA_HELDOUT_PLAN.md)，held-out `parse_success` 必须至少 98%；实际为 55/60（91.67%）。5 图在有限格式重试后仍没有合法 `real` / `fake` STOP，`forced_or_missing_final=5`。这已超出冻结允许的失败数。

## 未满足的编排要求

合法工具请求 189/189，平均 3.15 次/图，所有 60 图至少调用 2 次工具，0 重复，提前停止启发式 5/60（8.3%）。主要失效点是轨迹无法稳定结束，而不是单工具捷径、工具调用越界或大规模过早停止。按现有评价定义，`multi_step_completion_rate=55/60`（91.67%），其余 5 图也完成多步但没有合法终态。

## 失败比例与典型轨迹

5 条失败均发生在 STOP：3 条的两次候选均为 `inconclusive`，1 条两次均缺失 verdict，1 条在缺失与 `inconclusive` 间变化。parser 拒绝这些输出，未根据置信度、工具分数或真值标签补判。它们已完成 3–4 次工具调用；其中 2 图已观察到局部纹理与互补工具相反的信号，缺少可供 Monitor 使用的合法冲突后终态。60 图共有 26 次原始格式错误，另外一些可在有限重试中恢复。

## Schema 修复为何未消除问题

原 schema 已允许 `final_confidence=null`，parser 本轮只对齐此字段并继续强制 `STOP final_verdict ∈ {real,fake}`。原 30 图回归由 28/30 合法终态提升至 30/30，且 30/30 工具序列与旧版完全一致。曾尝试条件式 schema 文本，但前 16 图已出现终态与重复调用退化，随即中止并恢复原 schema；详见[中止记录](baseline_b0_schema_fixed/SCHEMA_CANDIDATE_ABORTED.md)。held-out 在恢复后的同一 reasoning prompt、工具和生成参数下仍有 5/60 终态失败。现有 parser 和一次有限格式重试不足以稳定满足协议。

## 为什么进入 SFT 分支

按本轮预定门槛，Actor-B0 不能冻结为固定轨迹生成器。`ACTOR_B1_SFT_REQUIRED` 表示需要提出并审批下一阶段的轨迹级协议学习方案；它不证明 SFT 是唯一可能的工程手段，也不授权立即训练。若要比较严格约束解码等其他纯工程手段，须先明确新实验设计、额外用卡与冻结口径，不能事后改写这次 held-out 结果。PROBE 归因错误、最终准确率和解释文风没有被用作 SFT 触发条件。
