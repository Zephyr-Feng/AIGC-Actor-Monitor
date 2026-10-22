# 历史交接：27B Monitor 的8例与部署记录

> 当前续跑入口已更新为[2026-10-10交接](SESSION_HANDOFF_20261010.md)。下文保留旧阶段背景和部署细节；实例地址、进程状态、待执行步骤与旧粘贴文本均不能作为当前状态。最新G/H已完成，第八轮尚未启动。

更新日期：2026-10-09。工作区：`D:\Codex\AIGC`。本页是当前续跑入口；`SESSION_HANDOFF_20261008.md`保留为早期设计讨论记录，不再代表当前执行状态。

> **2026-10-10新授权优先：** 用户已授权持续开卡自主改进Monitor、实验与复审直到额度限制或打断；10:06新实例 `connect.bjb1.seetacloud.com:18203`、RTX4090及完整交接通过。pilot_v3四轮完成及复审均未采用默认，第五轮F技术失败已停止；第六轮G冻结、无卡8/8长度预检完成，正恢复原服务做原生预检及8例新条件。旧v2不重跑。最新状态见PROJECT_PROGRESS和pilot_v3/ITERATION_REVIEW_20261010.md。下文只等待人审/不追加任务是旧阶段限制，已被自主实验授权替代；仍不SFT、保持冻结Actor、人工gold0与74预留来源组边界。

> **最新复审：** 研究者随后授权Codex代为仔细审核并复审，8例、63项适用检查、16条指控与8项建议均已完成双轮Agent审核。见[复审摘要](../experiments/faithbench_monitor_v0/pilot_v2/REVIEW_SUMMARY_27B_20261009.md)，逐例原文及两轮变化在private/text_review_v2_27b_20261009/agent_review_2pass_20261009/REVIEW.md。同一助手、非盲审、非独立人审；人工gold/训练仍0，原6/8接口指标不改，无新增GPU任务或SFT。下一步讨论未决标注口径与正式来源组划分，不重复推理。

> **2026-10-09 21:34续接结果：** 当前实例 `connect.bjb2.seetacloud.com:53248`，hostname `autodl-container-ylgygfuaq4-534f0ec5`。同版本后端恢复、52项hash及正式权重SHA通过；RTX4090加载与8/8原生模板核验成功，同8例已各生成一次。8/8 JSON解码，110处显式编号存在，6/8完整接口；两例为finding/check不一致和非法检查状态。19份产物备份hash一致，服务21:34:27退出、显存0 MiB，已告知可以关卡。下一步独立人审；不重跑、不SFT、不执行Actor动作。详见[27B报告](../experiments/faithbench_monitor_v0/pilot_v2/RUN_REPORT_27B_20261009.md)，无卡准备/36712为历史记录。

## 阅读顺序

1. 根目录[AGENTS.md](../AGENTS.md)：研究决策、GPU、未提交工作及卡顿处理要求。
2. [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md)：当前状态和历史阶段的边界。
3. [现行主方案](Actor_Monitor_MVP_Protocol.md)：离线Monitor验证后再做在线干预，Actor保持冻结。
4. 本页。
5. [pilot_v2说明](../experiments/faithbench_monitor_v0/pilot_v2/README.md)、[27B运行报告](../experiments/faithbench_monitor_v0/pilot_v2/RUN_REPORT_27B_20261009.md)、[27B聚合结果](../experiments/faithbench_monitor_v0/pilot_v2/RESULT_27B_20261009.json)、[8B聚合结果](../experiments/faithbench_monitor_v0/pilot_v2/RESULT_8B_20261009.json)；涉及来源和部署再读[27B无卡准备报告](../experiments/faithbench_monitor_v0/pilot_v2/PREPARATION_27B_20261009.md)。
6. 涉及设计依据时再读[机制讨论](MONITOR_MECHANISM_DISCUSSION_20261008.md)、[相关论文与可复用方法](MONITOR_RELATED_WORK_AND_IDEAS_20261009.md)、[中文标注规范](../experiments/faithbench_monitor_v0/ANNOTATION_GUIDELINES.md)。不需要重新开展相同下载或调研。

## 当前任务与授权

研究者已授权：简化Monitor接口 → 同8例冻结8B对照 → 更强模型未训练基线 → 待人审数据准备，随后明确授权Codex仔细代审并复审。8B/27B生成、可读核对材料及双轮Agent审核均完成；下一步讨论未决口径与正式来源组划分。独立人审仍未进行，不重复生成。

本轮用户已开RTX4090，16 CPU/120 GiB核验通过；模型服务PID3391和运行器PID3917均已退出，显存0 MiB，用户已获知可以关卡。原始响应及启动/退出/模板记录保存本地private；后续GPU状态应重新只读核验，不能自行开卡或追加任务。逐请求耗时合计151.2951秒，不含下载、加载、审批等待及收尾。

实际SFT还不能开始：独立人审确认0、gold空、训练记录0，正式训练量和来源组划分未确认。8例是开发诊断，包含同图条件及前缀，不能当8个独立测试样本，不能兼作独立测试和训练。74个Monitor预留来源组保持不动；B0-D正式gate仍`ACTOR_B0_D_INCONCLUSIVE`。不执行Monitor提出的Actor动作，不追加Actor训练或重跑工具。

## 本轮学到了什么

| 阶段 | 结果 | 解释边界 |
|---|---|---|
| v1，冻结Qwen3-VL-8B | 8/8生成与JSON解码，0/8完整接口；38处引用仅4处有效 | 审核范围、引用、状态和可执行性都存在失败；原响应保留 |
| v2，同一冻结8B | 8/8生成与JSON解码，8/8适用范围，86处引用编号均存在，4/8完整接口 | 另4例非法finding类型；仍有证据语义错误，不是准确率50% |
| 27B无卡准备 | 整份权重hash、官方后端与私有运行库校验通过，版本检查成功，8/8词表与长度预检通过 | 未加载推理权重或生成；显存、原生服务模板及审核质量尚未知 |
| 27B v2实际运行 | 8/8生成/JSON/适用范围，110处显式编号存在，6/8完整接口；8/8原生模板一致 | 非准确率；finding/check及状态失败，仍有证据语义问题，未训练/执行反馈 |

v2将机械工作交给代码：固定不适用checks、case_id和总体decision，编号还原原始pointer/quote；模型负责适用检查的语义判断、定位、缺口与反馈。原v1解析器继续拒绝非法字段/动作，不修复模型答案。编号存在只能证明可定位，不证明引用支持指控。

8B仍会把非方向偏离当冲突、自设high/元数据门槛、预算0误判提前STOP、把首次CALL补证判断为证据不足。上述诊断等待人审，不自动写为gold。STOP审核保持现有规范：资源耗尽与证据充分分开，不能预算0仍要求补证；CALL前缀不使用当前CALL结果、未来步骤或未来STOP。不要自行新增多数投票、固定两工具、用完全部工具或置信度阈值。

8B→27B同时改变代际、量化、运行后端；重复惩罚窗口也可能不同（原生默认最近64 tokens，Transformers按已有序列）。后续差异不能只归因于参数规模。

## 文件位置：保留原布局，不重新准备输入

| 用途 | 本地路径（相对仓库根） |
|---|---|
| 当前接口与运行器 | `experiments/faithbench_monitor_v0/pilot_v2/` |
| 必须冻结的协议实现 | v2 `protocol.py`、`prompt.md`、`prepare.py`、`run.py`；其他依赖见准备manifest的`protocol_hashes` |
| 旧v1失败基线与报告 | `experiments/faithbench_monitor_v0/pilot_v1/` |
| 当前8例准备包 | `experiments/faithbench_monitor_v0/private/pilot_v2_locked/` |
| 8B v2原响应及runtime/log/launch | `experiments/faithbench_monitor_v0/private/text_review_v2_8b_20261009/` |
| 27B最终六份部署凭据 | `experiments/faithbench_monitor_v0/private/remote_preflight_v2_27b_20261009/` |
| 53248交接/同版本恢复凭据 | `experiments/faithbench_monitor_v0/private/clone_handoff_20261009_53248/` |
| 27B原响应、运行记录和待人审诊断 | `experiments/faithbench_monitor_v0/private/text_review_v2_27b_20261009/`，19份远端产物hash一致；gold留空 |
| 8例待人审诊断材料 | `experiments/faithbench_monitor_v0/private/human_review_v2_diagnostic_20261009/`，含`CASE_REVIEW.md`与`review_queue.jsonl` |
| 技术边界测试 | `tests/test_monitor_pilot.py`、`tests/test_monitor_pilot_v2.py` |

`private/pilot_v2`、`private/pilot_v2_lf`是早期未使用的跨平台准备目录，最终使用`pilot_v2_locked`。旧目录、原日志、原输出不覆盖。准备器有已有目录保护；不要为了接续重复运行prepare_dev或prepare。

本地可先执行默认校验（不加载模型）：

```powershell
python experiments/faithbench_monitor_v0/pilot_v2/run.py --input-dir experiments/faithbench_monitor_v0/private/pilot_v2_locked
```

协议阶段全仓库69项测试已通过；后续部署辅助脚本语法检查通过。本次仅整理文档，不重新跑模型或更改实验。最新Git HEAD为`aaeaf2f`，当前v1/v2代码、报告、测试及若干文档仍未提交；这些磁盘文件才是当前进度，不要按HEAD恢复。私有逐例材料被Git忽略，有大量其他缓存/第三方文件，不能批量清理或`git add .`。本次不自动提交、推送或创建新对话。

## 当前服务器及隔离环境

- 最近核验入口：`connect.bjb2.seetacloud.com:53248`，hostname `autodl-container-ylgygfuaq4-534f0ec5`，现有密钥可用；36712/33082为历史实例。地址会随克隆变化，不能当永久入口。文件不包含密码/私钥/令牌。
- Monitor运行根：`/root/autodl-tmp/monitor-pilot-20261009/`；代码在其中`experiments/faithbench_monitor_v0/pilot_v2/`，输入在其中`experiments/faithbench_monitor_v0/private/pilot_v2_locked/`。
- 27B公开准备根：`/root/autodl-tmp/monitor-v2-public-20261009/`，模型文件`Qwen3.5-27B-Q4_K_M.gguf`。
- 本轮完整启动参数为公开准备根`deployment_prepared_20261009.json`中的原`server_argv`与`runner_argv`；服务cwd必须为公开根`runtime/llama-b11517`。已完成，不重复启动；本地有完整launch记录。
- 官方后端：`runtime/llama-b11517/llama-server`。**不能直接裸跑**：Ubuntu22系统库不满足要求，必须使用凭据中的`runtime-noble`私有ELF loader及library-path。版本/帮助均已成功核验。
- 原Actor venv：`/root/autodl-tmp/mini-faithbench-v0/actor-venv/bin/python`，不改依赖；基础CPU Python为`/root/miniconda3/bin/python`。
- 原Actor根：`/root/autodl-tmp/actor-b-schema-20261007/actor_b/`，冻结模型Qwen3-VL-8B-Instruct revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`，未Actor SFT。
- 53248仅经授权清理旧权重半成品后曾剩约17.46GB，随后恢复后端；空间读数为历史值，需重新核验。本轮开卡实际cgroup16 CPU/120 GiB；无卡会收紧，主机nproc/free输出不代表容器可用资源。

## 关键hash与本轮已完成GPU步骤（历史执行清单，不重跑）

- 最终8例v2 manifest：`a0cea96066cc0b20f25e5dd57e1b5489b6a302dd6ac720774760016f85b23a17`。
- 原输入JSONL：`a93ed4d266c9848e991c940463c0280b170086c14c8042f56809b613d343bbba`。
- 27B权重：16,740,812,704字节，SHA `84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806`；HF revision `3221f178a6b842d04f1fb42f1c413534adcc0a6a`。
- llama.cpp b11517 commit：`8a1a9b5126126e5228b95fa909d4b08fac65e8b3`。
- 部署凭据SHA：`0872e3486a948a3f169fb046cff29877cc52f831842089757c09bf43a740638f`；8例词表预检SHA：`3b7084fc10fffc5d5945ab20fe9e1f9766bddeef84e4c463d84109b91f99e9e1`。全部包hash与六份凭据hash见27B准备报告。

1. 只读核验当前实例、GPU/实际内存、磁盘、关键代码/输入/部署凭据、现有输出目录和进程，避免重复启动；若是克隆，按AGENTS.md做交接。已有16GB权重无需重新下载。
2. 用户已开卡才执行`server_argv`。计划GPU layers99、context24576、单并发、flash attention on、batch512/ubatch256、thinking off；只监听`127.0.0.1:8089`。先检查加载日志、显存、服务health和模板，不将CPU长度预检当显存通过。最长输入加预留输出15,498tokens，CPU模板渲染为Python Jinja2，原生服务渲染仍待核验。
3. 加载失败或前提不成立时，停在该步骤，展示资源/日志证据；不擅自改模型、量化或实验设置。常规进程排查和可逆修复可以直接做。
4. 核验通过后运行`runner_argv`：同8例、单次独立上下文、纯文字、greedy、seed42、最多4096输出tokens、repetition_penalty1.05、无格式重试。不执行Monitor反馈。
5. 保存全部原响应、解析失败、runtime、启动参数与日志；备份至新的private目录并核对两端hash。统计接口指标与待人审语义问题，不能把模型预审当准确率。确认进程退出/GPU释放后及时告知研究者可关卡，更新进度。

实际27B输出目录：`/root/autodl-tmp/monitor-pilot-20261009/outputs/text_review_v2_27b_20261009/`，已完成8例。成功启动/模板/退出记录在outputs/launch_v2_27b_20261009_53248_cwd；首次失败在无 `_cwd` 的目录，均已备份。输出已有内容，不能覆盖或重复启动。下一步使用本地待人审材料。

## 卡顿处理：研究者反复强调的要求

远端命令、下载、安装或实验超预期时，主动检查自己的进程、最新日志时间/大小、GPU/CPU/内存、网络和实际已完成字节；至少每60秒给有意义的状态。没有输出不等于还正常进行，不依赖用户打断。确认停滞后终止自己的进程或切换已核实替代路线，保留旧日志/半成品并说明残留；先核对PID，不能误杀其他任务。

这次重启中断下载后按真实断点恢复；大分段低速转64MB队列，整份SHA已成功。ModelScope文件SHA相同但测速差，未作为正式来源。源码编译被Killed后不在0.5CPU/2GiB环境重复，而用官方包及私有运行库解决兼容性。**这些步骤已经解决，不要重做下载或编译。**

本机默认sandbox命令曾因helper setup失败，已授权步骤通过`require_escalated`执行；自动审批超时不代表命令已经执行，要先核对状态。PowerShell曾启动崩溃，随后恢复，必要时可用`cmd.exe`处理原生ssh/scp。原生cmd中的复杂远端引用曾被bash当成整段文件名；优先上传短脚本，再以绝对Python路径执行简单SSH参数，不将用户文本整体当命令或把密码写入参数/文件。

## 可粘贴到新对话

交接整理后的验证：主要入口44个本地链接均存在；v2默认校验`preparation_valid=true, cases=8, model_loaded=false`，冻结协议与输入保持一致。

> 项目在 D:\Codex\AIGC。请读取 docs/SESSION_HANDOFF_20261009.md，按阅读顺序接续。当前27B Monitor同8例已完成，6/8完整接口通过，原始结果已备份；服务退出、GPU显存0 MiB，已提示可以关卡。下一步独立人审与正式来源组划分讨论。先核验当前实例和文件状态，不重复下载、准备输入或推理，不改冻结Actor，不启动SFT，不动74个预留来源组。长任务主动排查卡顿，至少每60秒报告有意义的状态。
