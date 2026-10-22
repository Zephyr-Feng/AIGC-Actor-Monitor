# 文档导航

**推荐直接阅读：** [导师阅读稿：总览＋六个完整案例，图片已内嵌，可离线转发](MONITOR_ACTOR_ADVISER_READING_COPY_20261021.html)。


## 现行入口

- [Monitor净收益目标与公平比较设计](MONITOR_NET_GAIN_PLAN_20261021.md)：已核对历史自然005正例，区分旧DeepSeek反馈效果与当前本地候选待验证收益。

- [导师阅读版：简明总览＋完整案例](MONITOR_ACTOR_READABLE_REPORT_20261021.html)（[Markdown](MONITOR_ACTOR_READABLE_REPORT_20261021.md)）：六个导读案例，全部120分支完整记录，含原图/图块、原稿、证据、反馈、实际响应和两组完整最终稿；另列15自然整稿。

- [2026-10-21纯Actor同105题补充对照](ACTOR_ONLY_COMPARISON_REPORT_20261021.md)（[可打印HTML](ACTOR_ONLY_COMPARISON_REPORT_20261021.html)）：A0/A1/M、115新增生成、逐例结果与9样例；纯Actor候选能改错，落地差距含接口因素。

- [2026-10-21导师版105题测试报告](MONITOR_ACTOR_TEST_REPORT_20261021.md)（[可打印HTML](MONITOR_ACTOR_TEST_REPORT_20261021.html)）：105条配对、120闭环分支、451次生成；完整结果、样例、收益和失败边界。

- [2026-10-21项目阶段总结](PROJECT_SUMMARY_20261021.md)：研究MVP、最新定向Monitor与Actor控制结果、失败经验和未解决事项；当前执行状态以项目进度顶部为准。

- [2026-10-18最新交接](SESSION_HANDOFF_20261018.md)：反馈SFT与80条完整验收已交付，模型明显进步但不晋级；用户已同意既有候选仅CPU自然全文反馈建设，新对话直接接续，不自动训练或增加预算。
- [2026-10-17反馈SFT完整报告](../experiments/faithbench_monitor_v0/monitor_quality_v2/FEEDBACK_REPORT_20261017.md)：格式/受控核对改善、五核心和自然全文纠错仍未过，最终adapter/raw/审阅均已回收，可关卡；独立/领域/Actor收益未验证。

- [Monitor D2开发闭环结果](../experiments/faithbench_monitor_v0/monitor_mechanism_v1/REPORT_D2_20261013.md)：12分支已完成退出，M/G原核心均5/5修复，M未多修复非接口核心且局限遗漏/028新增方向误用，事前门槛未通过；未读GT或证明完整机制，GPU可关。
- [Monitor D2冻结方案](../experiments/faithbench_monitor_v0/monitor_mechanism_v1/PLAN_D2_DEVELOPMENT_CLOSED_LOOP_20261013.md)：用户已确认范围、门槛和预算并执行完成；保留事前条件，不是续跑入口。
- [Monitor D1b显式契约补充结果](../experiments/faithbench_monitor_v0/monitor_mechanism_v1/REPORT_D1B_20261013.md)：8请求完成，M2通过四个已曝光案例的原开发门槛；尚未验证Actor采纳或检测损害，最终机制goal active。
- [Monitor D1开发比较结果](../experiments/faithbench_monitor_v0/monitor_mechanism_v1/REPORT_D1_20261013.md)：8请求完成，M1原核心5/5修正，但未决处理失败，未过完整开发门槛；最终机制goal active。
- [Monitor机制有效性验证路线](research/MONITOR_MECHANISM_VALIDATION_ROADMAP_20261013.md)：主目标为证据推理改善并核查检测损害；D1/D1b/D2已完成，当前限制与接续以最新D2报告、进度为准。
- [DeepSeek四例归因复核](../experiments/faithbench_monitor_v0/independent_evaluation_v1/ATTRIBUTION_REVIEW_20261013.md)：事实核对与数值修正有明确错误，成功有parser提示，部分意见仍依赖未定判据；离线复核不改旧评分、不启动新实验。
- [DeepSeek自然30组初步能力结果](../experiments/faithbench_monitor_v0/independent_evaluation_v1/REPORT.md)：单次30/30正常结束，助手初评显示局部能力、整体纠错仍不稳定；非人审gold、无正式可靠性通过。
- [Actor-B→DeepSeek离线验证执行准备](../experiments/faithbench_monitor_v0/independent_evaluation_v1/EXECUTION_PLAN.md)：自然30组Actor/DeepSeek审核及初评已完成，GPU/API退出；找全核心10/23、可用反馈5/23、新增错误4/30。
- [74保留组元数据审计](../experiments/faithbench_monitor_v0/independent_evaluation_v1/RESERVED_METADATA_AUDIT.md)：74组222图均有旧Actor-0轨迹及Evidence-only卡；所查当前Actor-B保留轨迹为0，旧/当前协议不同，31组有旧审阅记录；未选样或运行模型，接续需确认协议与新增轨迹范围。
- [独立Monitor启动与无卡准备记录](../experiments/faithbench_monitor_v0/independent_evaluation_v1/PREPARATION.md)：用户已要求启动，6张判据卡与库存核查已完成，后续限定元数据审计已完成；独立样本/研究者复核前提未满足，API批次未启动。
- [DeepSeek独立Monitor评价方案（2026-10-13）](research/DEEPSEEK_MONITOR_INDEPENDENT_EVALUATION_PLAN_20261013.md)：已进入自然30组/助手初评执行，原配额与候选门槛不套用；正式可靠性及独立人审尚未证明。
- [2026-10-12交接](SESSION_HANDOFF_20261012.md)：最新接续入口。FULL20闭环完成停止；当前讨论如何确定DeepSeek独立Monitor的评判标准，新样本/门槛/实验未确认。以下更早记录中的运行中/待确认/goal状态属于历史，不作为自动执行指令。
- [FULL20 DeepSeek→Actor闭环报告](../experiments/actor_b/deepseek_monitor_pilot_v1/REPORT.md)：A/B/C有效正确14/13/6，C9失败，无检测收益；部分修正增加，完整联合仍0，部署和接口争议已披露。
- [DeepSeek与8B六例审核报告](../experiments/faithbench_monitor_v0/model_comparison_v1/REPORT.md)：DeepSeek核心定位有改善，截断/接口缺口使完整候选条件未通过。
- [正确反馈单例三分支报告](../experiments/actor_b/feedback_pilot_v1/REPORT.md)：主要证据误用修复并提出CALL，未执行补证或验证最终检测收益。

- [事实表12次配对诊断结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BINDING_TABLE_PROBE_V1_20261011.md)：两组完整无截断，标签均5/6，条件/理由/标签4/6→3/6、完整联合3/6→2/6；明确缺失仍误支持，新增条件与理由矛盾。0训练，GPU已退出可关卡；继续讨论可核验条件步骤，完整目标未解决。

- [既有六例输出前缀事后核查](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BINDING_COMPACT_PREFIX_AUDIT_20261011.md)：三截断前缀40/40值抄对，不能证明缺失/对象/关系正确；空白计数不修补raw或推断未生成答案。

- [六例紧凑绑定模型预检结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BINDING_COMPACT_PROBE_V1_20261011.md)：6推理/0训练，3简单关系联合正确，3复杂输出截断；第三值缺失仍错误标全体100条件满足，未完成最终标签。纯提示未稳定执行绑定/缺失步骤，目标未解决；raw/审阅备份完成、worker退出GPU0，已通知关卡。

- [六例绑定草稿输出长度核查](research/MONITOR_EVIDENCE_BINDING_LENGTH_AUDIT_20261011.md)：CPU准确紧凑正文228–616token，3例超过旧384预算且末尾判断在预算外；先讨论减少重复信息并保留必要绑定/核验，未生成简化目标或改预算，无需GPU。

- [6个证据绑定与关系核验草稿](research/MONITOR_EVIDENCE_BINDING_DRAFTS_20261011.md)：已获用户批准，复用训练72中的6例，保留原事实/主张/Actor/标签，先明确对象与字段实际值或缺失，再核验关系。16字段/6身份绑定、同助手六例核读及两缺失兼容反例对通过；0模型调用/训练，无需开卡。当前讨论监督形式和输出复杂度，尚未模型验证或采用新接口。

- [现有SFT事后诊断](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_POSTHOC_AUDIT_20261011.md)：20失败连训练曝光，缺失监督确实存在；已覆盖关系回归两adapter均29/32，未覆盖迁移与引用失败需区分。144目标新增962token全部理由，判断值占比变化不能证明因果；0新请求/训练/监督材料，6个新监督草例仍待确认。

- [两种理由监督SFT结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_COMPARISON_V1_20261011.md)：432更新、204新推理+48旧raw精确复用、252首审复审完成。原48联合41→普通45/关系43，预留36联合34→32/28，两组未达候选门槛，不默认采用；证据绑定/缺失仍失败。两个adapter/raw/日志已备份核hash、进程退出GPU0，已通知关卡。当前接续该报告讨论下一阶段，完整goal未完成；不重跑。

- [关系监督材料完成报告](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_MATERIALS_20261011.md)：有效v2，72训练/36整组预留及216目标审阅/CPU检查完成；v1停用保留。该无卡阶段0请求，后续两组训练已获批准并完成，结果见顶部。

- [提示对照结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_PROMPT_PROBE_V1_20261011.md)：192新请求完成保存，base标签+理由33→43/41（每版48），旧adapter31→30/36且96条不遵守理由先顺序；该阶段0训练，局部修复伴随失败，未解决目标。后续材料及两组训练现已完成，不重跑提示请求。

- [关系前测结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_PROBE_V2_20261011.md)：96请求完成，标签与理由联合base33/48、v3 31/48，5显式矛盾及属性/全称/目标漂移；[提示对照执行冻结](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_RELATION_PROMPT_PROBE_V1_20261011.md)对应192已完成新请求，0新训练。

- [证据关系前测执行记录](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_RELATION_PROBE_V2_20261011.md)：12组/9关系簇、48条抽象开发材料、base/v3共96次前测已完成保存，不重跑；当时未训练，当前以顶部SFT结果为准。

- [2026-10-11最新交接](SESSION_HANDOFF_20261011.md)：基础筛查、输入分组/局部校验及12片段扩大验证已完成保存；分组减少adapter内容误支持，但数量推理、引用和base误拒绝仍有失败，候选未默认采用。

- [2026-10-10历史交接](SESSION_HANDOFF_20261010.md)：三轮SFT、中文NLI及结构展示失败、来源范围引用候选背景；续跑状态以10月11日交接与当前进度为准。
- [2026-10-09历史交接](SESSION_HANDOFF_20261009.md)：原8B/27B v2与隔离部署细节；旧地址、进程和待执行步骤不作为当前续跑指令。
- [Monitor pilot v2](../experiments/faithbench_monitor_v0/pilot_v2/README.md)：现行8例开发接口与文件分工；[27B运行报告](../experiments/faithbench_monitor_v0/pilot_v2/RUN_REPORT_27B_20261009.md)记录6/8完整接口及语义限制，[准备报告](../experiments/faithbench_monitor_v0/pilot_v2/PREPARATION_27B_20261009.md)保留来源/部署校验。

- [项目主方案](Actor_Monitor_MVP_Protocol.md)：Evidence-Grounded Actor–Monitor Framework；后续研究路线以此为准。
- [项目进度与交接](PROJECT_PROGRESS.md)：已完成工作、当前限制、远端续跑位置和下一步。
- [FaithBench与离线Monitor下一阶段入口](FAITHBENCH_NEXT_STAGE_ENTRY.md)：可先执行的无卡准备、开发标签边界与正式实验前待确认事项。
- [FaithBench开发与离线Monitor v0](../experiments/faithbench_monitor_v0/README.md)：已完成的中文标注规范、隔离输入、输出Schema与引用校验；[阶段报告](../experiments/faithbench_monitor_v0/PREPARATION_REPORT.md)。
- [Actor-B 当前执行决策](ACTOR_B_EXECUTION_DECISION.md)：Structured Actor-B0 的冻结边界、30 图 sanity 集和进入 SFT 的门槛。
- [B0-D Agent 辅助审计](../experiments/actor_b/actor_b0_d/audit_assist/AGENT_AUDIT_PLAN.md)：隔离预审、风险CALL队列和[人审指南](../experiments/actor_b/actor_b0_d/audit_assist/HUMAN_REVIEW_GUIDE.md)。
- [仓库协作原则](../AGENTS.md)：研究决策、未提交工作、GPU 与服务器操作约束。

## 已有证据与实验记录

- [输入分组12片段扩大验证](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BOUNDARY_EXPANSION_V1_20261011.md)：38新增+10旧raw复用、48条件；adapter三语义误支持消失，但存在标签正确理由错、列表漏引、base误拒绝和2输出预算失败，不构成独立泛化验证。
- [Monitor v3 SFT复盘](../experiments/faithbench_monitor_v0/sft_evidence_contract_v3/REPORT_20261010.md)：格式改善，但决定性证据绑定与未知判别不可靠，adapter不采用。
- [Monitor跨阶段失败原因排查](research/MONITOR_FAILURE_CAUSAL_AUDIT_20261010.md)：训练监督/执行检查、文献方法与未确定的因果解释。
- [中文NLI CPU实测](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_NLI_CPU_20261010.md)、[结构展示25次诊断](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_STRUCTURED_SOURCE_V2_20261010.md)：已实际运行并细审复审，不能作为默认方案或教师。
- [完整来源/数组引用候选](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_SOURCE_SCOPE_CANDIDATE_20261010.md)：已完成CPU准备与复审，待引用规范确认，尚未接入完整Monitor或证明模型效果。

- [PROBE Evidence-Only v1](../experiments/probe_evidence_v1/REPORT.md)：证据卡、图块及冻结验证。
- [Actor-0](../experiments/actor0/REPORT.md)：旧 prompt-only Actor 的结果与过程风险。
- [Mini FaithBench v0 第三轮技术小样](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)：归因和 STOP 契约的未解决问题。
- [异构工具筛选](../experiments/toolbox_screening/REPORT.md)：工具准入、互补性与局限。

上述结果属于新方案的前期证据；不自动等同于正式 FaithBench、冻结主 Actor 或 Monitor 基线。

## 历史方案与阶段材料

- [2026-10-08交接](SESSION_HANDOFF_20261008.md)、[首轮Monitor试做入口](MONITOR_PILOT_ENTRY_20261009.md)：早期STOP讨论与v1设置；其中执行状态已被10月9日交接及v2记录更新。
- [MVP v2 快照](archive/Actor_Monitor_MVP_Protocol_v2.md)、[MVP v1 快照](archive/Actor_Monitor_MVP_Protocol_v1.md)：已被现行方案替代，保留决策脉络。
- [旧版研究协议](RESEARCH_PROTOCOL.md)：MVP v2 的固定检查点动作和数据契约；相关评估代码仍在仓库中。
- [Stage 0 复用审计](STAGE0_REUSE_AUDIT.md)、[Stage 1 专家筛选](STAGE1_EXPERT_SCREEN.md)、[MLLM 工具复用评审](MLLM_TOOL_REUSE_REVIEW.md)：候选工具与既有基线的历史核对。
- [旧进度归档](archive/PROJECT_PROGRESS_20261006_precompact.md)：详细时间线和早期服务器记录，以当前进度页为续跑依据。

其余 `docs/` 下的报告和 SOP 保留原路径，作为对应实验的历史记录。实施新方案前，先核对这些材料的日期、数据范围和协议版本。
