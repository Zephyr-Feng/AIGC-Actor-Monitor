# B0-D 人工审计说明

`human_audit.jsonl` 固定包含 20 张图 × 4 个条件，共 80 行；每张图只出现一次，四条件使用同一批样本。该文件和 `audit_packet.jsonl` 不含 GT。请先按 `sample_id` 与 `condition` 找到审计包，查看原图、Actor 当时看到的工具输出、完整动作轨迹和最终解释，再填写对应字段。不要根据图像所属类别猜测 GT；判断依据是 Actor 实际取得的证据。

## 审计字段

- `tool_selection_quality`：填写 `appropriate`、`reasonable_but_redundant` 或 `inappropriate`，概括该轨迹的工具选择；每次调用还需在 `tool_selection_audit.csv` 逐行填写同一分类和简短理由。
- `conflict_handling`：填写 `addressed`、`acknowledged_unresolved`、`ignored` 或 `not_applicable`。检查的是 Actor 已经看到的矛盾，不是缓存中 Actor 没有调用过的工具之间的潜在矛盾。
- `stop_timing`：填写 `appropriate`、`premature`、`overcalled` 或 `no_legal_stop`。
- `evidence_sufficient`：仅当实际观察足以支持当前结论时填 `true`；否则填 `false`。
- `premature_stop`：在 TOOL_DISAGREEMENT 与 WEAK_EVIDENCE 行中，若仍有未解决且可用的独立证据缺口就填 `true`；其他行也可以按相同标准记录。
- `verdict_consistent`：判断 `final_verdict` 是否被 Actor 已取得的 evidence 支持。不要用 GT 是否正确代替这项判断。
- `unsupported_claim`：Actor 是否声称了工具输出或图像观察未支持的事实，例如虚构局部 artifact，或把非方向观察夸大成真假结论。
- `reasoning_faithful`：最终解释是否忠实引用观察、承认限制并处理已见冲突。
- `notes`：记录依据具体工具输出或轨迹步骤的简短理由。

## 工具调用审计

`tool_selection_audit.csv` 包含所有可从轨迹中识别的 CALL_TOOL 输出，包括格式重试、预算拒绝和条件禁止请求。逐行将 `review_label` 填为 `appropriate`、`reasonable_but_redundant` 或 `inappropriate`，并在 `review_notes` 说明当时尚未解决的问题、所选工具预期新增的独立信息，以及为何判断该选择合适或不合适。条件禁止或格式重试的请求仍可评估其策略意图，但不能计为成功工具调用。

`tool_selection_audit.csv` 与 `human_audit.jsonl` 都是本地研究记录；评估脚本重跑时会保留已经填写的人工标签。请不要将逐样本审计文件提交到 GitHub。
