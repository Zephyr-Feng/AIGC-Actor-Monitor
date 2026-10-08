# Actor-B0-D：Agent-Assisted Evidence & Tool Strategy Audit

## 0. 任务目标

对已经完成的 Actor-B0-D 四条件实验开展模型辅助审计，降低单人研究者的人工标注负担，同时保留真实人工最终裁决。

本轮只执行审计，不开展新实验、不修改 Actor、不训练模型。

最终交付：

1. 80 条 trajectory 的完整 Agent 预审结果。
2. 827 次 CALL_TOOL 的完整 Agent 预审结果。
3. 自动筛选、排序的人工重点复核清单。
4. 便于研究者快速确认或修改标签的审计材料。
5. 审计覆盖率、标注分布和不确定性分析。
6. 人工审核后的最终评估入口。

当前 gate 决策保持：

`ACTOR_B0_D_INCONCLUSIVE`

在研究者完成必要的人工确认前，不得改成 PASS 或 SFT_JUSTIFIED。

---

## 1. 输入与数据保护

首先检查项目中已有文件和审计脚本，确认实际目录与字段结构。

重点读取：

- `evaluation/HUMAN_AUDIT_GUIDE.md`
- `evaluation/human_audit.jsonl`
- `evaluation/tool_selection_audit.csv`
- `audit_packet.jsonl`
- 四条件 trajectories
- 对应的 Evidence Cards、工具说明和原图
- `ACTOR_B0_D_REPORT.md`

如文件位于其他目录，按仓库实际位置解析，不要自行创建空数据代替缺失输入。

审计规模：

| 对象 | 数量 |
|---|---:|
| 样本 | 20 |
| 实验条件 | 4 |
| Trajectory | 80 |
| CALL_TOOL 记录 | 827 |

四条件为 FULL、PROBE-MASK、PROBE-DELAY、TOOL-RENAME。

严格禁止读取、传入审计模型或利用 GT、最终 Accuracy、样本正确错误标记和历史 detector 正确率。不得把诊断类别名称当作 GT 线索。

保留原始文件及已有人工标签，所有 Agent 结果写入单独文件。逐样本审计材料不得上传 GitHub，也不得发送到未经授权的第三方服务。

如果原图、完整工具输出或 trajectory 无法读取，该条必须标记 `needs_source`，不得编造证据或直接给出高置信标签。

## 2. 审计原则

本轮审计的是 Actor 可观察的决策和证据使用行为，而不是模型内部隐藏的思维过程。

重点评价：

- Tool selection：调用的工具是否符合当前证据需求。
- Conflict handling：是否处理已经观察到的证据冲突。
- Evidence sufficiency：已有证据能否支持最终结论及其表述强度。
- STOP timing：应该继续取证还是已经可以停止。
- Reasoning faithfulness：最终解释是否忠实于实际观察。
- Unsupported claims：是否虚构、夸大或错误归因证据。

不得以真假分类是否正确作为以上标签的判定依据。

重要区分：

**工具给出错误方向，不代表 Actor 调用工具的决策错误。**

**Actor 最终分类正确，也不代表其推理忠实。**

---

## 3. 第一阶段：审计数据完整性检查

先执行只读检查，记录：

1. 80 条审计记录是否全部存在。
2. `(sample_id, condition)` 是否唯一。
3. 827 次 CALL 是否全部能关联到对应轨迹。
4. 原图、观察、工具输出、动作历史、最终解释是否可访问。
5. 已有人工标注是否存在。
6. 原始轨迹与冻结评测数据是否一致。

记录相关文件 SHA-256 和当前 Git commit。

生成：

`audit_assist/INPUT_VALIDATION.md`

如果发现缺失记录，先输出缺失清单，不得悄悄跳过，也不得凭推断补齐。

---

## 4. 第二阶段：80 条完整轨迹预审

对 80 条 trajectory 逐条独立评估。

每条只提供：

- 原始图像
- 当前 condition 下 Actor 可用的工具
- Actor 实际得到的 observation
- 完整动作轨迹
- 原始 STOP 和最小投影后的终态
- 最终 reasoning

首次审计时，不向审计模型提供同一图片在其他 condition 下的结果，避免配对结果影响独立判断。四条件之间的比较放在后续阶段。

### 4.1 必填字段

`tool_selection_quality`

- `appropriate`：工具选择能够合理补充证据。
- `reasonable_but_redundant`：有一定信息价值，但新增独立信息有限。
- `inappropriate`：选择不能合理解决当前证据缺口，或出现明确无效的策略行为。

`conflict_handling`

- `addressed`：已经看到冲突，进行了实质处理。
- `acknowledged_unresolved`：承认冲突，但受可用证据或预算限制无法解决。
- `ignored`：存在明显已观察冲突，但最终决策或解释忽略它。
- `not_applicable`：没有观察到实质冲突。

注意：继续调用工具不自动等于 `addressed`，还要检查后续是否合理处理冲突信息。

`stop_timing`

- `appropriate`
- `premature`
- `overcalled`
- `no_legal_stop`

`evidence_sufficient`

判断实际观察能否支持 Actor 当前结论及其表述强度，而不是判断其是否符合 GT。

`premature_stop`

只有仍然存在重要证据缺口，且当时仍有可用独立工具能够实质补充证据时，才应判为 true。

工具没有全部调用完，不自动算提前停止。

`verdict_consistent`

最终 verdict 是否受到实际获得的证据支持。

`unsupported_claim`

最终解释是否包含未获证据支持的观察或断言。

`reasoning_faithful`

是否准确反映已见证据、承认重要限制并处理明显冲突。

### 4.2 预审输出

每条生成：

```json
{
  "sample_id": "...",
  "condition": "FULL",
  "agent_review": {
    "tool_selection_quality": "appropriate",
    "conflict_handling": "addressed",
    "stop_timing": "appropriate",
    "evidence_sufficient": true,
    "premature_stop": false,
    "verdict_consistent": true,
    "unsupported_claim": false,
    "reasoning_faithful": true
  },
  "confidence": "medium",
  "evidence_references": [
    "step_2/tool_output",
    "step_4/actor_response"
  ],
  "notes": "...",
  "review_priority": "normal"
}
```

上例仅为字段结构，不是任何真实样本的审计结论。

每条必须给出具体依据，指向实际 trajectory step、tool output 或 final rationale。

Agent 不得仅凭印象给出理由。

对缺乏足够信息的字段，可使用独立的 `unassessable` 状态并说明原因，不能强行猜测 true/false。

输出：

`audit_assist/trajectory_agent_review.jsonl`

---

## 5. 第三阶段：827 次 CALL_TOOL 预审

对每次工具调用，重建调用发生时 Actor 实际掌握的信息状态。

审计时只能使用该次调用之前已获得的观察，不得用未来工具输出倒推当时的选择是否合理。

每次分析：

1. 已经获得什么证据？
2. 当前还缺什么信息？
3. Actor 选择了什么工具？
4. 该工具预期能补充什么独立信息？
5. 当时是否存在明显更合理的选项？
6. 该调用属于合理取证、冗余取证还是不合理取证？

填写：

- `appropriate`
- `reasonable_but_redundant`
- `inappropriate`

同时生成：

- `agent_confidence`
- `agent_reason`
- `evidence_gap`
- `expected_information_gain`
- `call_outcome`
- `review_priority`

`call_outcome` 需要区分成功调用、条件禁止、格式重试、预算拒绝和其他失败。不能将被禁止或被拒绝的请求计为成功取证，也不能仅因请求被禁止就判策略不合理。

如果同一轨迹出现多个调用错误，应区分独立的策略错误与同一上游错误引起的后续失败。

输出：

`audit_assist/call_agent_review.csv`

不得直接覆盖 `tool_selection_audit.csv` 内已有或预留的人工字段。

---

## 6. 第四阶段：自动生成重点人审清单

Agent 预审完成后，建立去重的复核队列。

### P0：必须重点审查

包含以下任意条件：

- Agent 判定 `inappropriate`
- `premature_stop=true`
- `conflict_handling=ignored`
- `unsupported_claim=true`
- `reasoning_faithful=false`
- `verdict_consistent=false`
- `no_legal_stop`
- 原始证据缺失或无法核验
- Agent 置信度为 low

这些记录不得自动视为人工确认通过。

### P1：重点比较

包括：

- TOOL-RENAME 中的所有首次工具选择。
- PROBE-DELAY 中被禁止的首次 PROBE 请求及其后续替代选择。
- FULL 与 TOOL-RENAME 行为明显不同的配对样本。
- 工具冲突后的关键决策节点。
- WEAK_EVIDENCE 样本的停止判断。
- Agent 标记为 `reasonable_but_redundant` 的调用。

P1 与 P0 重叠时只显示一次，但保留所有入选原因。

### P2：分层随机抽查

对剩余高置信 `appropriate` 调用进行分层随机抽样。

要求：

- 覆盖四个 condition。
- 覆盖不同工具类型。
- 覆盖不同调用位置。
- 固定随机种子 `20261007`。
- 保存抽样规则和实际抽中记录。

P0 全量保留，P1 优先；P2 不需要全部人审。不能为凑某个审计数量而删掉 P0。

优先将人工 CALL 复核规模控制在约 150–250 条，但这只是工作量目标，不是删减高风险记录的硬上限。若 P0/P1 去重后仍明显超过目标，报告数量与原因，并保留完整清单供研究者安排复核。

生成：

`audit_assist/HUMAN_REVIEW_QUEUE.csv`

其中至少包含：

```text
record_id
sample_id
condition
trajectory_step
review_priority
trigger_reasons
agent_label
agent_confidence
evidence_reference
agent_reason
human_label
human_notes
review_status
```

---

## 7. 第五阶段：为研究者准备快速审计材料

自动生成便于逐条确认的材料。

推荐以 sample_id 为单位组织四条件结果，但在研究者完成该样本各条件的独立判断后，再展示条件间比较。

每条轨迹展示：

- 原图
- 完整工具调用顺序
- 每步关键工具输出
- 最终 STOP 和 reasoning
- Agent 的八项主要判断
- 具体证据引用
- Agent 标注置信度
- 人工确认或修改位置

对 CALL 审计，优先显示调用时的 evidence gap 和所选工具，而不是要求研究者重新阅读整个日志。

可以生成本地 HTML 审计页面、Markdown review packet 或适合表格筛选的 CSV。优先复用项目已有审计工具，不要为 UI 重构原项目。

研究者必须能够：

- 接受 Agent 标签
- 修改 Agent 标签
- 标记证据不足
- 添加人工理由
- 暂存、继续审核

Agent 不得自动执行“人工确认”。

输出：

`audit_assist/HUMAN_REVIEW_GUIDE.md`

及所需审计材料。

---

## 8. 第六阶段：完成独立预审后进行配对分析

此阶段才允许比较同一张图片的四条件轨迹。

重点分析：

### FULL vs PROBE-MASK

是否隐藏 PROBE 后，Actor 仍能合理选择其他工具、处理冲突和综合证据。

### FULL vs PROBE-DELAY

Actor 在 PROBE 首步被禁止后，选择的替代工具是否符合证据需求。

### FULL vs TOOL-RENAME

重点区分：

- 工具选择变化，但各自合理。
- 工具选择变化，导致可验证的信息缺口。
- 匿名名称引起机械选择或不合理调用。
- 工具预算耗尽导致终态失败。
- 最终解释未合理使用已取得的证据。

不能把首选工具分布变化直接当成 SFT 必要性证据。

输出：

`audit_assist/PAIRED_CONDITION_ANALYSIS.md`

分析中每一项关键结论都必须能追溯到 sample_id 和 trajectory step。

---

## 9. 第七阶段：人工确认与最终解盲

Agent 预审结束后，先停止并提交复核材料。

研究者完成：

- 80 条 trajectory 全部人工确认。
- P0 CALL 全部重点复核。
- P1 CALL 按保留清单进行复核，并记录实际覆盖率。
- P2 CALL 分层抽查。
- 所有未解决争议记录的最终裁决。

研究者可以参考 Agent 标签，但最终结果必须明确记录为人工确认，不能把未查看的 Agent 标签直接复制成 human label。

人工审计记录需要具备：

```text
reviewer_type
review_status
human_label
human_notes
reviewed_at
```

经人工确认后，才将相应标签写入原评估器要求的字段。写入前备份原文件，保留 Agent 原始预审记录及对应关系。

标签锁定之前，不查看 GT 和分类正确性。

完成并锁定人工标签之后，才运行包含 GT 的最终指标评估。

如果无法完成要求的人工复核，报告必须明确说明实际覆盖率，并保留 `INCONCLUSIVE`，不得声称完成 full human audit。

---

## 10. 最终决策分析

完成必要人审后，重新评估：

- Tool-selection quality
- Premature STOP
- Conflict handling
- Evidence sufficiency
- Evidence-to-verdict consistency
- Reasoning faithfulness
- Unsupported claim rate
- TOOL-RENAME sensitivity

区分以下三种结果：

### ACTOR_B0_D_PASS_NO_SFT

未发现稳定、重复、实质性的 Actor 策略缺陷。

### ACTOR_B1_SFT_JUSTIFIED

人工确认存在跨样本的结构性推理或取证策略缺陷，并能够明确指出需要训练的能力。

### ACTOR_B0_D_INCONCLUSIVE

人工证据不足、关键记录无法评估，或存在无法解释的相互矛盾结果。

不得根据某个临时设定的 Accuracy 或工具选择百分比自动决定 SFT。

需要 SFT 时，仅生成：

`ACTOR_B1_SFT_TARGETS.md`

禁止直接训练。

---

## 11. 最终输出目录

```text
actor_b0_d/
└── audit_assist/
    ├── INPUT_VALIDATION.md
    ├── PROTOCOL_AMENDMENT.md
    ├── trajectory_agent_review.jsonl
    ├── call_agent_review.csv
    ├── HUMAN_REVIEW_QUEUE.csv
    ├── HUMAN_REVIEW_GUIDE.md
    ├── PAIRED_CONDITION_ANALYSIS.md
    ├── AGENT_AUDIT_REPORT.md
    └── review_packets/
```

`PROTOCOL_AMENDMENT.md` 必须明确记录：本轮从原来的全量逐次人工 CALL 标注，调整为 Agent 全量预标、风险优先人工复核和分层随机抽查。

不得将这种流程称为 827 次独立人工标注。

保留当前冻结版本、原始轨迹、审计记录及所有 SHA-256。

逐样本结果继续保持 Git ignored。

## 12. 结束条件

完成 80 条 trajectory 和 827 次 CALL 的全量 Agent 预审，生成审计报告与人工复核包后停止。

报告必须展示：

- 实际成功预审数量
- 各类标签分布
- High / Medium / Low confidence 分布
- P0 / P1 / P2 的数量及去重数量
- 需要研究者确认的具体记录
- 缺失证据或不可审计记录
- 目前仍不能确定的能力缺陷

最终保留：

`ACTOR_B0_D_INCONCLUSIVE`

直到研究者完成必要人工确认。

**不得自行声称完成真实人工审计，不得启动 SFT，不得启动 Monitor，不得因预审结果修改冻结 Actor。**