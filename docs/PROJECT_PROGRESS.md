# 项目进度与跨对话交接

> 新对话先读本页、仓库根目录 `AGENTS.md` 和[项目主方案](Actor_Monitor_MVP_Protocol.md)。[文档导航](README.md)区分现行方案与历史材料；详细过程和旧版进度见[2026-10-06 压缩前归档](archive/PROJECT_PROGRESS_20261006_precompact.md)。

## 当前状态（2026-10-07）

- **Actor-B Schema/Held-out 阶段完成，决策为 `ACTOR_B1_SFT_REQUIRED`，未启动训练。** 原 30 图 parser 对齐回归 30/30 合法终态，95/95 合法工具请求，0 重复，30/30 工具序列与旧 B0 一致。独立 60 图 held-out 为 55/60 合法终态（91.67%），低于预定 ≥98% 冻结门槛；189/189 合法工具请求、平均 3.15 次/图、提前 STOP 5/60、0 重复、9 种工具序列。5 条失败均为有限重试后仍非法的 STOP verdict。按[最终决策报告](../experiments/actor_b/ACTOR_B_FREEZE_DECISION_REPORT.md)和[SFT 触发报告](../experiments/actor_b/ACTOR_B_SFT_TRIGGER_REPORT.md)停止本阶段，尚未冻结 Actor、未跑正式 900 条。归因审计见[30 图](../experiments/actor_b/baseline_b0_schema_fixed_v2/analysis/MANUAL_AUDIT_30.md)和[60 图](../experiments/actor_b/heldout_confirmation/analysis/MANUAL_AUDIT_60.md)；归因本身未用于触发 SFT。
- **Actor-B0 原 30 图 sanity（历史记录）。** 30/30 PROBE Evidence-only、30/30 B0 推理完成；28/30 有合法最终输出，95/95 工具调用请求合法、0 重复，平均 3.17 次/图。两张失败均为 STOP 的 `final_confidence` 为空；9/30 图出现明确把 PROBE 全局偏离标成 `real`/`fake` 的归因错误。小样 balanced accuracy 0.65 仅作诊断。自动评价最初把 `inconclusive` 算作归因违规，50.4% 已撤回；原始“考虑 SFT”标签也因阈值未经确认而撤回。[报告](../experiments/actor_b/baseline_b0/analysis/ACTOR_B0_BASELINE_REPORT.md)、[轨迹复核](../experiments/actor_b/baseline_b0/analysis/ACTOR_B0_AUDIT.md)。
- **Mini FaithBench v0 停在第三轮技术小样。** 按用户最后授权，仅补强 PROBE observation / Actor inference 的归因边界和 STOP 的 `real|fake` 输出说明；固定 6 图×3 条件重跑为 18/18 最终可解析，crop 图像输入、其他工具 callable 和 PROBE 输入结论泄漏检查均正常。但人工复核发现 PROBE 偏离仍被写成真假倾向；一次原始 STOP 仍输出 `final_verdict=uncertain`，虽在下一步重试恢复。按预设门槛**不再叠加 prompt patch、不冻结 prompt、不启动正式 900 条或 SFT**。结论：Prompt-only schema adaptation is insufficient to reliably enforce evidence attribution boundaries。[本轮报告和原始轨迹](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)；[前轮失败](../experiments/mini_faithbench_v0/technical_sample_v2/REPORT.md)。
- **Prompt 版本。** 旧 Actor-0 prompt material SHA-256 `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`；前轮 Evidence-compatible 候选 `cc128afa3e4f6ec0f0cc68509386c2668f6375f551fdc45803369746b6c8882f`；本轮**未冻结候选** `5cc7a1cd8ffda55b7d2b94b7546619944073c933ed1a064c0a2d07c0c94604f2`。完整文件与哈希记录在 `experiments/mini_faithbench_v0/config/`；三条件使用同一候选。
- **PROBE Evidence-Only v1 已完成并冻结。** 独立 RAISE 参考集 100 图、600 patches；固定 `k=20`、percentile、top-3、crops 和 spatial pattern。300 张 eval 图形成 300 份无 classifier 结论的 Evidence Cards 与 900 张 crops；classifier 路径 300/300 与原 PROBE 对齐。[报告与验证](../experiments/probe_evidence_v1/REPORT.md)。
- **Actor-0 已完成。** 100 来源组、300 张 eval 图，Qwen3-VL-8B-Instruct revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`。Actor accuracy 0.950，低于 PROBE-only 0.987；global-only STOP 为 112/300，128 个冲突均未解决。Actor-0 决策为 CONDITIONAL KEEP。[报告](../experiments/actor0/REPORT.md)。
- **研究主线已更新。** 用户提供的[现行主方案](Actor_Monitor_MVP_Protocol.md)以 Evidence-Grounded Actor–Monitor Framework 为核心：先固定结构化 Tool Actor，再构建 FaithBench，先做离线轨迹验证，后做在线 Monitor 干预。Actor-0 保留为较弱 Actor；是否需要轻量 trajectory SFT 取决于基础工具编排验证。旧版同轨迹 `A0/A1/A2` 增量收益与成本预测方案已存入[历史快照](archive/Actor_Monitor_MVP_Protocol_v2.md)，不再作为后续实验指令。当前主 Actor、正式 FaithBench、Monitor 均未完成；专家栈与 Evidence 接口仍需按新方案明确。既有工具筛选结论：PROBE KEEP，PatchCraft/SAFE/Provenance CONDITIONAL，RIGID DROP；FSD/AIDE 不进入主工具箱。[工具筛选报告](../experiments/toolbox_screening/REPORT.md)。

## 续跑位置与约束

- 最近核验的 AutoDL 入口：`connect.bjb3.seetacloud.com:20277`，主机 `autodl-container-px0barc0vk-969e5ef2`。用户提供克隆入口后用现有密钥只读核验，无需使用密码；旧 `bjb1:31805` 入口已拒绝连接。新实例 30 图回归结果、模型、代码、输入及 60 图原图/卡片/crops 均已核验。AutoDL 克隆后入口仍可能改变。**Actor-B 60 图 GPU 推理已完成并正常退出，最后核验为 0 MiB / 0% 利用率；已告知用户可以关卡。**
- Actor-B0 远端隔离目录：`/root/autodl-tmp/actor-b0-20261007/`；30 图原始轨迹还在此目录及本地 `experiments/actor_b/baseline_b0/outputs/`（Git 忽略，不上传 GitHub）。冻结输入及运行哈希见 B0 报告。旧实例的两份派生 JSONL 传输曾获单次授权；用户随后提供新克隆并明确要求在新实例续跑，held-out 输入仅在该实例用于此次实验，仍不上传 GitHub。
- 远端 Mini FaithBench 隔离目录：`/root/autodl-tmp/mini-faithbench-v0/`；独立 Actor venv 为 `transformers==4.57.4`、`accelerate==1.10.1`，PROBE 环境未改。模型与 processor 使用上述同一 revision。三轮小样在 `technical_sample/`、`technical_sample_v2/`、`technical_sample_v3/`；`formal/` 尚无正式轨迹。
- 本地入口：`experiments/mini_faithbench_v0/`（runner、三条件 inputs、benchmark config、prompt 与技术小样）；`experiments/probe_evidence_v1/results/output/`（Evidence v1）；`runs/actor0-bfree-20261002/`（旧 Actor-0 原始结果，忽略目录）。代码和研究文件存在未提交改动，不重置或覆盖。
- 下一步先讨论 B1 轨迹级协议学习方案及所需算力，或另立严格约束解码的工程验证；这两条路径会影响研究结论和用卡开销，尚未获确认。当前不启动 SFT、正式 900 条或新 GPU 实验，不建立 `frozen_actor`。PROBE 归因错误保留为可检测的失败案例。旧实验记录保留在各报告及上述归档，历史 SSH 端口不要当作当前入口。

## 早期阶段索引

| 阶段 | 保留结论 | 详细记录 |
|---|---|---|
| T0 与三动作 pilot | 加入旧 CPU 读数未稳定改善判断；pilot 未观察到有用的动作选择空间。仅为探索诊断。 | [T0](T0_TOOL_CHECK.md)、[pilot](THREE_ACTION_PILOT_CHECK.md) |
| Stage 1 FSD/AIDE/SAFE | 目标域表现未达稳健专家准入；SAFE 官方 DiTFake 正向复现通过，目标域问题不能简单归因于安装失败。 | [Stage 1](STAGE1_EXPERT_SCREEN.md)、[SAFE 正向对照](SAFE_POSITIVE_CONTROL_REPORT.md) |
| SAFE 图块诊断 | 位置有描述性差异，固定阈值下真图误报仍高；未证明总体改进。 | [报告](../SAFE_patch_diagnostic/REPORT.md) |
| PROBE 与异构工具 | PROBE 冻结 300 图表现强，但论文覆盖 FLUX/SD3、训练图逐图重叠未知；工具角色以上方当前状态为准。 | [PROBE](../experiments/probe_dinov2/REPORT.md)、[筛选](../experiments/toolbox_screening/REPORT.md) |
| 存储 | 旧实例曾清理至约 2.8 GB 可用并建议扩容；克隆后空间必须重新核验。 | [存储审计](../experiments/storage_audit/STORAGE_AUDIT_REPORT.md) |

## 2026-10-07 维护记录

独立 held-out 60 图推理在新克隆正常完成，60/60 记录齐全，GPU 最后核验 0 MiB / 0%；轨迹 SHA-256 `276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`，runtime SHA-256 `031c5e1d081abc1fba0b1217e6d3271340f36ec05bd64211df353a497a0aa711`，本地副本与远端一致。评价：parse 55/60（91.67%）、合法工具请求 189/189、平均工具次数 3.15、60/60 实际多步、0 重复、提前 STOP 5/60、9 种工具序列；5 个无效 STOP 为 `inconclusive` 或空 verdict，有限重试后仍失败。人工复核 244 个已接受步骤：显式违规 45、隐含违规 58、涉及 47/60 图；12 图有真实方向工具冲突，其中 2 图因缺少合法终态而无可读的冲突后状态。根据预定 ≥98% parse 冻结条件，单次决策 `ACTOR_B1_SFT_REQUIRED`，但未训练，未冻结，未启动正式 900 条。报告和原始数据位置见当前状态；下一阶段方向需与用户讨论。

AutoDL 新克隆交接：旧运行会话断开后，用户给出 `connect.bjb3.seetacloud.com:20277`；现有密钥连接成功，未使用或记录用户密码。新数据盘已出现完整 30 图回归输出（轨迹 SHA-256 `1ee452bee4aec6328f6bf6d4b82d2d3ccb80a66a1cd03ad2518027aad034aaee`），模型、30/60 图输入及代码哈希与既定版本一致；旧实例入口已拒绝连接。30 图 CPU 评价：`parse_success=1.0`、`legal_tool_call_rate=1.0`、`multi_step_completion_rate=1.0`、`premature_stop_rate=0.0667`、`repeated_tool_call_attempt_rate=0`、`forced_or_missing_final=0`；8 次原始 `uncertain` STOP 均按协议拒绝并在有限重试内修复，未猜测或映射 verdict。30/30 工具调用序列与旧 B0 相同，旧 28 条有效最终 verdict 也相同。人工复核结果见上方链接，真实方向工具相反的 7 图均在最终状态记录冲突；4 图把格式修复提示复制进最终理由。新克隆上 60 图原图哈希、派生 Evidence 卡片和 crops 逐一核验为 60/60、0 缺失，held-out Actor 推理已启动，预计约 35–45 分钟。GPU 工作结束须提醒用户关卡。

已接收[Actor-B Schema/Held-out 新执行方案](ACTOR_B_SCHEMA_HELDOUT_PLAN.md)，附件 SHA-256 `2d5f70117e4b4d74cc0bc43e62ce1bb740c7e75dc3f0d9057f67608cf435d261`。Phase A 对齐 STOP parser 与原 schema：保留 `final_verdict=real|fake` 强制约束，允许原 schema 已许可的 `final_confidence=null` 原样保留；旧 30 条 raw 轨迹用新 parser 重放为 30/30 合法终态，仍拒绝 8 次原始 `uncertain` STOP。曾尝试增加条件式 schema 文本，但前 16 条中出现 1 条 `inconclusive` STOP 重试失败和 1 条重复工具重试失败，已停止该候选并保留远端部分记录；原 schema 哈希 `d0ea87912099ccc058045f266bc904517f8abc209eea54ac707c44e2fc55b9b5` 已恢复。仅 parser 对齐的完整 30 图回归保存在独立目录 `actor-b-schema-20261007/actor_b/baseline_b0_schema_fixed_v2/`；不能将中止候选误作最终结果。

用户同意从既有 Actor-0 eval 按来源组选 60 图作为 held-out；20 个独立来源组，RAISE/FLUX/SD3.5 各 20，方向工具一致/冲突均覆盖，与 B0 30 图及 Mini FaithBench 固定 6 图的来源组和样本 ID 重叠均为 0。其余 74 个 eval 来源组保留给 Monitor test。held-out manifest SHA-256 `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`；本地与远端图像 60/60 哈希一致。已有冻结 Evidence v1 覆盖这 60 图，已复用原卡片和 crops，仅在派生卡片中更换 callable 名称；合并输入 SHA-256 `94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`。不重复执行 PROBE 推理。人工审计规则已在 `experiments/actor_b/AUDIT_PROTOCOL.md` 预先记录，最终 60 图结果见本日维护记录首段。

完成用户开卡后的 B0 GPU 实验。远端模型 revision、PROBE checkpoint/参考库及 30 图清单核验通过，30/30 Evidence-only 卡片与 90 crops 提取成功；合并输入 SHA-256 `ffda7e8c15885922b3ceb510eae6bfe4eb4a296fdf0dc74aff206987778c34e9`。Actor-B0 30/30 推理完成，原始轨迹 SHA-256 `48727c6d39ee9a97265db968302b5ca0992e4f2c0143722ec72fffe04a0b62d9`。复核发现两张 STOP 字段失败、9 张明确全局证据方向性归因错误；修正指标脚本的合法调用率与归因口径，撤回误导性的 50.4% 和自动 SFT 决策。27 项本地测试通过；GPU 已空闲，可关卡。未解决：B0 冻结口径、STOP 结构修复是否需要独立验证，以及 FaithBench/Monitor 标注口径。详见 B0 报告与轨迹复核。

执行前的本地准备：新增 `experiments/actor_b/`，包括结构化 action schema/parser、最小中文 prompt、冻结模型与生成配置、30 图 B0 清单选择、PROBE Evidence-only dev 提取、证据合并、B0 运行与一次性评价脚本；新增 5 项协议测试。固定 B0 sanity 集来自既有 Actor dev：30 图、30 个互不重复来源组，RAISE/FLUX/SD3.5 各 10，15 个既有方向工具冲突案例和 15 个一致案例；与旧 Actor eval 和 Evidence v1 参考集来源组重叠均为 0，30/30 本地图像存在。旧 PROBE 分类输出已从 B0 输入中移除。清单 SHA-256 `455c011e8146cdccb04696bed3ad1b2c521e5424fd22d4e7edcd38e68cc8a915`；本地全套 27 项测试通过。原定 RTX 4090 步骤已按上段完成。

## 2026-10-06 维护记录

已将现行方案、历史快照、项目源码、测试、实验脚本、配置及小体积分析摘要共 252 个文件提交并推送到 GitHub `Zephyr-Feng/AIGC-Actor-Monitor` 的 `main` 分支，提交 `69ab505`。本地 22 项单元测试通过，远端分支更新成功。原始图像、模型权重、下载缓存、第三方仓库和大体积实验产物仍留在本地，不属于本次 GitHub 归档；后续若需共享数据或完整轨迹，先核对来源许可、体积和匿名化要求。研究进度本身未因归档而推进，下一步仍是按新方案核对工具、Evidence Card、Actor 轨迹和 FaithBench 标注协议。

用户明确将项目主方案更新为 Evidence-Grounded Actor–Monitor Framework。已将贴出的原文逐字复制为现行主方案，并将此前 MVP v2 保存为历史快照；同步 README、文档导航和本页的研究主线。核对新文件与用户附件 SHA-256 一致，旧方案快照已保存。旧实验结果及未提交代码未改；新方案中引用的外部论文、具体工具组合、FaithBench 标注规则与 Monitor 评价协议尚未独立核验或冻结。下一步从协议梳理和复用核对开始，不直接启动采集或训练。

按用户授权完成最后一轮两处 prompt 归因/STOP 契约说明修复并重跑原 18 条。工程检查 18/18 最终可解析、0 非法 callable、crop 像素一致、输入 classifier 结论泄漏 0；人工检查仍发现 PROBE 方向性归因，且一次原始 STOP 的 `final_verdict=uncertain` 被 parser 拒绝后才恢复。候选 SHA 和全部原始轨迹已归档；未改 Evidence、工具、parser 或 Actor 取证策略。门槛失败，正式采集与 SFT 均未启动；GPU 推理进程退出，可关卡。详细见[第三轮小样](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)。本页先前压缩前版本仍在[归档](archive/PROJECT_PROGRESS_20261006_precompact.md)，SHA-256 `4d70b710b77029a4e99748679da416061449e55521208798dd502c1848797c82`。
