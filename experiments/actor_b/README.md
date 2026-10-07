# Actor-B

本阶段按用户提供的 [Schema 收尾、Held-out 确认与冻结决策方案](../../docs/ACTOR_B_SCHEMA_HELDOUT_PLAN.md) 执行。人工归因复核口径见 [AUDIT_PROTOCOL.md](AUDIT_PROTOCOL.md)。

本目录实现现行方案 Phase I 的最小 Structured Actor-B0。它复用冻结的 Qwen3-VL-8B-Instruct、取证工具、PROBE Evidence-only v1 语义、原始图像和既有工具结果，不修改 Actor-A、Mini FaithBench 或任何 detector。

执行顺序：

1. `prepare_b0_subset.py` 从既有 Actor dev 中固定选择 30 张、30 个互不重复来源组，RAISE/FLUX/SD3.5 各 10 张，并移除旧 PROBE 分类输出。
2. `extract_b0_probe_evidence.py` 在 RTX 4090 上复用冻结 checkpoint、预处理和参考库，为这 30 张生成 Evidence-only 卡片与 crops。
3. `merge_b0_evidence.py` 合并 Evidence-only 卡片与既有 PatchCraft、SAFE、Provenance 输出。
4. `run_b0.py` 在同一 RTX 4090 上运行 prompt-only Structured Actor-B0。
5. `evaluate_b0.py` 生成固定指标和 `ACTOR_B0_BASELINE_REPORT.md`，只做一次是否需要 SFT 的判断。

以上为原 B0 的执行顺序，报告中的自动 SFT 标签已在轨迹复核后撤回。现行 Schema/Held-out 阶段保留原 system prompt、工具卡与生成配置；parser 允许 schema 原本就许可的 STOP `final_confidence=null`，仍拒绝非法 verdict 与重复调用。原 30 图在独立目录完整复跑；工程指标正常后，对 60 图 held-out 运行同一 Actor 配置并按 [人工口径](AUDIT_PROTOCOL.md) 审计。曾增加条件式 schema 文本的候选已因编排退化中止，详见[中止记录](baseline_b0_schema_fixed/SCHEMA_CANDIDATE_ABORTED.md)。

`prepare_heldout.py` 从已有 Actor-0 eval 按来源组固定 60 图，排除 Mini FaithBench 固定 6 图；`reuse_heldout_evidence.py` 复用冻结 Evidence v1 卡片与 crops，只对派生卡片调整 callable 名称。60 图已完成，parse 55/60，低于预定冻结门槛；本轮单次决策为 `ACTOR_B1_SFT_REQUIRED`，详见[最终决策](ACTOR_B_FREEZE_DECISION_REPORT.md)和[触发报告](ACTOR_B_SFT_TRIGGER_REPORT.md)。当前不运行正式 900 条、不训练 Actor、不开发 Monitor。原 B0 结果见 [B0 报告](baseline_b0/analysis/ACTOR_B0_BASELINE_REPORT.md)和[轨迹复核](baseline_b0/analysis/ACTOR_B0_AUDIT.md)。逐图原始轨迹和输入清单留在本地及获授权的 AutoDL 实例，不上传 GitHub。

