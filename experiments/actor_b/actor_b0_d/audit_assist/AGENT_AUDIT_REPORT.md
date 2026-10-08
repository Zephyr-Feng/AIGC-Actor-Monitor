# Actor-B0-D Agent 辅助审计报告

当前 gate：ACTOR_B0_D_INCONCLUSIVE。

仅为全量模型预审；真实人工确认数为0。没有读取GT或重新运行含GT评价。

完成80/80条轨迹、827/827次CALL预审。缺源轨迹0，缺源调用0。

## 预审分布

CALL标签：{'appropriate': 812, 'reasonable_but_redundant': 2, 'inappropriate': 13}
CALL置信度：{'high': 488, 'medium': 339}
轨迹置信度：{'medium': 59, 'high': 21}

- tool_selection_quality: {'appropriate': 77, 'reasonable_but_redundant': 1, 'inappropriate': 2}
- conflict_handling: {'not_applicable': 54, 'acknowledged_unresolved': 26}
- stop_timing: {'appropriate': 60, 'no_legal_stop': 4, 'premature': 14, 'overcalled': 2}
- evidence_sufficient: {'false': 47, 'true': 32, 'unassessable': 1}
- premature_stop: {'false': 62, 'true': 18}
- verdict_consistent: {'true': 79, 'false': 1}
- unsupported_claim: {'true': 31, 'false': 49}
- reasoning_faithful: {'false': 31, 'true': 49}

## 条件内预审统计

以下为独立Agent提议，不是正确率或已验证缺陷率；字段可能重叠。不同审计Agent的尺度差异需人审裁决。

| 条件 | CALL/轨迹 | 证据不足 | 提前停止 | 无支持断言 | 不忠实 | 原始无合法STOP |
|---|---:|---:|---:|---:|---:|---:|
| FULL | 189/20 | 16 | 7 | 7 | 7 | 2 |
| PROBE-MASK | 180/20 | 10 | 0 | 15 | 15 | 0 |
| PROBE-DELAY | 233/20 | 15 | 9 | 7 | 7 | 2 |
| TOOL-RENAME | 225/20 | 6 | 2 | 2 | 2 | 0 |

## 人工队列

80条轨迹全部需要真实人工确认。CALL去重队列243条，优先级{'P1': 212, 'P0': 13, 'P2': 18}。
各入选理由计数（可能重叠）：{'paired_first_divergent_choice': 70, 'decision_after_observed_conflict': 63, 'agent_redundancy': 2, 'delay_blocked_first_request': 28, 'delay_following_choice': 28, 'agent_inappropriate': 13, 'rename_first_tool': 60, 'stratified_random_check:FULL:complementary_forensic_analyzer:late': 1, 'stratified_random_check:FULL:global_forensic_analyzer:first': 1, 'stratified_random_check:FULL:global_forensic_analyzer:middle': 1, 'stratified_random_check:FULL:local_texture_analyzer:middle': 1, 'stratified_random_check:FULL:provenance_inspector:middle': 1, 'stratified_random_check:PROBE-DELAY:complementary_forensic_analyzer:late': 1, 'stratified_random_check:PROBE-DELAY:complementary_forensic_analyzer:middle': 1, 'stratified_random_check:PROBE-DELAY:global_forensic_analyzer:late': 1, 'stratified_random_check:PROBE-DELAY:global_forensic_analyzer:middle': 1, 'stratified_random_check:PROBE-DELAY:local_texture_analyzer:middle': 1, 'stratified_random_check:PROBE-DELAY:provenance_inspector:first': 1, 'stratified_random_check:PROBE-DELAY:provenance_inspector:late': 1, 'stratified_random_check:PROBE-DELAY:provenance_inspector:middle': 1, 'stratified_random_check:PROBE-MASK:complementary_forensic_analyzer:middle': 1, 'stratified_random_check:PROBE-MASK:local_texture_analyzer:first': 1, 'stratified_random_check:PROBE-MASK:local_texture_analyzer:middle': 1, 'stratified_random_check:PROBE-MASK:provenance_inspector:first': 1, 'stratified_random_check:PROBE-MASK:provenance_inspector:middle': 1}；累计理由命中282，去重后243。
所有80条终态均纳入证据充分性复核，包含WEAK_EVIDENCE停止判断；不把诊断类别提供给独立预审Agent。
P0全部保留，P1按完整保留清单，P2按condition×工具×step位置分层每个非空层随机抽1，固定seed20261007。
P2剩余高置信候选数：{'FULL': 121, 'PROBE-MASK': 150, 'PROBE-DELAY': 113, 'TOOL-RENAME': 0}。TOOL-RENAME调用均为medium，严格P2没有候选；其首次选择全量通过P1保留。该P2四条件覆盖例外已提交研究者确认，不自行提高Agent置信度或扩展抽样门槛。
150–250为工作量目标；如果高风险队列超过250，仍保留全部记录，不为凑数删去高风险请求。
本轮CALL队列处于250条以内。

## 未确定事项

策略、冲突综合、提前停止和证据忠实度的Agent判断需研究者确认。高置信预审也不是人类验证。具体记录见私有HUMAN_REVIEW_QUEUE.csv和PAIRED_CONDITION_ANALYSIS.md。

审计输入不提供GT/类别/来源文件名；隔离条件先审调用前状态，锁定后再审完整轨迹，最后配对。所有逐样本材料仅本地保存。

验证：四条件调用/轨迹源与结果SHA锁、时间顺序、80/827唯一关联和八字段枚举全部通过；原人工文件SHA未变。离线浏览器加载80条轨迹、图像正常、无JavaScript错误。虚构数据验证确认必填和无法判断标签锁定，不写真实人工标签。

完成并锁定必要人审后，通过import_human_reviews.py导入确认标签；显式--evaluate才运行含GT的最终评价。当前没有SFT或Monitor实验。
