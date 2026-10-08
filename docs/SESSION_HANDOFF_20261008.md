# 新对话交接：Actor现状与Monitor/STOP设计讨论

更新日期：2026-10-08。工作区：`D:\Codex\AIGC`。本页整理截至本次对话的事实、判断与待讨论建议；现行主方案仍为[Evidence-Grounded Actor–Monitor Framework](Actor_Monitor_MVP_Protocol.md)。

## 1. 新对话先从这里接续

**当前任务：继续讨论Monitor设计，首先明确允许STOP的条件。** 研究者明确要求设计讨论先于模型选择和实验。先读根目录`AGENTS.md`、[项目进度](PROJECT_PROGRESS.md)、[主方案](Actor_Monitor_MVP_Protocol.md)，再读本页。

- 当前Actor-B0-C已有契约层冻结；暂保留该版本作为Monitor开发的Actor候选。
- Actor基础工具编排已表现，证据解释与停止决策仍有问题；暂不追加Actor SFT。
- B0-D正式证据审计gate仍`ACTOR_B0_D_INCONCLUSIVE`，独立人工确认0。
- FaithBench开发材料和离线Monitor接口草案已完成，真实Monitor推理、训练、在线干预和正式benchmark尚未启动。
- STOP设计是讨论建议，研究者尚未确认采用；不要直接写入冻结Actor策略或当成金标签规则。
- 本阶段不用GPU。此前“现有Qwen跑8个文字开发例”的建议未获执行确认，先讨论设计。

## 2. 研究主线与已完成工作

目标：研究Monitor能否核验自主图像取证Actor的证据归因、综合、冲突处理、充分性和停止决策。主方案路线：固定工具/Evidence/Actor → FaithBench → 离线Monitor → 在线干预。旧MVP v2成本/收益预测路线仅保留为历史。

| 阶段 | 已完成事实 | 结论边界 / 入口 |
|---|---|---|
| PROBE Evidence-Only v1 | 独立RAISE参考100图/600 patches；300 eval卡片与900 crops，分类路径300/300与原实现对齐 | 表征偏离提供观察和定位；[报告](../experiments/probe_evidence_v1/REPORT.md) |
| Actor-0 / Actor-A | 100来源组、300 eval图；旧Actor accuracy 0.950，PROBE-only 0.987；global-only STOP 112/300 | 历史较弱Actor对照，CONDITIONAL KEEP；[报告](../experiments/actor0/REPORT.md) |
| Mini FaithBench技术小样 | 固定6图×3条件，第三轮18/18最终可解析，但归因与原始STOP问题仍有 | 未冻结该prompt，未启动正式900条；[报告](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md) |
| Actor-B0-C契约冻结 | 60/60合法终态；只修5个非法STOP，55/55原合法verdict保持；60/60工具序列及STOP前历史保持 | `ACTOR_B0_C_FREEZE`仅是此次契约/保持性门槛；[报告](../experiments/actor_b/ACTOR_B_CONSTRAINED_FREEZE_REPORT.md) |
| Actor-B0-D条件诊断 | FULL、PROBE-MASK、PROBE-DELAY、TOOL-RENAME各60图，后三组GPU推理完成；240轨迹，827 CALL请求 | 复用B0-C60图；PROBE类用困难代理；74预留来源组不动；[报告](../experiments/actor_b/actor_b0_d/report/ACTOR_B0_D_REPORT.md) |
| Agent辅助预审 | 827/827 CALL与固定20图×4条件80/80轨迹完成并SHA锁定，先CALL后终态再配对 | 全部是模型预审，未冒充人工金标签；[预审报告](../experiments/actor_b/actor_b0_d/audit_assist/AGENT_AUDIT_REPORT.md) |
| FaithBench/Monitor无卡准备 | 827 CALL前缀、80原始终态、8说明性开发例；中文规范、prompt、Schema、引用/状态解析及检查入口 | 51项仓库测试通过，907输入hash/时间边界检查通过；无模型推理；[阶段报告](../experiments/faithbench_monitor_v0/PREPARATION_REPORT.md) |

Actor模型：冻结`Qwen3-VL-8B-Instruct`，revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`。本项目没有进行Actor SFT；“已学会调用”应表述为“当前设置下展示了已有工具调用能力”。

## 3. 当前Actor判断及其限制

[模型审计判断](../experiments/actor_b/actor_b0_d/audit_assist/MODEL_AUDIT_ASSESSMENT.md)建议暂不训练Actor：主要疑点集中于证据解释、综合与STOP，适合作为Monitor研究对象；现有证据没有证明SFT必要性或效果。

预审聚合（均为silver提议）：

- CALL：812 appropriate、2合理但冗余、13 inappropriate。13个不合理请求均在预算剩余0时出现，涉及12条sample-condition轨迹。
- 80轨迹：证据充分32、不足47、无法判断1；`premature_stop=true`18；无支持断言31、不忠实31；冲突已承认但未解决26。
- 80条是同20图四条件；827请求包含相关轨迹及重试，不能视为独立样本。
- 条件由不同隔离Agent审核，尺度可能不同；条件间预审数量差不能直接解释为干预效应。
- 真实人工确认0，身份/真假GT未用于此次预审判断；正式gate不变。

研究者曾授权隔离Agent做本轮预审，随后委托模型审核；这已完成。现有模型审核只作为开发标签，不自动延伸为新一轮Agent任务授权或独立人工标签。原预审及锁不覆盖。

## 4. 现有工具语义与预算

冻结工具说明在[tool_cards.json](../experiments/mini_faithbench_v0/config/tool_cards.json)。

| 工具 | 当前证据含义 | 需要保留的限制 |
|---|---|---|
| `global_forensic_analyzer` / PROBE | 相对真实参考库的表征偏离、空间分布、定位crops | 偏离百分位不等于假图概率；高偏离或低偏离均不能单独证明来源 |
| `local_texture_analyzer` | 局部纹理原始score、real_like/synthetic_like方向信号 | 可能误报；strength未校准；工具卡明确不应单独作为最终结论 |
| `complementary_forensic_analyzer` | 不同训练/表征流程的real/fake补充意见 | 存在分布变化局限；不同方法不自动证明错误统计独立 |
| `provenance_inspector` | C2PA/EXIF/XMP等来源线索 | 缺失为inconclusive；未经验证的声明不能证明来源 |

**预算的含义：当前每图最多4次计入预算的CALL请求。** 格式/枚举输出重试不计入；通过解析、进入调用流程的请求计数，PROBE-DELAY首步受规则阻断的请求也会占额度。因此不能仅用成功工具返回数计算剩余预算。代码依据：`run_b0_d_condition.py`的`call_attempts`计数，以及盲审包的`budget`字段。成功工具禁止重复调用。

预算耗尽是调用额度已用完，不说明证据充分。运行器可能记录越预算请求并反馈错误；这不等于实际获得了额外工具证据。预算上限4尚未因Monitor讨论改变。

## 5. Monitor设计讨论：目前的建议，尚未定稿

### 目标与结构

分别审核：证据使用是否忠实、结论支持是否充分、STOP是否合理。先离线审核已有轨迹，再讨论在线干预。建议结构：确定性规则检查（格式/预算/重复/引用）＋语义审核（证据对齐/冲突/缺口）＋可定位报告。

建议输入：工具说明、原始Evidence Cards、Actor逐步输出与预算。是否加入原图/crops待讨论；文字原型没有像素，Actor视觉自述不能当成Monitor已核实的事实。逐步骤判断只能使用当时已获得的信息。

候选对照：普通轨迹Judge、加入领域规范的Judge、逐步骤对齐并要求原文引用/缺口解释的Monitor；比较时尽量保持模型与信息一致。尚未确认对照设置、模型或数量。

### STOP讨论建议

将“可以结束取证”与“足以支持当前结论”分别记录：

1. **证据支持的停止**：存在与结论相关的真实方向支持；重要冲突得到有依据的处理；没有值得补充的关键缺口；结论强度符合证据局限。
2. **受资源限制的结束**：预算耗尽或没有可执行补证据途径，允许结束；证据仍可不足/未决。这种结束不自动算提前STOP，也不自动获充分性通过。

拒绝STOP、要求继续时，建议Monitor必须给出“具体缺口＋原始引用＋当前可执行的补证据方向”，检查预算/工具可用性。只写“还需要更多证据”不足以支撑继续。

当前讨论的默认边界：

| 当前信息 | 暂拟建议 |
|---|---|
| 只有PROBE偏离或来源信息缺失 | 不能由此取得真假方向支持；有相关补证据途径时继续 |
| 只有局部纹理方向信号，互补工具仍可调用且有预算 | 默认请求补证据；依据现有局部工具卡限制 |
| 局部与互补信号一致 | 可进入STOP审核，仍检查适用性、局限、冲突和表述，不自动通过 |
| 方向工具相反，重要冲突未处理 | 能补证据则继续；不能则受限结束并保留不确定性 |
| 预算0 | 结束；另行报告结论支持程度 |

这不是“统一至少调用两个工具”或多数投票规则。相同方向不代表独立证据；单份来源证据的可信性与范围也需单独审核。没有采用真假概率、工具分数或置信度阈值。

当前Actor要求`real/fake`输出不变；可以考虑在Monitor侧独立记录“支持/不足/无法判断”与停止原因。尚未增加字段、修改Schema或实施该建议。

规范对齐参考[GLEAN原论文](https://arxiv.org/abs/2603.02798)，其原验证为临床诊断并另做可靠性校准；本项目未复现完整GLEAN。公开Vectara FaithBench是文本摘要任务，仓库许可CC BY-NC-SA 4.0；本项目未引入其数据/代码。来源核对见[REUSE_REVIEW](../experiments/faithbench_monitor_v0/REUSE_REVIEW.md)。

## 6. 下一步最需要讨论的问题

1. 是否采用“证据支持停止 / 受限结束”的区分，怎样与现有`stop_justified`、`verdict_supported`标签对齐？
2. 局部单信号且互补工具可用时，是否按上述默认要求补证据；哪些可信来源证据允许例外？
3. 什么算“重要缺口”，什么证据足以处理冲突；无法确认权重/校准时怎样保留unassessable？
4. 第一版是否需要原图/crops，还是先限定工具语义与文字推理审核？
5. 如何获取独立可核验的标签，避免同一模型自生成标签又自评有效；正式来源组边界怎样划分？
6. 确认目标和评价后，再选择Monitor模型、开发小样及需要GPU的任务。8例建议仍未执行；10–20分钟仅是粗略技术检查估计，不能当已确认用卡安排。

## 7. 本地材料、操作与保护边界

- 离线原型入口：`experiments/faithbench_monitor_v0/README.md`。代码已有输入适配、中文prompt、输出Schema、响应检查；不是已验证的Monitor。
- 私有包：`experiments/faithbench_monitor_v0/private/`，含`inputs.jsonl`、`annotations.jsonl`、`assets.jsonl`、`manifest.json`、`case_index.json`、`development_cases.md`与8例请求。
- 私有manifest SHA-256：`5359eb808e00f5d21447434720c3a0d5b8a74045470717d38811a76fbdd44e6e`。审计输入fingerprint：`7b8f962172d9a28454895d0b120e2018b068a57b1cc4345b208d1905d9d3db70`。
- 原审计包：`experiments/actor_b/actor_b0_d/audit_assist/work/{full,probe_mask,probe_delay,tool_rename}/`，每条件CALL/轨迹及独立锁。原图/crops在同目录的`review_packets/`。
- 人审入口`review_packets/human_review.html`已修复按钮提示并做虚构数据测试。实际人工标签未导入。80轨迹＋243去重CALL队列仍在；P2的RENAME高置信空候选例外未确认。
- 已查看B0-D60图是开发/诊断材料；74个Monitor预留来源组不动，同图条件/同源图不能跨正式划分。本次不解盲、不复用GT作推理标签。
- `prepare_dev.py`已有输出时拒绝覆盖；不用为了交接重跑。现有51项测试通过为上次代码验证，本次仅整理文档。
- 原始图像、轨迹、身份映射、逐样本标签、示例请求留本地且Git忽略。公开代码/文档可按已有用户授权归档GitHub。
- 本地有大量无关未跟踪缓存、第三方仓库与研究产物，保留，不清理、不批量提交。

## 8. GitHub与服务器续接

GitHub：`Zephyr-Feng/AIGC-Actor-Monitor`，`main`。交接前最新公共提交：`d78de49`（无卡准备）、`c2791ff`（优先讨论设计）；本交接随新提交归档。

最近核验AutoDL入口：`connect.bjb1.seetacloud.com:33082`，这是2026-10-07实验实例，当前可达性和GPU状态未再次核验。B0-D远端目录`/root/autodl-tmp/actor-b-schema-20261007/actor_b/actor_b0_d/`，此前推理已结束、GPU空闲，用户已获知可以关卡。

当前任务不需要SSH或GPU。以后研究者提供新克隆时，先用已有密钥做只读代码/数据盘/模型/结果/hash交接；入口会变，不按历史端口直接启动实验。真实GPU任务先讲清任务与预计时段，请研究者开卡，结束告知关卡。凭证不得写入命令、文件或进度。

## 可直接粘贴到新对话的开场

> 项目在 D:\Codex\AIGC。请先读 AGENTS.md、docs/PROJECT_PROGRESS.md、docs/Actor_Monitor_MVP_Protocol.md 和 docs/SESSION_HANDOFF_20261008.md。继续与我讨论Monitor设计，当前先确定允许STOP的条件。已有Actor-B0-C契约冻结版本暂保留，不追加SFT；B0-D正式gate仍INCONCLUSIVE，Agent标签只作silver开发参照。先讨论，不启动模型推理、不改冻结策略、不动74个Monitor预留来源组；需要用卡时再告诉我。
