# Actor/Monitor：只读必要证据

这是选假设的索引，不是整轮必读背景。当前摘要由 `loop.py context` 提供；动态运行状态以 PROJECT_PROGRESS 顶部为准。本文从本地已核读材料提炼，未重新检索或独立认证论文结论。

## 当前研究问题

固定 Actor，检验本地可训练 Monitor 是否能凭实际取证证据，帮助同一个 Actor 修复强Actor自审未修的实质推理错误，并保护正确内容与未知。识错、建议可执行、Actor采纳及最终整稿正确是不同环节。最终解释改善不自动等于真假分类改善。

现用 Monitor 为00373；定向00012只有有限未知处理开发收益，不是全面更优模型。历史相同 checkpoint 编号需用完整目录消歧。未有当前本地Monitor整体净收益的独立验证基线。历史外部DeepSeek M2有自然纠错个案，普通外部审核也能修，不能写成当前本地模型独有收益。

## 真正影响决策的教训

| 已观察到的事实 | 下一轮如何思考 | 只在相关时读 |
|---|---|---|
| 10/17格式/锚点大幅改善，五核心0/5完整过；出现反向改引用与捏造建议 | 先看原错误是否完整修复、是否新增损害；不能用loss/JSON替代语义 | experiments/faithbench_monitor_v0/monitor_quality_v2/FEEDBACK_REPORT_20261017.md |
| 10/19混训纠错51→55/128，但无错空问题6→0/7；初始化与比较基线不同 | 保护正确内容要单列；先核同起点/提示/损失与来源格式捷径，再谈因果 | experiments/faithbench_monitor_v0/monitor_quality_v2/FAVA_MIXED_RESULT_20261019.md |
| 344条整稿混训仍在训练内漏主目标；训练监督自身有错、覆盖不均 | 区分没学会目标与没泛化；先审监督和输入/输出对齐 | data/monitor_supervision_audit_20261021/REPORT.md |
| 修订监督并增加到776条/97更新、167018监督token后，002仍漏五处，006/008仅部分修复 | 增量配方失败；停止按此配方盲加epoch。样本数不等于自然来源数（仍11取证来源），也不能断言模型无能力 | data/monitor_relation_coverage_v1_20261021/RESULT.md 与 FROZEN_PLAN.md、profile.json |
| 无关STOP/历史结构说明引发越权指控，范围简化仍未解决 | 审核对象/时点是候选解释，现有反证不支持继续同源换词 | data/monitor_review_scope_v1_20261021/RESULT.md |
| 旧视图遗漏且编辑器保护unresolved_conflicts，导致伪冲突残留 | 先判断接口是否允许完整修复，再训练模型；同强Actor同视图/动作边界比较 | experiments/faithbench_monitor_v0/monitor_quality_v2/full_action_feedback.py |
| 旧脚本顶层可制造approved再启动；观察超时曾易被误当任务失败 | 不导入启动器；只读检查现有PID/输出后决定，不重复启动或把旧授权续用 | docs/SESSION_HANDOFF_20261020.md（定向搜“旧启动器”“超时”） |

## 语义边界

- global 表征偏离本身无真假方向；local有方向但未校准，不能抹去方向，也不能提升为来源证明。
- unknown/缺失不是no；未校准不是无方向；真实local/comp冲突不能被“消除冲突”模板抹去。
- 同源变体不算独立来源；训练内、开发曝光、未参与选择与独立人审分别记。助手审阅不是gold。
- 必须查看完整最终动作：reason、global解释、gap、unresolved_conflicts可能同时残留同一错误。只改对一句不等于整稿通过。
- 比较强Actor自审与Monitor反馈后的同Actor修订，控制信息、调用次数、提示、输出限长与编辑边界；硬件或输入不同要披露。

## 定向复用

- 当前验收与路线：`docs/MONITOR_NET_GAIN_PLAN_20261021.md` 的“具体接受/不退化”段；细节以原冻结方案为准。
- 协议：`docs/Actor_Monitor_MVP_Protocol.md` §6（Monitor）、§9（固定Actor路线）；无需全文重读。
- 现有接口：`experiments/faithbench_monitor_v0/monitor_quality_v2/actor_feedback_bridge.py`（输入、实际adapter/输出限长），`full_action_feedback.py`（完整视图与字段边界）；按改动搜调用者与对应test文件。
- CPU材料剖析：`data/monitor_relation_coverage_v1_20261021/profile.json` 的summary可复用；不要加载逐条全量。
- 文献方法索引：`docs/MONITOR_RELATED_WORK_RETROSPECTIVE_20261021.md`。CriticBench区分识错/纠正，CriticGPT控制虚构指控，FAVA区分冲突/不可核实，CFT提供具体批评监督，CRITIC强调外部验证；它们均不能替代本项目有效性证据。需要引用或改变方法时才核对原论文。
- 已有`.agents/skills/codex-autoresearch`需要干净工作区、单指标与自动Git回滚，本仓库大量未提交材料且有多维语义门槛，不直接运行或扩建它；不因此新增第二套控制框架。
