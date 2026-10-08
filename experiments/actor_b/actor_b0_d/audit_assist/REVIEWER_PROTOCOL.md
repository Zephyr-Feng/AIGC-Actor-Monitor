# 隔离 Agent 预审规则

本文件落实 AGENT_AUDIT_PLAN.md。审计只判断 Actor 已可观察的决策与证据；不推测内部隐藏思维，不使用 GT、准确率、历史 detector 表现、诊断类别或同图另一条件。

## 隔离顺序

每个审计 Agent 仅可访问分配条件的 tools.json、calls.jsonl、trajectories.jsonl 及其中指向的中性图像/裁片。不得读取 identity_map、原始评估目录、其他条件、项目进度、任务历史或含准确率的报告。

先对 calls.jsonl 按轨迹内时间顺序审阅并保存全部调用标签。每次仅依据该记录的 before-context 和 Actor request；不能读取该次或未来工具 observation、最终 STOP。call_outcome 是运行事件，不能用来倒推工具是否适合。调用审计保存后再读取本条件的 20 条完整轨迹，逐条加载原图和实际已观察的裁片，生成八项预审。独立结果锁定后才由协调者作配对比较。

## 判断边界

- 单次预期无标签的工具探索可能合理，工具最终方向错误不等于调用不合理。
- 非方向全局偏离只表示相对参考分布的异常程度；不能当工具 real/fake verdict。
- 缺失 metadata、没有发现异常或 inconclusive observation，不自动证明真实或伪造。
- 从多个来源综合形成的 Actor interpretation 可以是结论，但不得改写成工具原始 observation。
- 冲突只指当时实际观察到的互相不一致证据。继续调用不自动等于实质处理；检查最终理由是否承認或合理综合矛盾。
- premature_stop=true 需要重要尚未解决的信息缺口，以及当时仍可调用、能补充该信息的独立来源和预算。剩余工具未用完不自动是提前停止，预算耗尽后无可用来源也不能单凭冲突标提前停止。
- 多工具调用/引用数量不证明充分性或忠实度。evidence_sufficient 判断观察能否支持当前结论及其强度，而非证明绝对真实性。
- 对缺源或不可确定字段填 unassessable，并记录 needs_source/原因。不得给缺源记录 high confidence。具体区域伪影若不能从图像/裁片或实际 observation 核验，不得自行补足。
- 不设置临时准确率阈值或调用比例阈值，不作 SFT gate 决定。

## 调用输出

每个输入 record_id 必须恰有一个输出，保存到本条件 call_reviews.jsonl。字段包括 record_id、sample_id（blind ID）、condition、trajectory_step、raw_attempt、agent_label（appropriate/reasonable_but_redundant/inappropriate/unassessable）、agent_confidence（high/medium/low）、agent_reason（中文）、evidence_gap、expected_information_gain、call_outcome、evidence_references（明确 before/step_N/tool_observation 等路径）、review_priority（P0/P1/normal）、needs_source、observed_conflict、upstream_error_group（适用时）。禁止自动填 human_label。

每个理由必须解释当前已有观察、Actor 明确的缺口和所选功能之间的关系，不能只是复述通用模板或用未来结果合理化调用。重试/预算拒绝要区分同一上游错误的衍生请求与独立错误。

## 轨迹输出

20 个输入 key 各写一个 trajectory_reviews.jsonl 输出。字段 sample_id（blind ID）、condition、agent_review（tool_selection_quality、conflict_handling、stop_timing、evidence_sufficient、premature_stop、verdict_consistent、unsupported_claim、reasoning_faithful）、confidence、evidence_references、notes（中文）、review_priority、needs_source、reviewer_type=agent、review_status=agent_proposed。八项取值遵循用户方案；信息不足的字段可为 unassessable。不要把条件之间的比较写进独立判断。

证据引用至少覆盖支持标签的关键动作/observation/最终理由，并在 notes 中写出具体支持或矛盾的内容。模型预审不称人工审计。
