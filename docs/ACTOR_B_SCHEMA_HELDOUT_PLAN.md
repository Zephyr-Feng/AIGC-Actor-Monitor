# Actor-B 下一步执行方案：Schema 收尾、Held-out 确认与冻结决策

## 0. 当前状态

已有 Actor-B0 baseline：

- 30 条 sanity samples；
- `parse_success = 93.33%`；
- `legal_tool_call_rate = 100%`；
- `average_tool_calls = 3.17`；
- `premature_stop_rate = 3.33%`；
- `repeated_tool_call_attempt_rate = 0%`；
- `multi_step_completion_rate = 93.33%`；
- 存在 10 个 format errors；
- 2 个 forced/missing final；
- 30 个样本中 9 个出现显式 global directional attribution；
- 当前状态为 `B0_REVIEW_REQUIRED`。

当前判断：

> Actor-B0 的 tool orchestration 已经基本可用，当前没有充分证据支持立即进行 SFT。

本轮任务只回答一个问题：

> **修掉纯工程格式问题后，Actor-B0 是否已经足够稳定，可以直接冻结并进入 FaithBench / Monitor？**

---

# 1. 本轮禁止事项

本轮禁止：

- 修改 forensic tools；
- 修改 Evidence v1；
- 修改 PROBE 语义；
- 修改 crop/image pipeline；
- 新增 detector；
- 修改 Actor reasoning prompt 来修 attribution；
- 为 attribution error 做 prompt patch；
- 启动 LoRA/SFT；
- 启动 MiPO / DPO / GRPO / RL；
- 跑正式 900 条；
- 为提高 final accuracy 调 Actor；
- 根据单个失败样本持续迭代 prompt。

除非发现明确工程 bug，否则：

> **reasoning behavior 保持冻结。**

---

# 2. Phase A：纯 Schema / Contract 修复

目标：

> 去掉所有不应该由模型学习的格式错误。

允许修改范围仅限：

- output schema；
- parser；
- constrained decoding / enum validation；
- CALL_TOOL / STOP contract；
- invalid final field handling；
- callable validation。

不得修改：

- system prompt 中的 evidence reasoning 规则；
- tool descriptions 的语义；
- action selection guidance；
- evidence attribution guidance。

---

## 2.1 强制结构约束

确保：

```text
next_action ∈ {CALL_TOOL, STOP}
```

如果：

```text
next_action = CALL_TOOL
```

则：

```text
selected_tool ∈ VALID_TOOLS
final_verdict = null
```

如果：

```text
next_action = STOP
```

则：

```text
selected_tool = null
final_verdict ∈ {real, fake}
```

禁止：

```text
final_verdict = uncertain
```

禁止 STOP 时 verdict 缺失。

---

## 2.2 Parser 原则

parser 不允许：

- 将 `uncertain` 自动映射为 real/fake；
- 根据 confidence 猜 verdict；
- 根据 tool scores 自动补 verdict；
- 修改 reasoning；
- 自动修复 evidence attribution。

parser 只负责：

> 格式合法化与明确非法输出拒绝。

如模型输出内容无法满足 schema，可进行有限 retry，但 retry prompt 只能指出：

> 输出格式违反 schema。

不得加入 forensic reasoning 提示。

---

# 3. Phase B：原 30 条回归复跑

完成 schema 修复后，使用**完全相同的 30 条 baseline manifest**重新运行。

必须保持：

- 相同图片；
- 相同顺序；
- 相同工具结果；
- 相同 model revision；
- 相同 tool versions；
- 相同 Evidence v1；
- 相同 reasoning prompt；
- 相同生成参数，除非 schema constrained decoding 必须调整。

输出单独目录，例如：

```text
actor_b/baseline_b0_schema_fixed/
```

禁止覆盖原 B0。

---

# 4. Phase B 验收指标

至少重新统计：

```text
parse_success
legal_tool_call_rate
tool_call_requests
average_tool_calls
premature_stop_rate
repeated_tool_call_attempt_rate
multi_step_completion_rate
forced_or_missing_final
format_errors
first_tool_counts
tool_call_counts
final_balanced_accuracy
global_directional_attribution_steps
global_directional_attribution_samples
```

---

## 4.1 Schema 层目标

期望：

```text
parse_success = 100%
legal_tool_call_rate = 100%
forced_or_missing_final = 0
format_errors ≈ 0
```

如果仍出现少量 parser 问题，优先判断：

> 是 schema 实现 bug，还是模型根本无法满足协议？

只修工程问题。

---

## 4.2 Orchestration 层目标

不要求每个数与原 B0 完全一致，但应保持同一量级。

重点确认：

```text
multi_step_completion_rate >= 90%
premature_stop_rate <= 10%
repeated_tool_call_attempt_rate <= 5%
legal_tool_call_rate = 100%
```

平均 tool calls 不设死门槛，但应明显大于 1。

如果 schema 修复后 Actor 突然退化成：

```text
大量单步 STOP
```

或：

```text
固定全工具调用
```

则标记异常并调查 schema 是否改变了 action behavior。

---

# 5. Phase C：人工 Attribution Audit

不要自动把 attribution error 修掉。

对 schema-fixed 的 30 条轨迹进行一次人工审计。

审计重点不是最终 verdict，而是：

> Actor 是否错误赋予某个 evidence 不存在的方向性含义。

特别检查以下语言：

```text
supports real
supports fake
indicates real
indicates fake
consistent with fake
consistent with real
aligns with fake
aligns with authenticity
confirms
reinforces
corroborates
agrees with
points toward
forms a tendency
```

以及中文等价表达。

---

## 5.1 Attribution 分类

每个可疑 step 标记为：

```text
VALID_DIRECTIONAL_USE
VALID_NON_DIRECTIONAL_USE
EXPLICIT_ATTRIBUTION_VIOLATION
IMPLICIT_ATTRIBUTION_VIOLATION
AMBIGUOUS
```

重点单独统计：

```text
explicit_attribution_violation_rate
implicit_attribution_violation_rate
sample_level_attribution_violation_rate
```

---

## 5.2 不进行修复

即使发现：

```text
PROBE deviation → supports fake
```

也只记录。

不要：

- 改 prompt；
- 改 tool card；
- 改 trajectory；
- 重跑该样本直到正确。

这些 failure 将成为后续 FaithBench 候选。

---

# 6. Phase D：构建独立 Held-out Confirmation Set

如果 schema-fixed 30 条工程正常，则开始一次新的 held-out confirmation。

样本数量：

> **建议 60 条左右。**

允许范围：

```text
50–100
```

默认使用 60，除非现有冻结数据组织使其他数量更合理。

---

## 6.1 样本必须独立

不得使用：

- 原 B0 的 30 条；
- Mini FaithBench 固定 6 图；
- 用于 prompt 调试的样本；
- 后续计划正式作为 Monitor test 的保留样本。

建立新的 frozen manifest，并记录 SHA-256。

---

## 6.2 类别组成

尽量覆盖：

- real；
- 不同 fake generator；
- 已知 tool agreement；
- 已知 tool disagreement；
- 不同难度；
- 不同 forensic evidence pattern。

不要求完全平衡，但避免全部集中在单一 fake generator。

---

# 7. Held-out 实验目的

这次实验**不是 accuracy benchmark**。

禁止根据 60 条的 final accuracy 做 headline claim。

主要验证三件事：

### A. Orchestration stability

Actor 是否仍然：

- 能多步调用；
- 不会重复工具；
- 不会大量 premature STOP；
- 不会固定走单一路径。

### B. Trajectory diversity

检查：

- first tool 是否有变化；
- tool subset 是否有变化；
- tool order 是否存在多样性；
- 不同 evidence state 是否导致不同 action。

避免：

```text
所有样本完全相同调用序列
```

### C. Reasoning failure prevalence

确认真实环境中仍然存在一定比例：

- attribution error；
- conflict omission；
- unsupported synthesis；
- premature STOP；
- evidence-gap mistake。

这些错误不是本阶段失败，只要 orchestration 本身稳定。

---

# 8. Held-out 必须输出的指标

至少包括：

```text
parse_success
legal_tool_call_rate
average_tool_calls
tool_call_distribution
first_tool_distribution
tool_sequence_distribution
premature_stop_rate
repeated_tool_call_attempt_rate
multi_step_completion_rate
final_balanced_accuracy
explicit_attribution_violation_rate
implicit_attribution_violation_rate
sample_level_attribution_violation_rate
conflict_omission_rate
unsupported_synthesis_rate
```

如果某些 reasoning 指标暂时只能人工统计，可以人工审计全部 60 条，或者先自动筛选后人工确认。

---

# 9. FREEZE / SFT 决策规则

Held-out 完成后，只允许做一次决策。

---

## 9.1 FREEZE 条件

如果总体表现满足：

### Engineering

```text
parse_success >= 98%
legal_tool_call_rate = 100%
forced_or_missing_final ≈ 0
```

### Orchestration

```text
multi_step_completion_rate >= 90%
premature_stop_rate <= 10%
repeated_tool_call_attempt_rate <= 5%
```

并且人工检查确认：

- tool selection 不是明显随机；
- 没有极端单工具 shortcut；
- 不会所有样本机械调用全部工具；
- 遇到部分冲突时能够继续取证；
- trajectory 信息足够后续 Monitor 阅读。

则：

```text
Actor-B status: FREEZE
```

---

## 9.2 Attribution error 不作为否决条件

即使存在：

```text
10–30% attribution failure
```

甚至一定程度的：

```text
unsupported synthesis
conflict omission
```

也不自动触发 SFT。

这些错误首先视为：

> Monitor research target。

只有它们严重到：

> trajectory 基本失去可解释性，无法作为 Monitor 输入

时，才考虑 Actor 不合格。

---

# 10. 只有以下情况才允许启动 SFT

Actor-B1 SFT 只有在出现下面任一类**明显 orchestration failure**时启动：

### 严重单工具 shortcut

例如绝大多数样本只调用同一个 tool，然后 STOP。

### 严重 premature STOP

证据明显不足，但大量样本一两步结束。

### 无法根据 evidence state 选择工具

action 与 evidence gap 基本无关。

### 冲突后完全不会继续

工具矛盾时仍大规模直接 STOP。

### 轨迹结构不可用

大量 evidence state 丢失、逻辑断裂，导致 Monitor 无法理解发生了什么。

### Schema 工程化后仍频繁失败

说明模型连最基本 protocol 都没有内化。

---

# 11. 如果不满足 SFT 条件

直接：

```text
FREEZE Actor-B0
```

不要因为：

- Accuracy 不够高；
- attribution error 存在；
- reasoning 不够漂亮；
- 某些工具判断错；
- Actor 没有主动自我反思；

而启动 SFT。

---

# 12. 如果满足 SFT 条件

停止当前任务并提交：

```text
ACTOR_B_SFT_TRIGGER_REPORT.md
```

只说明：

1. 哪一项 orchestration requirement 未满足；
2. 失败比例；
3. 典型轨迹；
4. 为什么 schema 修复无法解决；
5. 为什么需要 trajectory SFT。

未经批准，不直接开始大规模 SFT。

---

# 13. Actor FREEZE 后的版本固定

一旦通过：

记录：

```text
model revision
prompt SHA
schema SHA
runner commit
tool revisions
Evidence v1 SHA
generation config
parser version
```

建立：

```text
actor_b/frozen_actor/
```

并输出：

```text
ACTOR_B_FREEZE_MANIFEST.json
```

之后 Monitor 开发期间：

> 禁止因为 Monitor 表现不好而修改 Actor-B。

---

# 14. 冻结后立即转入 FaithBench

Actor-B FREEZE 后，下一个阶段不是继续 Actor evaluation。

立即开始：

> **FaithBench trajectory collection**

优先收集：

```text
Actor-A trajectories
Actor-B trajectories
```

并筛选：

```text
attribution violations
unsupported synthesis
conflict omissions
premature STOP
unnecessary continuation
verdict inconsistency
clean trajectories
```

形成：

```text
positive trajectory
vs
failure trajectory
```

数据池。

---

# 15. 本轮最终报告

完成后输出：

```text
ACTOR_B_FREEZE_DECISION_REPORT.md
```

结构至少包括：

## 1. Schema Fix

说明修改内容仅涉及格式/contract。

## 2. 30-sample Regression

原 B0 vs schema-fixed B0。

## 3. Manual Attribution Audit

报告 explicit / implicit attribution errors。

## 4. Held-out Confirmation

报告 50–100 条独立样本表现。

## 5. Decision

只能写：

```text
ACTOR_B0_FREEZE
```

或：

```text
ACTOR_B1_SFT_REQUIRED
```

## 6. Rationale

只基于 orchestration usability 决策。

---

# 16. 当前默认预期

根据现有 30 条结果：

```text
legal_tool_call_rate = 100%
average_tool_calls = 3.17
premature_stop_rate = 3.33%
repeated_tool_call_attempt_rate = 0%
multi_step_completion_rate = 93.33%
```

当前默认假设为：

> **Actor-B0 很可能无需 SFT。**

本轮任务的作用是验证这一判断，而不是证明 SFT 有用。

如果 held-out confirmation 支持这一判断，应立即冻结 Actor-B0。

---

# 17. 核心原则

本阶段只回答：

\[
\boxed{
Is\ Actor\text{-}B0\ good\ enough\ to\ serve\ as\ a\ fixed\ trajectory\ generator?
}
\]

而不是：

\[
\boxed{
Can\ we\ make\ Actor\text{-}B0\ reason\ perfectly?
}
\]

前者通过即可结束 Actor 阶段。

后者属于后续 Monitor 所要研究的问题。