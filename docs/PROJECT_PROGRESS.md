# 项目进度与跨对话交接

> 新对话先读本页、仓库根目录 `AGENTS.md` 和[项目主方案](Actor_Monitor_MVP_Protocol.md)。[文档导航](README.md)区分现行方案与历史材料；详细过程和旧版进度见[2026-10-06 压缩前归档](archive/PROJECT_PROGRESS_20261006_precompact.md)。

## 当前状态（2026-10-08）

- **FaithBench开发与离线Monitor无卡准备完成。** 用户授权后复用锁定盲化输入，生成827条CALL前缀、80条原始终态（20图×4条件）、8个说明性开发例；silver预审标签和后处理投影单独保存，当前CALL结果与未来步骤不进入请求。完成七类中文规范、Monitor prompt/Schema与引用/状态解析入口，907输入来源hash/时间边界检查通过，新增8项测试及全仓库51项通过。代码/文档可归档，逐样本与资产留本地且Git忽略。没有实际Monitor推理，未读取74个预留组或身份映射；人工确认0，B0-D gate仍INCONCLUSIVE，暂不追加Actor SFT。见[开发入口](../experiments/faithbench_monitor_v0/README.md)、[阶段报告](../experiments/faithbench_monitor_v0/PREPARATION_REPORT.md)。下一步确认8例文字技术检查的模型/口径后再开卡，独立效能评价另议。

- **B0-D Agent 辅助预审已完成80/80轨迹、827/827 CALL并独立锁定。** 按[新方案](../experiments/actor_b/actor_b0_d/audit_assist/AGENT_AUDIT_PLAN.md)先锁定调用前审核，再审完整轨迹，最后配对。原人工标签文件SHA保持不变，真实人工确认0；当前gate仍为`ACTOR_B0_D_INCONCLUSIVE`。CALL预审812 appropriate、2 reasonable_but_redundant、13 inappropriate；均为模型提议。人审材料为80轨迹全量及243条去重CALL（P0=13、P1=212、P2=18）。TOOL-RENAME全部CALL置信medium，严格高置信P2没有候选，四条件P2覆盖例外已向研究者提问，当前保持原门槛；RENAME首次选择通过P1全量覆盖。[预审报告](../experiments/actor_b/actor_b0_d/audit_assist/AGENT_AUDIT_REPORT.md)、[人审指南](../experiments/actor_b/actor_b0_d/audit_assist/HUMAN_REVIEW_GUIDE.md)。本轮不需要GPU，未解盲、未启动SFT或Monitor。

- **Actor-B0-D 三个 GPU 条件和四条件自动评价均已完成；人工审计等待中。** PROBE-MASK、PROBE-DELAY、TOOL-RENAME 各 60/60，GPU 已释放。当前决策 `ACTOR_B0_D_INCONCLUSIVE`，原因是方案规定的 20 图 × 4 条件人审（80 行）及 827 条工具选择审计尚未开始；自动指标不能替代人审。诊断类别固定为 EASY 12、PROBE 困难代理 12、工具方向冲突 16、弱证据 10、困难可解 10；历史 PROBE 错误图重叠为 0，74 个 Monitor 预留来源组未触碰。完整数值、限制和审计入口见[B0-D 报告与说明](../experiments/actor_b/actor_b0_d/README.md)。
- B0-D 源码冻结于 `1c26bca4bae2bde5f94f409e4cf430fdaabd98ec`，运行器冻结时 39 项仓库测试通过；离线评价修正后全套 43 项通过。用户开卡后，当前入口 `connect.bjb1.seetacloud.com:33082` 的 B0-C prompt、模型 config、60/60 图像 hash、180/180 crops 与运行版本核验通过。PROBE-MASK 原始解析 57/60、effective 60/60；PROBE-DELAY 原始解析 52/60、effective 60/60，28 次首步 PROBE 禁止尝试已记录。三个条件均已备份且轨迹/runtime hash 与远端一致；60/60 顺序和 runner hash 核验通过。正式评价输出四条件各 60 条、80 行固定盲审模板和 827 行调用审计表。FULL/MASK/DELAY/RENAME 的有效终态分别为 60/60、60/60、60/60、59/60；RENAME 唯一无效轨迹为预算耗尽后两次请求重复工具。SFT gate 暂为 INCONCLUSIVE，等待人审。
- **Actor-B Contract-Constrained Freeze Gate 通过，决策为 `ACTOR_B0_C_FREEZE`；未启动 SFT。** 用户选择保留已有合法 `real/fake` verdict，只对 5 条非法 STOP 使用同模型 forced choice。独立派生评价为 60/60 合法终态、5/5 失败修复、55/55 原合法 verdict 保持、60/60 工具序列及 STOP 前历史保持。先前“每条 STOP 均做 forced choice”的候选仅保留 37/55 verdict，已作为失败诊断保留，不作冻结版本。所选派生 replay SHA-256 `89fbe915fdf32505b20da820a50236c2a2238fc3fa72ab0e4bce06447464f130`，详见[最终报告](../experiments/actor_b/ACTOR_B_CONSTRAINED_FREEZE_REPORT.md)。
- **Actor-B0 原 30 图 sanity（历史记录）。** 30/30 PROBE Evidence-only、30/30 B0 推理完成；28/30 有合法最终输出，95/95 工具调用请求合法、0 重复，平均 3.17 次/图。两张失败均为 STOP 的 `final_confidence` 为空；9/30 图出现明确把 PROBE 全局偏离标成 `real`/`fake` 的归因错误。小样 balanced accuracy 0.65 仅作诊断。自动评价最初把 `inconclusive` 算作归因违规，50.4% 已撤回；原始“考虑 SFT”标签也因阈值未经确认而撤回。[报告](../experiments/actor_b/baseline_b0/analysis/ACTOR_B0_BASELINE_REPORT.md)、[轨迹复核](../experiments/actor_b/baseline_b0/analysis/ACTOR_B0_AUDIT.md)。
- **Mini FaithBench v0 停在第三轮技术小样。** 按用户最后授权，仅补强 PROBE observation / Actor inference 的归因边界和 STOP 的 `real|fake` 输出说明；固定 6 图×3 条件重跑为 18/18 最终可解析，crop 图像输入、其他工具 callable 和 PROBE 输入结论泄漏检查均正常。但人工复核发现 PROBE 偏离仍被写成真假倾向；一次原始 STOP 仍输出 `final_verdict=uncertain`，虽在下一步重试恢复。按预设门槛**不再叠加 prompt patch、不冻结 prompt、不启动正式 900 条或 SFT**。结论：Prompt-only schema adaptation is insufficient to reliably enforce evidence attribution boundaries。[本轮报告和原始轨迹](../experiments/mini_faithbench_v0/technical_sample_v3/REPORT.md)；[前轮失败](../experiments/mini_faithbench_v0/technical_sample_v2/REPORT.md)。
- **Prompt 版本。** 旧 Actor-0 prompt material SHA-256 `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`；前轮 Evidence-compatible 候选 `cc128afa3e4f6ec0f0cc68509386c2668f6375f551fdc45803369746b6c8882f`；本轮**未冻结候选** `5cc7a1cd8ffda55b7d2b94b7546619944073c933ed1a064c0a2d07c0c94604f2`。完整文件与哈希记录在 `experiments/mini_faithbench_v0/config/`；三条件使用同一候选。
- **PROBE Evidence-Only v1 已完成并冻结。** 独立 RAISE 参考集 100 图、600 patches；固定 `k=20`、percentile、top-3、crops 和 spatial pattern。300 张 eval 图形成 300 份无 classifier 结论的 Evidence Cards 与 900 张 crops；classifier 路径 300/300 与原 PROBE 对齐。[报告与验证](../experiments/probe_evidence_v1/REPORT.md)。
- **Actor-0 已完成。** 100 来源组、300 张 eval 图，Qwen3-VL-8B-Instruct revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`。Actor accuracy 0.950，低于 PROBE-only 0.987；global-only STOP 为 112/300，128 个冲突均未解决。Actor-0 决策为 CONDITIONAL KEEP。[报告](../experiments/actor0/REPORT.md)。
- **研究主线已更新。** 用户提供的[现行主方案](Actor_Monitor_MVP_Protocol.md)以 Evidence-Grounded Actor–Monitor Framework 为核心：先固定结构化 Tool Actor，再构建 FaithBench，先做离线轨迹验证，后做在线 Monitor 干预。Actor-0 保留为较弱 Actor；是否需要轻量 trajectory SFT 取决于基础工具编排验证。旧版同轨迹 `A0/A1/A2` 增量收益与成本预测方案已存入[历史快照](archive/Actor_Monitor_MVP_Protocol_v2.md)，不再作为后续实验指令。当前主 Actor、正式 FaithBench、Monitor 均未完成；专家栈与 Evidence 接口仍需按新方案明确。既有工具筛选结论：PROBE KEEP，PatchCraft/SAFE/Provenance CONDITIONAL，RIGID DROP；FSD/AIDE 不进入主工具箱。[工具筛选报告](../experiments/toolbox_screening/REPORT.md)。

## 续跑位置与约束

- 2026-10-07 在 connect.bjb1.seetacloud.com:33082 完成 B0-D 推理；远端目录 /root/autodl-tmp/actor-b-schema-20261007/actor_b/actor_b0_d/。TOOL-RENAME PID 7077 已退出，60/60 runtime 写入，GPU 检查为 0 MiB / 0%，用户已获知可关卡。入口会随克隆改变，无凭证记录。剩余工作仅为本地人工审计及据此更新最终 gate。
- Actor-B0 远端隔离目录：`/root/autodl-tmp/actor-b0-20261007/`；30 图原始轨迹还在此目录及本地 `experiments/actor_b/baseline_b0/outputs/`（Git 忽略，不上传 GitHub）。冻结输入及运行哈希见 B0 报告。旧实例的两份派生 JSONL 传输曾获单次授权；用户随后提供新克隆并明确要求在新实例续跑，held-out 输入仅在该实例用于此次实验，仍不上传 GitHub。
- 远端 Mini FaithBench 隔离目录：`/root/autodl-tmp/mini-faithbench-v0/`；独立 Actor venv 为 `transformers==4.57.4`、`accelerate==1.10.1`，PROBE 环境未改。模型与 processor 使用上述同一 revision。三轮小样在 `technical_sample/`、`technical_sample_v2/`、`technical_sample_v3/`；`formal/` 尚无正式轨迹。
- 本地入口：`experiments/mini_faithbench_v0/`（runner、三条件 inputs、benchmark config、prompt 与技术小样）；`experiments/probe_evidence_v1/results/output/`（Evidence v1）；`runs/actor0-bfree-20261002/`（旧 Actor-0 原始结果，忽略目录）。代码和研究文件存在未提交改动，不重置或覆盖。
- Actor-B0-C 已按获批最小策略冻结。下一步回到主方案安排 FaithBench 阶段；正式 benchmark 尚未启动。当前不运行 SFT 或正式 900 条。PROBE 归因错误保留为可检测的失败案例。旧实验记录保留在各报告及上述归档，历史 SSH 端口不要当作当前入口。


四条件 B0-D 推理及自动配对评价完成。TOOL-RENAME 轨迹/runtime SHA-256 分别为 `83fba0e96c644a6a1107ec327581060b566c2a7572634b004357140e0e39c51d` 与 `af08cf140b58e46a38fc8885709c3a511763c297781cbbb50f194071a263b90c`，与远端一致；四条件顺序、runner hash 核验通过。raw/effective 合法终态：FULL 55/60→60/60，MASK 57/60→60/60，DELAY 52/60→60/60，RENAME 59/60→59/60。评价器生成 80 行固定人审包和 827 行调用审计；仅聚合 metrics、报告与 runtime 可提交，逐样本结果留本地。当前 gate `ACTOR_B0_D_INCONCLUSIVE`，待真实人审。FULL 无 PROBE-first immediate STOP；RENAME 首工具 60/60 集中至 tool_alpha（原 global/PROBE），显示改名敏感信号；冲突机会调整后，FULL/MASK/DELAY/RENAME 有机会时跟进计数为 3/4、27/27、5/9、20/20。报告见 `experiments/actor_b/actor_b0_d/report/ACTOR_B0_D_REPORT.md`。没有训练 SFT 或启动 Monitor。
## 早期阶段索引

| 阶段 | 保留结论 | 详细记录 |
|---|---|---|
| T0 与三动作 pilot | 加入旧 CPU 读数未稳定改善判断；pilot 未观察到有用的动作选择空间。仅为探索诊断。 | [T0](T0_TOOL_CHECK.md)、[pilot](THREE_ACTION_PILOT_CHECK.md) |
| Stage 1 FSD/AIDE/SAFE | 目标域表现未达稳健专家准入；SAFE 官方 DiTFake 正向复现通过，目标域问题不能简单归因于安装失败。 | [Stage 1](STAGE1_EXPERT_SCREEN.md)、[SAFE 正向对照](SAFE_POSITIVE_CONTROL_REPORT.md) |
| SAFE 图块诊断 | 位置有描述性差异，固定阈值下真图误报仍高；未证明总体改进。 | [报告](../SAFE_patch_diagnostic/REPORT.md) |
| PROBE 与异构工具 | PROBE 冻结 300 图表现强，但论文覆盖 FLUX/SD3、训练图逐图重叠未知；工具角色以上方当前状态为准。 | [PROBE](../experiments/probe_dinov2/REPORT.md)、[筛选](../experiments/toolbox_screening/REPORT.md) |
| 存储 | 旧实例曾清理至约 2.8 GB 可用并建议扩容；克隆后空间必须重新核验。 | [存储审计](../experiments/storage_audit/STORAGE_AUDIT_REPORT.md) |

## 2026-10-08 维护记录

研究者要求先讨论Monitor设计。后续先确认监督目标、证据充分/STOP标准、信息范围、结构与评价对照，再选择模型并运行技术小样；此前8例同模型文字检查仅为建议，未获执行确认。现有规范/prompt/schema是可修改开发草案，不代表研究架构已定稿。本轮不启动推理或新增实验。

研究者授权“直接进行工作”，完成[FaithBench与离线Monitor无卡准备](../experiments/faithbench_monitor_v0/PREPARATION_REPORT.md)。复用已有盲化轨迹与SHA锁、Actor JSON提取器及审计读写/核验函数，核对Mini FaithBench、GLEAN及Vectara文本FaithBench适用差异；后者仓库许可为CC BY-NC-SA 4.0，未引入外部数据/代码。使用experimental-design技能核对相关重复/来源组评估边界并记录原始论文来源。生成80终态和827前缀、8开发例，私有manifest SHA-256 `5359eb808e00f5d21447434720c3a0d5b8a74045470717d38811a76fbdd44e6e`；28个来源hash与登记产物hash、全部输入白名单和过去步骤检查通过。4条非法原始终态保留，投影不进入输入。新增8项针对性测试，全仓库51项通过；虚构响应1/1入口校验通过，无语义效能评价。silver预审与case索引/资产/请求被Git忽略，人工标签/锁未改。未解决：真实Monitor模型/输入模态与评价口径、独立标签与正式来源组划分；尚未推理/训练/解盲，用户当前不用开卡。

研究者询问是否可进入下一环节。核对主方案Phase II FaithBench与Phase III离线Monitor、现成Mini FaithBench实现后，形成[下一阶段入口建议](FAITHBENCH_NEXT_STAGE_ENTRY.md)：可先无卡整理标注规范、开发案例和离线Monitor协议；现有Agent提议作为开发标签，不充作独立ground truth。74个Monitor预留来源组不动，正式小样/划分/模型/标签依据和实验条件待确认。没有启动新实验、训练或在线干预，也未把B0-D正式gate改为通过。

研究者委托Agent审核并询问SFT必要性。完成已锁定预审结果的定点证据复核：13不合理CALL均剩余预算0，涉及12条sample-condition轨迹；另核对非方向偏离的过强真假解释，以及明示需补证据却执行STOP的实际步骤。形成[模型审计判断](../experiments/actor_b/actor_b0_d/audit_assist/MODEL_AUDIT_ASSESSMENT.md)：基础工具调用能力在当前设置下已表现，证据解释/停止仍不可靠；建议暂不追加Actor SFT，必要性与效果尚未被证明。此为研究建议，正式gate不改，人工确认仍0；未启动训练、Monitor或解盲。本项目未对Actor训练，“学会”不得写作本项目训练所得。定点案例留在私有work目录，原初审标签及SHA锁不变。

用户报告“接受Agent建议”点击无反应。定位到必填拒绝提示位于长页面顶部，底部按钮附近不可见；已将提示放到按钮旁并自动滚动显示，区分缺理由、缺阅读勾选和标签已修改，并显示浏览器暂存失败的具体原因与下载入口。虚构记录浏览器验证缺项拒绝、完整确认保存和模拟存储失败提示通过；更新本地HTML，输入指纹与记录ID不变，未操作真实人工标签。

完成Agent辅助审计阶段。用户授权不继承聊天历史的隔离子Agent，各条件先审全部CALL前缀，写SHA锁后再审20条完整轨迹和实际图像/裁片，全部独立锁定后生成配对分析。240条实验轨迹、80条固定审计轨迹、827次调用、60/60原图和180/180源裁片匹配；输入fingerprint为`7b8f962172d9a28454895d0b120e2018b068a57b1cc4345b208d1905d9d3db70`。本地冻结工具卡已找到并SHA核验（此前“本地无tool cards”属于未定位，现已修正）。额度中断后核对已有锁，从未完成部分继续；本地自动审批曾多次超时，未把超时当实验失败或填补未审核结果。

产出逐轨迹Agent标签、全827调用Agent标签、243条去重CALL人工队列、80条完整轨迹人审页面、私有配对分析、公共预审报告及人工导入/锁定入口。逐样本材料、身份映射、图像、HTML与源标签留本地且被Git忽略。真实离线浏览器验证80轨迹加载、图像显示和JavaScript正常；虚构数据验证人工理由/阅读勾选必填，以及最终unassessable判断可保留并按字段记录。未调用真实人工导入，原人工文件SHA不变。待解决：P2的RENAME空候选例外、80轨迹与243 CALL真实人工复核及争议裁决；之后才显式解盲。不能将风险子集复核声称827次独立人审，不根据预审统计作SFT决策。

## 2026-10-07 维护记录

用户开卡后完成 B0-D 克隆交接与冻结输入核验。PROBE-MASK、PROBE-DELAY 各 60/60 完成，分别 3 与 8 次非法 STOP 最小投影，effective 均 60/60；轨迹与 runtime 已本地备份并与远端 hash 一致，见 [冻结记录](../experiments/actor_b/actor_b0_d/FROZEN_INPUTS.md)。对话中断期间 PROBE-DELAY 在远端继续完成，随后检查 GPU 空闲并启动 TOOL-RENAME；新条件使用持久日志与 PID，防止重复启动。离线评价发现并修正 Q2 分子错误：原逻辑把所有 PROBE-first 最终 STOP 都计为立即停止，现要求仅成功调用一次 PROBE 且此后没有其他 CALL 请求；新增 4 项针对性测试，全套 43 项通过。该修正不影响模型运行与冻结输入。下一步完成第三组、四条件配对评价、20 图 × 4 条件真实人工审计及最终报告；尚未据此作 SFT 决定。

接收[Actor-B0-D Evidence Sufficiency & Tool Strategy Gate 方案](../experiments/actor_b/actor_b0_d/ACTOR_B0_D_PLAN.md)。按用户确认复用 B0-C 60 图，12 个 PROBE 类以困难代理代替真实历史错误，74 个 Monitor 预留来源组保持不动。完成互斥分层、冻结 FULL 派生、三条件运行器、配对行为评估器和盲审包模板；本地仓库测试 39 项通过。诊断 manifest SHA-256 `7730863c14b4781202b48c1fb95a38e52a54ec3c5966d1c307f819f16d52a807`，Actor 输入 manifest SHA-256 `b5a8fadd99a04b8c213a95640cc2537e5746a5bce1cb75fab0e099c5153c83c2`，FULL 衍生轨迹 SHA-256 `24b08992bf3add37e0644f6c9fe1b397af374ddaee312f1d1fad82b24658af34`。其中缓存方向冲突 36/60、B0-C 已观察到的 12/36 只用于诊断基线；评估器 smoke fixture 复用了 FULL 四次，不作实验结果。GPU 条件尚未运行：待用户开卡后只读核验当前克隆上的 tool cards 与模型/数据 hash，严格复现 B0-C prompt hash 后，才执行 PROBE-MASK、PROBE-DELAY 和 TOOL-RENAME（预计 2.5–3 小时）。旧端口 33082 已拒绝连接；本地无冻结 tool cards，缺失或 hash 不符即停止讨论。至少 20 图四条件人工审计仍待完成；尚未作 SFT 判断，也未训练。

按[Contract-Constrained Freeze Gate 方案](ACTOR_B_CONSTRAINED_FREEZE_PLAN.md)完成 20 图 pilot 和 60 图完整 forced-choice replay。Pilot：5/5 原失败修复，20/20 parse、20/20 工具序列保持，15 个合法对照的 verdict 保持 10/15（66.7%）。完整回放：60/60 parse，5/5 原失败修复；原合法 verdict 保持 37/55（67.3%），变化 18 条（17 fake→real、1 real→fake）；工具序列、STOP 前历史、非 verdict STOP 字段均 60/60 保持。1 条精确 likelihood tie 使用预先记录的规则保留原合法 verdict。最终 replay SHA-256 `ff410c84cb94c9a093b48e8edde06b6f0ab9d88428f184cba041654bd3261488`，runtime SHA-256 `223b4f69d29e60f4d016583f3004bd4dbfcd40630ab04f0d9bc2aabe86949a0f`。当前不冻结，不据此启动 SFT；需要决定是否仅对 5 条非法 STOP 做强制选择并保留原合法输出。第一次全量运行因 6 位舍入造成并列、第二次发现精确并列而中止；两次部分结果保留在远端，第三次全量完成。用户已获知 GPU 空闲可关卡。

用户选择“只修复 5 条非法 STOP”。在不新增推理的情况下，从完整评分结果派生最小策略输出：55 条本来合法的 STOP 原文原 verdict 保持；5 条非法 STOP 使用原先冻结模型的 forced-choice 结果。独立评价 60/60 parse、5/5 失败修复、55/55 合法 verdict 保持、60/60 工具序列保持、60/60 STOP 前历史和其他 STOP 字段保持；freeze gate 通过，决策 `ACTOR_B0_C_FREEZE`。派生 replay SHA-256 `89fbe915fdf32505b20da820a50236c2a2238fc3fa72ab0e4bce06447464f130`，metrics SHA-256 `5bc26a596ee48e4014b97de2398038165ffa606dbcff4f8e2e1e5fc9d97dda14`。未训练 SFT，未重跑 detector、crop 或工具。详见[最终报告](../experiments/actor_b/ACTOR_B_CONSTRAINED_FREEZE_REPORT.md)。

接收[Contract-Constrained Freeze Gate 新方案](ACTOR_B_CONSTRAINED_FREEZE_PLAN.md)，明确先验证仅约束 `STOP.final_verdict` 的工程路径，上一轮 `ACTOR_B1_SFT_REQUIRED` 暂缓执行。保留原始 60 图轨迹与 frozen 输入，建立独立回放程序、15 条确定性成功对照、CPU 结构与 tokenizer 预检及评价脚本；不重跑检测器、工具或图块。原轨迹 SHA-256 `276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`，工具输入 SHA-256 `94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`。60/60 结构预检通过，60/60 tokenizer 边界及 2 条多模态 processor 上下文通过，34 项本地测试通过。未解决：GPU pilot 和完整回放尚未运行，控制组 verdict 能否保持、能否冻结 Actor 均未知；待用户开卡后先运行 pilot。

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
