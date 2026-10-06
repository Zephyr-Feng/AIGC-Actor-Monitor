# 项目进度与跨对话交接

> 新对话先读本页、仓库根目录 `AGENTS.md` 和[项目主方案](Actor_Monitor_MVP_Protocol.md)。[文档导航](README.md)区分现行方案与历史材料；详细过程和旧版进度见[2026-10-06 压缩前归档](archive/PROJECT_PROGRESS_20261006_precompact.md)。

## 当前状态（2026-10-07）

- **Mini FaithBench v0 停在第三轮技术小样。** 按用户最后授权，仅补强 PROBE observation / Actor inference 的归因边界和 STOP 的 `real|fake` 输出说明；固定 6 图×3 条件重跑为 18/18 最终可解析，crop 图像输入、其他工具 callable 和 PROBE 输入结论泄漏检查均正常。但人工复核发现 PROBE 偏离仍被写成真假倾向；一次原始 STOP 仍输出 `final_verdict=uncertain`，虽在下一步重试恢复。按预设门槛**不再叠加 prompt patch、不冻结 prompt、不启动正式 900 条或 SFT**。结论：Prompt-only schema adaptation is insufficient to reliably enforce evidence attribution boundaries。[本轮报告和原始轨迹](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)；[前轮失败](../experiments/mini_faithbench_v0/technical_sample_v2/REPORT.md)。
- **Prompt 版本。** 旧 Actor-0 prompt material SHA-256 `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`；前轮 Evidence-compatible 候选 `cc128afa3e4f6ec0f0cc68509386c2668f6375f551fdc45803369746b6c8882f`；本轮**未冻结候选** `5cc7a1cd8ffda55b7d2b94b7546619944073c933ed1a064c0a2d07c0c94604f2`。完整文件与哈希记录在 `experiments/mini_faithbench_v0/config/`；三条件使用同一候选。
- **PROBE Evidence-Only v1 已完成并冻结。** 独立 RAISE 参考集 100 图、600 patches；固定 `k=20`、percentile、top-3、crops 和 spatial pattern。300 张 eval 图形成 300 份无 classifier 结论的 Evidence Cards 与 900 张 crops；classifier 路径 300/300 与原 PROBE 对齐。[报告与验证](../experiments/probe_evidence_v1/REPORT.md)。
- **Actor-0 已完成。** 100 来源组、300 张 eval 图，Qwen3-VL-8B-Instruct revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`。Actor accuracy 0.950，低于 PROBE-only 0.987；global-only STOP 为 112/300，128 个冲突均未解决。Actor-0 决策为 CONDITIONAL KEEP。[报告](../experiments/actor0/REPORT.md)。
- **研究主线已更新。** 用户提供的[现行主方案](Actor_Monitor_MVP_Protocol.md)以 Evidence-Grounded Actor–Monitor Framework 为核心：先固定结构化 Tool Actor，再构建 FaithBench，先做离线轨迹验证，后做在线 Monitor 干预。Actor-0 保留为较弱 Actor；是否需要轻量 trajectory SFT 取决于基础工具编排验证。旧版同轨迹 `A0/A1/A2` 增量收益与成本预测方案已存入[历史快照](archive/Actor_Monitor_MVP_Protocol_v2.md)，不再作为后续实验指令。当前主 Actor、正式 FaithBench、Monitor 均未完成；专家栈与 Evidence 接口仍需按新方案明确。既有工具筛选结论：PROBE KEEP，PatchCraft/SAFE/Provenance CONDITIONAL，RIGID DROP；FSD/AIDE 不进入主工具箱。[工具筛选报告](../experiments/toolbox_screening/REPORT.md)。

## 续跑位置与约束

- 最近核验的 AutoDL 入口：`connect.bjb1.seetacloud.com:31805`，主机 `autodl-container-40dd41ad1f-569df20a`。AutoDL 克隆后入口可能改变；连接新实例先只读核验数据、模型、未提交改动和结果哈希。**GPU 最后核验为空闲，用户可以关卡；下次用卡先告知任务和预计时段。**
- 远端 Mini FaithBench 隔离目录：`/root/autodl-tmp/mini-faithbench-v0/`；独立 Actor venv 为 `transformers==4.57.4`、`accelerate==1.10.1`，PROBE 环境未改。模型与 processor 使用上述同一 revision。三轮小样在 `technical_sample/`、`technical_sample_v2/`、`technical_sample_v3/`；`formal/` 尚无正式轨迹。
- 本地入口：`experiments/mini_faithbench_v0/`（runner、三条件 inputs、benchmark config、prompt 与技术小样）；`experiments/probe_evidence_v1/results/output/`（Evidence v1）；`runs/actor0-bfree-20261002/`（旧 Actor-0 原始结果，忽略目录）。代码和研究文件存在未提交改动，不重置或覆盖。
- 下一步先按新方案梳理冻结工具、Evidence Card 字段与 Actor 结构化轨迹的对应关系，明确基础 tool-use sanity check 和 FaithBench 标注口径；然后再决定是否需要轻量 Actor SFT。第三轮小样的归因失败和原始 STOP 契约失败可作为候选目标，但原先失败的 prompt 版本不因路线更新而自动冻结。本轮不启动 SFT、正式 900 条或 GPU 实验。旧实验记录保留在各报告及上述归档，历史 SSH 端口不要当作当前入口。

## 早期阶段索引

| 阶段 | 保留结论 | 详细记录 |
|---|---|---|
| T0 与三动作 pilot | 加入旧 CPU 读数未稳定改善判断；pilot 未观察到有用的动作选择空间。仅为探索诊断。 | [T0](T0_TOOL_CHECK.md)、[pilot](THREE_ACTION_PILOT_CHECK.md) |
| Stage 1 FSD/AIDE/SAFE | 目标域表现未达稳健专家准入；SAFE 官方 DiTFake 正向复现通过，目标域问题不能简单归因于安装失败。 | [Stage 1](STAGE1_EXPERT_SCREEN.md)、[SAFE 正向对照](SAFE_POSITIVE_CONTROL_REPORT.md) |
| SAFE 图块诊断 | 位置有描述性差异，固定阈值下真图误报仍高；未证明总体改进。 | [报告](../SAFE_patch_diagnostic/REPORT.md) |
| PROBE 与异构工具 | PROBE 冻结 300 图表现强，但论文覆盖 FLUX/SD3、训练图逐图重叠未知；工具角色以上方当前状态为准。 | [PROBE](../experiments/probe_dinov2/REPORT.md)、[筛选](../experiments/toolbox_screening/REPORT.md) |
| 存储 | 旧实例曾清理至约 2.8 GB 可用并建议扩容；克隆后空间必须重新核验。 | [存储审计](../experiments/storage_audit/STORAGE_AUDIT_REPORT.md) |

## 2026-10-07 维护记录

已接收并落实 Actor-B“最小化适配、轻量 SFT、尽快冻结”执行方案的本地准备部分。新增 `experiments/actor_b/`：结构化 action schema/parser、最小中文 prompt、冻结模型与生成配置、30 图 B0 清单选择、PROBE Evidence-only dev 提取、证据合并、B0 运行与一次性评价脚本；新增 5 项协议测试。固定 B0 sanity 集来自既有 Actor dev：30 图、30 个互不重复来源组，RAISE/FLUX/SD3.5 各 10，15 个既有方向工具冲突案例和 15 个一致案例；与旧 Actor eval 和 Evidence v1 参考集来源组重叠均为 0，30/30 本地图像存在。旧 PROBE 分类输出已从 B0 输入中移除。清单 SHA-256 `455c011e8146cdccb04696bed3ad1b2c521e5424fd22d4e7edcd38e68cc8a915`；本地全套 27 项测试通过。下一步需要 RTX 4090：先对 30 图运行冻结 Evidence-only v1 提取，再运行 Actor-B0，预计合计约 25–40 分钟；得到报告前不决定 SFT，也不运行正式 900 条。

## 2026-10-06 维护记录

已将现行方案、历史快照、项目源码、测试、实验脚本、配置及小体积分析摘要共 252 个文件提交并推送到 GitHub `Zephyr-Feng/AIGC-Actor-Monitor` 的 `main` 分支，提交 `69ab505`。本地 22 项单元测试通过，远端分支更新成功。原始图像、模型权重、下载缓存、第三方仓库和大体积实验产物仍留在本地，不属于本次 GitHub 归档；后续若需共享数据或完整轨迹，先核对来源许可、体积和匿名化要求。研究进度本身未因归档而推进，下一步仍是按新方案核对工具、Evidence Card、Actor 轨迹和 FaithBench 标注协议。

用户明确将项目主方案更新为 Evidence-Grounded Actor–Monitor Framework。已将贴出的原文逐字复制为现行主方案，并将此前 MVP v2 保存为历史快照；同步 README、文档导航和本页的研究主线。核对新文件与用户附件 SHA-256 一致，旧方案快照已保存。旧实验结果及未提交代码未改；新方案中引用的外部论文、具体工具组合、FaithBench 标注规则与 Monitor 评价协议尚未独立核验或冻结。下一步从协议梳理和复用核对开始，不直接启动采集或训练。

按用户授权完成最后一轮两处 prompt 归因/STOP 契约说明修复并重跑原 18 条。工程检查 18/18 最终可解析、0 非法 callable、crop 像素一致、输入 classifier 结论泄漏 0；人工检查仍发现 PROBE 方向性归因，且一次原始 STOP 的 `final_verdict=uncertain` 被 parser 拒绝后才恢复。候选 SHA 和全部原始轨迹已归档；未改 Evidence、工具、parser 或 Actor 取证策略。门槛失败，正式采集与 SFT 均未启动；GPU 推理进程退出，可关卡。详细见[第三轮小样](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)。本页先前压缩前版本仍在[归档](archive/PROJECT_PROGRESS_20261006_precompact.md)，SHA-256 `4d70b710b77029a4e99748679da416061449e55521208798dd502c1848797c82`。
