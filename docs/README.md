# 文档导航

## 现行入口

- [项目主方案](Actor_Monitor_MVP_Protocol.md)：Evidence-Grounded Actor–Monitor Framework；后续研究路线以此为准。
- [项目进度与交接](PROJECT_PROGRESS.md)：已完成工作、当前限制、远端续跑位置和下一步。
- [FaithBench与离线Monitor下一阶段入口](FAITHBENCH_NEXT_STAGE_ENTRY.md)：可先执行的无卡准备、开发标签边界与正式实验前待确认事项。
- [FaithBench开发与离线Monitor v0](../experiments/faithbench_monitor_v0/README.md)：已完成的中文标注规范、隔离输入、输出Schema与引用校验；[阶段报告](../experiments/faithbench_monitor_v0/PREPARATION_REPORT.md)。
- [Actor-B 当前执行决策](ACTOR_B_EXECUTION_DECISION.md)：Structured Actor-B0 的冻结边界、30 图 sanity 集和进入 SFT 的门槛。
- [B0-D Agent 辅助审计](../experiments/actor_b/actor_b0_d/audit_assist/AGENT_AUDIT_PLAN.md)：隔离预审、风险CALL队列和[人审指南](../experiments/actor_b/actor_b0_d/audit_assist/HUMAN_REVIEW_GUIDE.md)。
- [仓库协作原则](../AGENTS.md)：研究决策、未提交工作、GPU 与服务器操作约束。

## 已有证据与实验记录

- [PROBE Evidence-Only v1](../experiments/probe_evidence_v1/REPORT.md)：证据卡、图块及冻结验证。
- [Actor-0](../experiments/actor0/REPORT.md)：旧 prompt-only Actor 的结果与过程风险。
- [Mini FaithBench v0 第三轮技术小样](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)：归因和 STOP 契约的未解决问题。
- [异构工具筛选](../experiments/toolbox_screening/REPORT.md)：工具准入、互补性与局限。

上述结果属于新方案的前期证据；不自动等同于正式 FaithBench、冻结主 Actor 或 Monitor 基线。

## 历史方案与阶段材料

- [MVP v2 快照](archive/Actor_Monitor_MVP_Protocol_v2.md)、[MVP v1 快照](archive/Actor_Monitor_MVP_Protocol_v1.md)：已被现行方案替代，保留决策脉络。
- [旧版研究协议](RESEARCH_PROTOCOL.md)：MVP v2 的固定检查点动作和数据契约；相关评估代码仍在仓库中。
- [Stage 0 复用审计](STAGE0_REUSE_AUDIT.md)、[Stage 1 专家筛选](STAGE1_EXPERT_SCREEN.md)、[MLLM 工具复用评审](MLLM_TOOL_REUSE_REVIEW.md)：候选工具与既有基线的历史核对。
- [旧进度归档](archive/PROJECT_PROGRESS_20261006_precompact.md)：详细时间线和早期服务器记录，以当前进度页为续跑依据。

其余 `docs/` 下的报告和 SOP 保留原路径，作为对应实验的历史记录。实施新方案前，先核对这些材料的日期、数据范围和协议版本。
