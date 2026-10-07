# Actor-B Schema / Held-out 冻结决策报告（2026-10-07）

执行依据：[用户批准的方案](../../docs/ACTOR_B_SCHEMA_HELDOUT_PLAN.md)。本轮保留原始 30 图结果、中止的 schema 候选、独立 30 图回归和独立 60 图 held-out；不覆盖原轨迹。所有原始逐图输入、重试和轨迹只保存在本地及本次获授权的 AutoDL 实例，不上传 GitHub。

## 1. Schema Fix

原 action schema 已允许 `STOP.final_confidence=null`，但 parser 会拒绝它。本轮仅将 parser 对齐此 nullable 字段；`STOP.final_verdict` 仍强制为 `real|fake`，`uncertain`、`inconclusive` 和缺失 verdict 均拒绝，不做映射或猜测。reasoning prompt、工具卡、Evidence v1、裁剪、模型 revision 和生成参数均保持不变。条件式 schema 文本候选在前 16 图出现退化后中止，原 schema 已恢复；细节见[中止记录](baseline_b0_schema_fixed/SCHEMA_CANDIDATE_ABORTED.md)。协议测试通过。

## 2. 30-sample Regression

| 指标 | 原 B0 | parser 对齐后完整回归 |
|---|---:|---:|
| 合法最终结论 | 28/30（93.33%） | 30/30（100%） |
| 合法工具请求 | 95/95 | 95/95 |
| 平均工具次数 | 3.17 | 3.17 |
| 多步完成率（含合法终态） | 28/30 | 30/30 |
| 提前 STOP 启发式 | 1/30 | 2/30 |
| 重复工具请求 | 0 | 0 |
| 原始格式错误 | 10 | 8 |
| 缺少合法最终结论 | 2 | 0 |

30/30 工具序列与原 B0 一致；原先 28 条合法 verdict 也未改变。8 次原始非法 `uncertain` STOP 在有限重试中恢复。回归轨迹 SHA-256 `1ee452bee4aec6328f6bf6d4b82d2d3ccb80a66a1cd03ad2518027aad034aaee`；[工程报告](baseline_b0_schema_fixed_v2/analysis/ACTOR_B_ORCHESTRATION_REPORT.md)。

## 3. Manual Attribution Audit

30 图回归按预定口径复核 125 个已接受步骤：显式违规 21/125（16.8%），隐含违规 19/125（15.2%），涉及 24/30 图（80.0%）；真实方向工具相反的 7 图均在最终状态识别冲突。详见[30 图人工复核](baseline_b0_schema_fixed_v2/analysis/MANUAL_AUDIT_30.md)。归因错误未通过 prompt、工具卡或轨迹后处理修复，也不作为单独的 SFT 触发条件。

## 4. Held-out Confirmation

60 图来自 Actor-0 eval 的 20 个独立来源组，RAISE / FLUX / SD3.5 各 20；覆盖既有方向工具一致与冲突的来源组。与 B0 30 图和 Mini FaithBench 固定 6 图的样本 ID、来源组均无重叠，其余 74 个 eval 来源组留给 Monitor test。manifest SHA-256 `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`。原图、Evidence v1 卡片及 crops 均在新克隆逐项核验。推理轨迹 SHA-256 `276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`；运行元数据 SHA-256 `031c5e1d081abc1fba0b1217e6d3271340f36ec05bd64211df353a497a0aa711`。

| held-out 指标 | 结果 | 预定冻结门槛 |
|---|---:|---:|
| 合法最终结论 / parse success | 55/60（91.67%） | ≥98% |
| 合法工具请求 | 189/189（100%） | 100% |
| 缺少合法最终结论 | 5/60 | ≈0 |
| 平均工具次数 | 3.15 | 明显大于 1 |
| 工具调用次数分布 | 2 次:12；3 次:27；4 次:21 | 无单工具捷径/机械全调用 |
| 多步完成率（含合法终态） | 55/60（91.67%） | ≥90% |
| 提前 STOP 启发式 | 5/60（8.33%） | ≤10% |
| 重复工具请求 | 0 | ≤5% |
| 原始格式错误 | 26 | 描述性 |

所有 60 图都实际调用了至少 2 次工具；多步完成率下降的 5 图是终态无效。首工具为 PROBE 28 图、来源凭据 32 图；工具子集/顺序共 9 种。局部纹理 60 图、PROBE 60 图、来源凭据 45 图、互补分析 24 图；没有极端单工具路径，也没有全图机械调用全部工具。[完整序列分布](heldout_confirmation/analysis/ACTOR_B_ORCHESTRATION_REPORT.md)。最终 balanced accuracy 仅用于诊断，不作准确率结论。

5 条无效终态均为 STOP verdict 的 `inconclusive` 或缺失，有限重试后仍非法；不是图像缺失、工具调用越界或 parser 把合法字段误判。60 图人工复核：显式归因违规 45/244 已接受步骤（18.4%），隐含 58/244（23.8%），涉及 47/60 图；真实方向工具相反 12 图中 2 图因最终 STOP 无效而缺少冲突后的合法状态；最终理由不受支持的综合推断 33/60。详见[60 图人工复核](heldout_confirmation/analysis/MANUAL_AUDIT_60.md)。这些失败模式提供后续 Monitor 研究样本，但未触发本次决策。

## 5. Decision

`ACTOR_B1_SFT_REQUIRED`

## 6. Rationale

预定冻结门槛 `parse_success≥98%` 与 `forced_or_missing_final≈0` 未满足：实际 91.67% 和 5/60。工具编排的多步、合法性、重复率、提前停止率与路径多样性均基本达到门槛；决定性问题是 Actor 无法稳定输出可供 Monitor 消费的合法最终状态。原 30 图的 parser 修复不能解释或掩盖 held-out 的 5 次 STOP 协议失败；结果按原样保留。按方案输出[SFT 触发报告](ACTOR_B_SFT_TRIGGER_REPORT.md)并停止本轮，不训练、不运行正式 900 条、不建立 `frozen_actor`。后续若改用严格约束解码等工程方案，必须另立实验并明确额外算力与冻结口径，不能把这次失败改算为通过。
