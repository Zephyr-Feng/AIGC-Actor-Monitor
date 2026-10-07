# Actor-B0-D：Evidence Sufficiency & Tool Strategy Gate

## 0. 本轮目标

本轮只回答一个问题：

> 冻结的 Actor-B0-C 是否已经具备足够可靠的自主取证、冲突处理、证据充分性判断和多工具综合能力；如果没有，缺陷是否足以支持进入 Actor-B1 SFT。

本轮不是分类性能优化实验，也不是继续修 STOP contract。

禁止因为本轮结果直接修改 Actor prompt、tool schema、Evidence v1、detector、crop pipeline 或模型参数。

最终只允许输出以下两个决策之一：

`ACTOR_B0_D_PASS_NO_SFT`

或

`ACTOR_B1_SFT_JUSTIFIED`

如果证据不足以支持任一结论，则输出：

`ACTOR_B0_D_INCONCLUSIVE`

---

# 1. 冻结项

必须复用已经通过 freeze gate 的 Actor-B0-C。

冻结以下内容：

- Qwen3-VL-8B-Instruct model revision
- Actor system prompt
- tool schema
- generation configuration
- Evidence v1 输出格式
- 所有 detector/tool checkpoint
- crop 生成逻辑
- STOP schema
- minimal STOP repair policy
- tool callable interface
- parser
- verdict 定义

Minimal STOP policy：

```text
if raw final_verdict ∈ {real, fake}:
    原样保留
else:
    仅对 invalid verdict 使用已冻结的 same-model real/fake projection
```

禁止恢复“all-STOP forced choice”。

在正式运行前记录：

- model revision
- prompt SHA-256
- schema SHA-256
- tool code/version hash
- manifest SHA-256
- generation config
- 当前 Git commit

写入：

```text
actor_b0_d/FROZEN_INPUTS.md
```

---

# 2. 数据集设计

建立一个独立的 diagnostic manifest。

目标规模：

```text
60 samples
```

优先从已有冻结评测数据中选择，不重新构造图片。

样本必须按“行为诊断价值”选择，而不是随机追求总体 accuracy。

建议组成：

### A. Easy agreement：12 张

多个工具证据方向基本一致。

目标：

检查 Actor 是否会在证据已经充分时合理停止，而不是机械调用全部工具。

建议：

- 6 real
- 6 fake

---

### B. PROBE failure / complementary cases：12 张

优先包含已有的 PROBE 错误样本及其相近困难样本。

目标：

检查 Actor 是否形成：

```text
PROBE → verdict → STOP
```

单工具捷径。

要求尽可能覆盖：

- PROBE 错、其他工具对
- PROBE 高置信但结论错误
- PROBE evidence 与其他 evidence 冲突

---

### C. Tool disagreement：16 张

选择工具之间存在明显分歧的样本。

例如：

```text
Tool A strongly suspicious
Tool B weak/neutral
Tool C supports real
```

目标：

测试冲突后是否继续取证，以及是否能够解释冲突。

---

### D. Weak evidence / insufficient evidence：10 张

所有工具均无特别强证据，或证据质量不稳定。

目标：

测试 Actor 是否理解：

```text
当前证据不足 ≠ 可以随便 STOP
```

同时也检查其是否会无意义无限调用工具。

---

### E. Difficult but solvable：10 张

尽量选历史上 detector 或 Actor 判断困难，但多工具联合后有合理证据链的样本。

建议：

- 5 real
- 5 fake

---

必须输出：

```text
actor_b0_d/data/diagnostic_manifest.jsonl
actor_b0_d/data/SELECTION_REPORT.md
```

每条至少记录：

```json
{
  "sample_id": "...",
  "gt": "real/fake",
  "source_group": "...",
  "generator": "...",
  "diagnostic_category": "...",
  "selection_reason": "..."
}
```

GT 只允许用于最终评测，不允许进入 Actor 输入。

---

# 3. 实验条件

同一批 60 张，在以下条件运行。

## Condition 1：FULL

原始 Actor-B0-C。

所有工具正常可见。

这是主基线。

---

## Condition 2：PROBE-MASK

隐藏 PROBE 工具。

禁止修改其他工具描述。

目的：

测试 Actor 是否实际上依赖 PROBE 才能完成取证。

如果 tool registry 需要保持编号稳定，可以保留内部 ID，但 Actor 不得看到或调用 PROBE。

---

## Condition 3：PROBE-DELAY

PROBE 存在，但禁止作为第一次工具调用。

Actor 第一次 CALL 如果选择 PROBE，则返回一个结构化 contract error：

```text
PROBE is unavailable as the first evidence source.
Choose another available tool.
```

这不是模型失败，不计 parser failure。

第二次及以后允许调用 PROBE。

目的：

测试 Actor 能否主动先取得其他独立证据。

禁止通过 prompt 告诉 Actor“PROBE 很强”或暗示正确工具顺序。

---

## Condition 4：TOOL-RENAME

保持工具功能、输入输出完全不变。

仅将明显携带语义或历史暗示的 tool name 替换为中性名字，例如：

```text
tool_alpha
tool_beta
tool_gamma
tool_delta
```

tool description 中仍保留完成调用所必需的功能说明，但不得出现：

- detector accuracy
- 专家强弱
- 主力专家
- PROBE 名称
- “最可靠”
- “推荐优先使用”

目的：

检查 Actor 是根据 evidence need 选择工具，还是根据工具名字形成捷径。

---

# 4. 运行规则

四个 condition 必须使用：

- 完全相同的 60 张
- 相同样本顺序
- 相同模型 revision
- 相同生成配置
- 相同最大 tool-call budget
- 相同 STOP parser
- 相同 minimal contract policy

不得因为某个 condition 表现异常临时修改 prompt。

每个 sample 保存完整原始轨迹。

至少保存：

```text
raw model output
parsed action
tool input
tool output / Evidence Card
tool sequence
STOP output
minimal policy result
token usage
number of calls
parse failures
retries
```

目录建议：

```text
actor_b0_d/
├── data/
├── full/
├── probe_mask/
├── probe_delay/
├── tool_rename/
├── evaluation/
└── report/
```

---

# 5. 必须计算的基础指标

## 5.1 Final task metrics

每个 condition：

```text
Accuracy
Balanced Accuracy
Specificity
Fake Recall
Invalid trajectory rate
Final parse success
```

这些只作为背景结果。

本轮核心不是追求最高 Accuracy。

---

# 6. 核心行为指标

## 6.1 Single-Tool STOP Rate

定义：

```text
只调用 1 个工具后立即 STOP 的轨迹数
/
有效轨迹总数
```

另外单独计算：

```text
PROBE-only STOP Rate
```

FULL condition 必须报告。

---

## 6.2 Conflict Follow-up Rate

先根据冻结的 tool outputs 标记“明显冲突样本”。

不得用 Actor verdict 定义 conflict。

建议规则：

至少两个独立工具产生方向明显不同的 evidence interpretation。

计算：

```text
Conflict Follow-up Rate
=
发生工具冲突后，Actor 至少再调用一个独立工具的轨迹数
/
存在明显工具冲突的轨迹数
```

这是本轮核心指标之一。

---

## 6.3 Premature STOP Rate

对 weak-evidence 和 conflict subsets 做人工或规则审计。

判定 Actor STOP 时是否仍存在明确的未解决 evidence gap。

例如：

```text
只有单一纹理证据
但仍有可用独立证据源
Actor 却直接 STOP
```

记录：

```text
premature_stop = true / false
reason
```

计算：

```text
Premature STOP Rate
```

---

## 6.4 Tool Redundancy Rate

记录明显重复、没有增加独立信息的调用。

例如：

同一 evidence source 被无理由重复调用，且没有改变区域、参数或问题。

计算：

```text
redundant_calls / all_tool_calls
```

---

## 6.5 Evidence Diversity at STOP

对每个 STOP，统计最终 reasoning 实际使用了多少类独立 evidence。

注意：

“调用了三个工具”不等于“用了三个证据”。

需要区分：

```text
tools_called
tools_cited
independent_evidence_types_used
```

报告：

```text
mean evidence sources at STOP
median
1-source %
2-source %
3+-source %
```

---

## 6.6 Evidence-to-Verdict Consistency

人工审计 final reasoning。

判断：

> 最终 verdict 是否能够由轨迹中实际得到的 evidence 支持。

禁止因为 GT 正确就判 reasoning 正确。

例如：

```text
GT = fake
Actor = fake
但理由引用了不存在的工具结果
```

仍然判 inconsistent。

---

## 6.7 Unsupported Claim Rate

统计 Actor reasoning 中出现但工具 observation 并未支持的事实性判断。

特别关注：

```text
把 observation 夸大成结论
把模型 interpretation 写成 detector verdict
凭空声明某区域存在 artifact
```

---

## 6.8 Tool Selection Appropriateness

对每一次 CALL 判断：

> 根据当前已经获得的 evidence，下一步所选择的工具是否针对尚未解决的问题提供新的独立信息。

建议三分类：

```text
appropriate
reasonable_but_redundant
inappropriate
```

不得按“这个工具最后是否预测正确”来判定。

---

# 7. 专门的 shortcut 分析

重点比较 FULL、PROBE-MASK 和 PROBE-DELAY。

需要回答以下问题：

### Q1

FULL 中 Actor 第一次调用 PROBE 的比例是多少？

### Q2

第一次调用 PROBE 后立即 STOP 的比例是多少？

### Q3

PROBE-MASK 后：

- 是否仍能合理调用其他工具？
- 是否出现大量无效 STOP？
- accuracy 是否灾难性下降？
- evidence diversity 是否显著变化？

### Q4

PROBE-DELAY 后：

Actor 是否能够选择一个合理的替代 first tool？

还是出现：

```text
反复尝试 PROBE
随机选工具
直接 STOP
```

### Q5

TOOL-RENAME 后：

tool choice 分布是否发生异常大幅漂移？

如果只改工具名称就让策略崩溃，应视为明显 shortcut evidence。

---

# 8. 人工审计集

从 60 张中固定抽取至少 20 张做人审。

必须覆盖：

```text
5 easy agreement
5 conflict
5 PROBE failure
5 weak evidence
```

如果已有固定 20 control subset，可优先复用，但不得为了结果好看重新筛选。

每条人工审计填写：

```json
{
  "sample_id": "...",
  "condition": "...",
  "tool_selection_quality": "...",
  "conflict_handling": "...",
  "stop_timing": "...",
  "evidence_sufficient": true,
  "unsupported_claim": false,
  "reasoning_faithful": true,
  "notes": "..."
}
```

至少一轮完整人工复核。

不要只依赖 LLM-as-judge。

---

# 9. SFT Gate

本轮结束后禁止根据“感觉”决定微调。

只有观察到稳定、重复、结构性的策略缺陷，才能输出：

```text
ACTOR_B1_SFT_JUSTIFIED
```

强 SFT 证据包括但不限于：

### A. 明显 PROBE shortcut

例如：

- FULL 中大量 PROBE-first + immediate STOP
- PROBE-MASK 后策略明显崩溃
- PROBE-DELAY 后无法选择合理替代 evidence source

### B. 冲突处理失败

存在明显工具冲突时，Actor 经常直接 STOP，而不是补充独立证据。

### C. Evidence insufficiency 判断失败

大量 weak-evidence 样本提前停止。

### D. Tool selection 不具备状态依赖性

Actor 不能根据当前 evidence gap 决定下一个工具，而表现为固定顺序或随机调用。

### E. Evidence synthesis 失败

虽然调用多个工具，但 final reasoning：

- 实际只依赖单一工具
- 忽略矛盾 evidence
- 编造 observation
- 把 non-conclusive evidence 当成工具 verdict

只有这些“策略能力问题”才支持 SFT。

以下情况不得作为 SFT 理由：

```text
少量 JSON invalid
单纯 Accuracy 不高
某个 detector 本身出错
个别难例分类错误
contract repair 可以解决的问题
```

---

# 10. 决策原则

## 输出 `ACTOR_B0_D_PASS_NO_SFT`

当：

- tool selection 基本合理
- conflict 后大多数情况会继续取证
- weak evidence 下不存在系统性 premature STOP
- PROBE-MASK / DELAY 不导致策略性崩溃
- TOOL-RENAME 不造成明显工具选择失效
- evidence synthesis 基本忠实
- 剩余错误主要来自 detector evidence 本身，而非 Actor strategy

此时：

冻结 Actor-B0-D。

下一阶段进入 Monitor 设计。

---

## 输出 `ACTOR_B1_SFT_JUSTIFIED`

当存在明确的、跨样本重复出现的：

```text
shortcut
premature STOP
conflict handling failure
poor tool selection
unfaithful evidence synthesis
```

此时先停止。

禁止直接开始训练。

先生成：

```text
ACTOR_B1_SFT_TARGETS.md
```

明确列出需要训练的行为能力。

例如：

```text
Target 1: evidence-gap-aware tool selection
Target 2: conflict-triggered follow-up
Target 3: evidence sufficiency estimation
Target 4: multi-source synthesis
Target 5: faithful STOP rationale
```

等用户批准后再设计 SFT 数据。

---

## 输出 `ACTOR_B0_D_INCONCLUSIVE`

当：

- diagnostic 样本过少
- conflict subset 不足
- 工具输出本身无法定义证据充分性
- 不同 condition 差异无法稳定解释
- 人工审计结论不一致

此时只提出需要补充的最小实验。

不要擅自训练。

---

# 11. 最终交付物

必须生成：

```text
actor_b0_d/
├── FROZEN_INPUTS.md
├── data/
│   ├── diagnostic_manifest.jsonl
│   └── SELECTION_REPORT.md
├── full/
│   └── trajectories.jsonl
├── probe_mask/
│   └── trajectories.jsonl
├── probe_delay/
│   └── trajectories.jsonl
├── tool_rename/
│   └── trajectories.jsonl
├── evaluation/
│   ├── metrics.json
│   ├── per_sample.csv
│   ├── conflict_analysis.csv
│   ├── tool_selection_audit.csv
│   └── human_audit.jsonl
└── report/
    └── ACTOR_B0_D_REPORT.md
```

---

# 12. 最终报告结构

`ACTOR_B0_D_REPORT.md` 必须包含：

```text
A. Frozen configuration
B. Diagnostic dataset
C. Overall task performance
D. Tool-selection behavior
E. Conflict handling
F. Evidence sufficiency / premature STOP
G. PROBE shortcut analysis
H. TOOL-RENAME robustness
I. Evidence faithfulness
J. Failure taxonomy
K. SFT gate decision
```

报告开头直接写：

```text
Final decision:
ACTOR_B0_D_PASS_NO_SFT
```

或：

```text
Final decision:
ACTOR_B1_SFT_JUSTIFIED
```

或：

```text
Final decision:
ACTOR_B0_D_INCONCLUSIVE
```

---

# 13. 本轮硬性禁止事项

不得：

- 修改 Actor-B0-C prompt
- 改 tool schema
- 微调模型
- 改 Evidence v1
- 根据 GT 调整 tool policy
- 根据当前结果挑掉失败样本
- 改 detector threshold
- 重训 detector
- 使用工具最终 fake probability 作为 Actor 隐式答案
- 把工具观察改写成真假结论再喂给 Actor
- 因为 accuracy 下降就直接宣布 SFT
- 启动 Monitor 训练
- 覆盖此前 Actor-B0-C freeze 结果

---

# 14. 执行停止点

完成：

```text
60 samples
×
4 conditions
```

以及规定的行为评测和人工审计后停止。

输出最终报告。

如果判定需要 SFT，仅提交 `ACTOR_B1_SFT_TARGETS.md`，不得开始 SFT。

如果判定无需 SFT，则报告下一阶段建议：

```text
Proceed to Monitor-0 design.
```

但不要实际开始 Monitor 实验。