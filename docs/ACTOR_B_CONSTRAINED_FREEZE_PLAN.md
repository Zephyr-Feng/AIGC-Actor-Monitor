# Actor-B 下一步执行方案：Contract-Constrained Freeze Gate

## 0. 当前结论

现有 Actor-B0 held-out 结果表明：

- 合法 tool call：189/189；
- 平均 tool call：3.15；
- 所有样本至少调用 2 个工具；
- 无重复工具调用；
- premature STOP：8.33%；
- 存在 9 种工具路径；
- 没有单工具 shortcut；
- 没有机械全工具调用；
- multi-step orchestration 基本达到预定门槛。

当前冻结失败的决定性因素只有：

```text
55/60 valid final state
5/60 invalid STOP verdict
```

5 个失败均属于：

```text
final_verdict = inconclusive
```

或：

```text
final_verdict missing
```

而不是：

- illegal tool selection；
- tool-call failure；
- evidence state 丢失；
- 单工具 shortcut；
- 无法进行多步推理。

因此，本轮**暂缓 Actor-B1 SFT**。

先执行一次：

> **Actor-B0-C：contract-constrained decoding experiment**

目标是确认：

> 能否通过纯工程约束消除 STOP contract failure，而不改变 Actor 的 forensic reasoning 和 tool orchestration。

---

# 1. 核心原则

本轮只能解决：

```text
STOP → final_verdict ∈ {real, fake}
```

不得尝试解决：

- attribution violation；
- unsupported synthesis；
- conflict omission；
- fake bias；
- final accuracy；
- evidence reasoning；
- premature STOP reasoning；
- tool selection reasoning。

这些继续保留为 Monitor 研究对象。

---

# 2. 不做 SFT

本轮禁止：

```text
LoRA
QLoRA
full finetuning
DPO
MiPO
GRPO
PPO
preference optimization
trajectory augmentation
```

只有本轮严格约束解码仍无法形成稳定可消费的合法 trajectory，才重新考虑 Actor-B1 SFT。

---

# 3. 不修改 reasoning

严格冻结：

- system reasoning prompt；
- tool descriptions；
- Evidence v1；
- evidence semantics；
- callable；
- tool selection guidance；
- STOP reasoning guidance；
- image/crop pipeline；
- model revision；
- processor revision；
- generation sampling parameters，除实现局部 constrained decoding 所必须的部分外。

特别禁止为了减少：

```text
PROBE → real/fake attribution
```

而修改 prompt。

---

# 4. 实现目标：只约束动作协议

优先实现**局部字段级约束**，而不是重新设计整个 Actor 输出格式。

最终协议仍然是：

```text
next_action = CALL_TOOL | STOP
```

当：

```text
next_action = STOP
```

时：

```text
final_verdict ∈ {"real", "fake"}
```

模型不能生成第三个类别。

允许：

```text
final_confidence = low
```

来表达不确定性。

即：

```text
STOP
final_verdict = fake
final_confidence = low
evidence_gap = ...
```

是合法的。

但：

```text
STOP
final_verdict = inconclusive
```

永远不合法。

---

# 5. 推荐实现优先级

按照以下优先级选择实现，使用当前代码栈中最简单、最稳定的方法。

## 优先级 A：字段级 constrained decoding

如果现有推理后端支持 grammar / JSON schema / allowed tokens：

直接限定：

```text
final_verdict:
enum ["real", "fake"]
```

这是首选。

---

## 优先级 B：STOP 后单独进行 forced-choice decoding

如果整段 JSON constrained decoding 实现复杂，则不要为了 Actor 引入大型新框架。

可以采用两阶段协议：

### Stage 1

Actor 正常生成：

```text
reasoning
evidence_state
next_action
...
```

### Stage 2

如果：

```text
next_action = STOP
```

则 `final_verdict` 不再自由生成，而由同一个模型在完全相同的最终上下文下进行：

```text
real
vs
fake
```

二选一 constrained decoding。

可以比较两个合法字符串的条件 likelihood，或者使用 token-level allowed set。

这仍然是：

> 模型自己的预测。

不是 parser 猜测，也不是规则根据 tool score 自动赋值。

---

# 6. 严禁的“修复方式”

不得：

### Mapping

```text
inconclusive → fake
```

或：

```text
uncertain → real
```

### Tool-based repair

例如：

```text
if PatchCraft > threshold:
    verdict = fake
```

### Label-based repair

不得查看 GT 后补 final verdict。

### Retry reasoning patch

不得在 retry 中告诉模型：

```text
Evidence strongly supports fake, choose fake.
```

retry 只能施加合法输出空间约束。

---

# 7. 原始输出必须保留

对于任何 constrained decode：

同时保存：

```text
raw_unconstrained_output
```

和：

```text
contract_constrained_output
```

不能覆盖原输出。

需要能够审计：

> 模型原本想生成什么；

以及：

> 严格动作空间下最终选择了什么。

---

# 8. Phase A：5 个失败轨迹的 Replay

不要重新跑 detector。

不要重新计算 crops。

不要重新调用工具。

直接复用 held-out 60 中这 5 个失败样本在 STOP 前的完整：

```text
image context
tool observations
evidence state
conversation history
```

只重放最终 STOP generation。

对 5 条分别运行 contract-constrained version。

检查：

```text
5/5 valid final_verdict?
```

并记录：

```text
real/fake selection
confidence
action_reason
```

---

# 9. 加入成功对照组

为了确认 constrained decoding 没有破坏原来合法的行为，从原 held-out 55 条合法样本中固定抽取若干控制样本。

建议：

```text
10–20 条
```

覆盖：

- 原 verdict = real；
- 原 verdict = fake；
- high / medium / low confidence；
- tool agreement；
- tool conflict；
- 不同 tool sequences。

对这些样本进行相同 final-state replay。

重点检查：

> constrained version 是否保持原本合法 verdict。

统计：

```text
valid_verdict_preservation_rate
```

理想结果：

```text
≈100%
```

---

# 10. Phase B：完整 60 条 Contract Replay

如果 Phase A 正常，则对原 held-out 60 条进行 contract-level replay。

原则上不重新跑工具。

优先复用全部真实 frozen tool responses 与 trajectory state。

如果实现要求从 Actor step 开始重新生成，也必须确保：

- 工具 observation 使用原缓存；
- 工具本身不重新计算；
- 所有版本信息保持一致。

---

# 11. 关键检查：不要改变 Actor 行为

如果约束仅作用于 `final_verdict`，则应验证：

```text
tool sequence unchanged
```

```text
number of tool calls unchanged
```

```text
evidence cards unchanged
```

```text
next_action history unchanged
```

```text
reasoning before final verdict unchanged
```

如果这些发生变化，需要说明原因。

本实验最理想的情况是：

\[
Trajectory_{old}
=
Trajectory_{new}
\]

除最后非法 verdict 被限制为：

\[
real/fake
\]

之外完全相同。

---

# 12. Freeze Gate

如果满足：

```text
parse_success = 60/60
legal_tool_call_rate = 100%
forced_or_missing_final = 0
```

并且：

```text
tool sequences unchanged
```

同时原来的：

```text
multi-step behavior
premature STOP distribution
tool diversity
```

没有因为约束发生实质退化，

则直接：

```text
ACTOR_B0_C_FREEZE
```

不启动 SFT。

---

# 13. Attribution 不参与 Freeze Gate

当前人工 audit 已发现：

30 图：

```text
24/30 samples with attribution violation
```

60 图：

```text
47/60 samples with attribution violation
```

以及：

```text
33/60 unsupported final synthesis
```

这些全部保留。

本轮禁止因为这些指标较高而判 Actor 不合格。

它们应进入：

> FaithBench / Monitor failure pool。

当前 Actor 的价值恰恰在于：

> tool orchestration 基本正常，但 evidence reasoning 存在大量真实、细微且可审计的错误。

---

# 14. 何时才真正启动 Actor-B1 SFT

只有以下情况才进入 SFT：

## 情况 A

无法在当前技术栈中实现可靠 constrained decoding。

## 情况 B

严格 contract 后仍频繁产生无法消费的 trajectory。

## 情况 C

为了满足合法 contract，必须大幅修改 Actor reasoning / action generation，以至于 orchestration 明显退化。

## 情况 D

即使把格式完全工程化，Actor 仍存在真正的 orchestration failure，例如：

```text
large-scale premature STOP
single-tool shortcut
random tool selection
conflict → immediate STOP
unusable evidence state
```

当前结果尚未证明以上情况。

---

# 15. 不重新消耗 Monitor Test

当前还有：

```text
74 个来源组
```

预留给 Monitor test。

本轮禁止为了验证 contract constrained decoding 使用这些来源组。

因为：

> final_verdict legality 是 deterministic action-space property，不需要消耗新的 Monitor test data。

使用已有 60 图 replay 即可验证 contract implementation。

后续 Actor-B FREEZE 后，74 组继续保持 untouched。

---

# 16. 如果冻结成功

输出：

```text
ACTOR_B_FREEZE_MANIFEST.json
```

固定：

- code commit；
- model revision；
- processor revision；
- prompt SHA；
- Evidence v1 SHA；
- tool revisions；
- schema SHA；
- parser version；
- constrained decoder version；
- generation config；
- held-out manifest SHA。

Actor 正式命名建议：

```text
Actor-B
Structured Tool-Using Forensic Actor
```

并注明：

> Actor-B uses contract-constrained action decoding for structural validity; forensic reasoning remains model-generated and unconstrained.

---

# 17. 冻结后立刻停止 Actor 开发

不得继续做：

```text
Actor-B2
better prompt
better attribution
better evidence synthesis
higher accuracy
better self-reflection
```

下一阶段直接进入：

```text
FaithBench Construction
```

---

# 18. FaithBench 的第一批真实 failure 已经存在

现有轨迹已经足够形成至少以下候选：

### Evidence attribution failure

```text
non-directional PROBE
→ directional real/fake interpretation
```

### Unsupported synthesis

已有：

```text
33/60
```

候选。

### Conflict-related failure

方向工具相反样本已经存在。

### Premature STOP

已有真实样本。

### Clean trajectory

用于 Monitor negative/control。

因此 Actor-B 一旦 freeze：

> 不需要再优化 Actor 才能开始 Monitor。

---

# 19. 本轮输出

输出：

```text
ACTOR_B_CONSTRAINED_FREEZE_REPORT.md
```

至少包含：

## A. Implementation

约束发生在什么字段、什么阶段。

## B. Five Failure Replay

5 个原非法 STOP 的新结果。

## C. Control Replay

原合法样本是否保持原 verdict。

## D. Full 60 Replay

报告：

```text
parse_success
forced_or_missing_final
verdict preservation
tool-sequence preservation
```

## E. Decision

只能是：

```text
ACTOR_B0_C_FREEZE
```

或：

```text
ACTOR_B1_SFT_REQUIRED
```

---

# 20. 当前默认假设

基于现有结果，本轮默认研究假设为：

> Actor-B 不缺少 tool orchestration 能力；它缺少的是严格终态动作约束。

因此优先验证：

\[
\boxed{
Engineering\ constraint
}
\]

而不是：

\[
\boxed{
Model\ retraining
}
\]

只有该假设被实验否定，才启动 SFT。

---

# 21. 最重要的停止原则

如果 constrained decoding 能让 Actor-B：

```text
100% legal terminal state
```

同时保持当前 orchestration 行为，

则立即冻结。

不要因为：

```text
80% attribution failure
```

继续训练 Actor。

那已经不再是 Actor infrastructure 问题。

那正是：

\[
\boxed{\text{Monitor research problem}}
\]