# 2026-10-12 对话交接：先明确DeepSeek Monitor的独立审核标准

本次交接仅整理已完成实验和讨论，不启动新实验。用户准备开启新对话。

## 当前接续位置

用户的最新目标是：**先验证DeepSeek能否有效担任Monitor，再讨论反馈对Actor最终表现的提升。** 用户目前卡在“如何确定Monitor输出的评判标准”，尚未确认新的样本、评分标准、通过门槛、费用或实验方案。

Monitor职责已明确：根据Actor当时可见的工具证据、Actor具体主张和推理，审核证据是否被正确使用；发现归因、方向、综合、冲突和动作问题，必要时给出修正反馈。不能把Monitor默认为重新独立判断图像真假、再要求Actor服从其标签。

新对话应先协助把评判标准做成可核对的例子与判据，并讨论确认。不要直接追加API、GPU推理、训练或改变旧结果。用户过去的开卡/执行授权对应已完成批次，不表示新实验自动获批。FULL20执行goal已complete；整体研究目标仍未实现，无正在运行的实验。

## 阅读顺序

1. 本文件、[项目进度](PROJECT_PROGRESS.md)、[协作原则](../AGENTS.md)。
2. [项目主方案](Actor_Monitor_MVP_Protocol.md)：研究定位与Monitor职责。
3. [具体正确反馈单例结果](../experiments/actor_b/feedback_pilot_v1/REPORT.md)。
4. [DeepSeek与8B六例审核结果](../experiments/faithbench_monitor_v0/model_comparison_v1/REPORT.md)。
5. [FULL20闭环报告](../experiments/actor_b/deepseek_monitor_pilot_v1/REPORT.md)及需要时的[冻结方案](research/DEEPSEEK_MONITOR_ACTOR_CLOSED_LOOP_PILOT_PLAN_20261012.md)。该方案已执行完成，不是续跑指令。

10月11日交接及更早SFT/提示/绑定实验保留为历史背景；其中active、待开卡、运行中等描述不能覆盖本页和进度顶部。

## 三轮证据实际支持什么

| 阶段 | 已观察到 | 没有证明 |
|---|---|---|
| 人工具体正确反馈→Actor，单例三分支 | T修复主要全局证据角色误用，保留局部真实信号，提出合法互补CALL；R/G未修复 | 未执行CALL或续跑到终态，未读GT；局限保留不全，完整联合修复未通过；不是最终检测提升 |
| DeepSeek/8B六例自动审核 | DeepSeek可见回答定位三个错误案例的核心问题，三个合理对照无实质阻止 | E1截断、E2建议medium接口不兼容，只有E3定位/理由/反馈均通过；三来源组、非独立人审，不证明Monitor已可靠或Actor收益 |
| DeepSeek→Actor FULL20完整闭环 | C更常部分修正证据表述并补缓存证据 | 最终有效正确下降，完整联合修复0；不能据此宣布所有Monitor无效或仅8B太弱 |

用户曾理解“前两个验证已经通过”。已澄清：前两轮是局部机制积极信号，完整通过条件并未全部满足；不能把后来失败简单归因为前提自相矛盾。

## FULL20最终事实

固定原FULL开发队列20图、15来源组；raw与语义审核锁定后只解码选中20图GT（real6/fake14）。74预留未使用。

| 分支 | 合法终态 | 有效正确/20 | 失败 |
|---|---:|---:|---:|
| A 历史结果 | 18 | 14 | 2 |
| B 一般提醒 | 18 | 13 | 2 |
| C DeepSeek原样反馈 | 11 | 6 | 9 |

- C对B：1例错/失败→正确，8例正确→错/失败，净−7/20（−35个百分点）；8个损失均C失败。唯一改善blind_040是恢复B非法终态，原A已经正确。
- 原A合法18图内，双方合法比较B/C为9图、A/C为10图、A/B为17图；纯标签错→对和对→错均0。推理存在错误不等于原标签必然错误。
- 原A非法blind_010、020出现部分格式恢复但结论仍错。
- C失败：3非法CALL最终字段非null、5非法STOP verdict为null/inconclusive、1 JSON语法错误。不能把9例全部叫普通JSON格式错误，或假定修格式即可恢复检测效果。
- 事前预审16错误/1合理/3未决；16原错误部分修复B7/C14、完整联合均0。部分修复可与失败/新错误并存；合理n=1无实质误伤，无法估计误伤率；未决不按事后GT升级gold。
- Monitor自身仍有错误：blind_012阈值/伪冲突/指定最终标签问题；blind_027认可global非方向证据支持fake及错误一致综合。其他反馈也有伪冲突/前后不一致。
- 20 API完整stop、0重试/修补/语义筛选；50新增Actor请求、10真实互补缓存返回，未超80/40上限。无训练、新检测器运行或新增格式修复。
- Actor为Qwen3-VL-8B-Instruct基座BF16/无adapter/greedy/768；Monitor官方alias deepseek-flash、thinking enabled/high/16384，服务alias不等于固定权重快照。
- 全部为已观察开发材料，审核同助手隐藏条件标识，非真盲、非独立人审或gold；已知六例终态重合blind_003/E1、001/E2、010/E3，其余17不称未见集。

完整逐例、来源组、曝光、token、成本、协议、保护与争议见报告，不需在新对话重新生成。API低峰用量估$0.04346286，未核账单。

## 最新讨论：评判标准的拟议方向，尚未冻结

用户问“怎么确定Monitor输出的评判标准”。讨论建议如下，**不是已获批的新评价协议**：

1. 从Actor当时可见的实际工具返回、工具能力边界、接口和预算确定判据；图像GT不决定推理是否忠实。
2. 对具体问题列“必须修复什么、必须保留什么、不能新增什么错误”，接受不同合理措辞，无须写唯一理想答案。
3. 分别评价定位、依据/理由、修正内容、过度纠正、可执行性，避免只凭关键词、降置信度或免责声明判成功。
4. 参考样本分明确错误、合理、无法裁决。工具能证明的方向误用/数值错误/接口矛盾可作为硬判据；证据充分性、是否必须继续等若没有明确停止政策，保留未决，不用助手偏好充当真值。
5. 先用已观察案例校准判据卡，由研究者复核对应关系与争议，再冻结标准评价新材料。已观察20图可辅助制定标准，不能反复调试后再作为独立验证集；新材料范围和已有公开数据复用先核，再讨论授权。
6. 可考虑将“核心错误修复”和“完整联合修复”分开：未复述全部局限不自动否定已完成的核心修复，需看遗漏是否导致继续误用。**该建议仅用于未来讨论，不更改旧报告、冻结判据或重新打分。**

示例判据：global工具明确不提供real/fake方向，Actor却写“global与local一致支持fake”。合格反馈应定位global方向越界、依据真实工具卡、撤回global的fake支持、保留local真实方向；不能顺势指定real或抹去有效局部证据。即使GT为fake，此推理错误仍成立。

参考判据卡建议字段：Actor具体主张 → 当时可见的原始证据/规则 → 成立或不成立的理由 → 可接受修正范围 → 未决事项。没有独立复核前，不称客观金标准。

尚待研究者决定：哪些错误属于核心/严重、合理样本怎样组成、视觉材料是否提供Monitor、充分性/停止政策是否可判、新样本与来源组范围、谁复核、样本量、通过门槛、API配置/费用、是否及何时接入Actor。不要自行设通过百分比或选新数据。

## 必须保留的限制与争议

- Actor曾收到真实裁片，文字Monitor没有像素。blind_001天空/方尖碑/云、010门牌53、015塔尖/屋顶实际存在。不能因为工具文字未描述对象就判视觉描述捏造；要区分视觉观察与错误归为工具结论。其他未核像素对象保留未决。
- top-3相对排序不等于3个超过异常阈值；“高置信度”措辞不自动证明捏造校准概率。非方向global不能作为相反真假证据；缺乏佐证不自动等于方向冲突；剩预算本身不强制继续。
- 原parser允许STOP confidence=null，新增提示更严格；部分Monitor把null置信度当硬非法，需记录接口解释歧义。C五STOP失败是verdict非法，三CALL非null最终字段也违反原规则，不能用该争议豁免。
- 最终部署复查发现含人工判断的preaudit.py随依赖上传；preaudit JSON、GT、身份映射未上传，worker未调用脚本，50完整模型输入核验未发现判断进入请求。已披露部署范围缺口，不称服务器完全没有预审内容，不隐去或补跑。

## 保存、服务器与防重跑

新闭环代码/报告：`experiments/actor_b/deepseek_monitor_pilot_v1/`。

Git忽略的完整私有目录：`experiments/faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/`。包含freeze/execution_freeze、inputs/历史A/80资产、20 API request/state/SSE/response、原样feedback_delivery、40分支输入/raw/return/terminal、CPU/部署/保护/备份、raw和语义锁、60引文、离线GT evaluation、曝光/语义摘要、final_audit_check.py和final_audit.json。旧实验及用户未提交工作保留，未commit/push。

关键SHA256：

- raw_output_lock：`38ccbc2cbb93b9afdec2b0c57e55655068a82df2e78f38b75feb4f5dde63177b`
- semantic_review_lock：`189e5d4a3878fb1d75d42d47fe71db5ac99201560c680dfb8fb552fa5864ab9c`
- final_audit：`4367d5a0be693c0ce2ea1d34a49ec0551a3caa7a14654ef73965a5bbcdf12c39`

final_audit保存的是实验结束时公共文档hash快照；本次新增交接和进度/导航更新在其后，属于正常文档演进，不重写旧审计或冻结。

最后核验实例：root@connect.bjb1.seetacloud.com:14601，hostname autodl-container-8fc0409877-3d080f20；地址可能随AutoDL克隆改变。独立实验根`/root/autodl-tmp/deepseek-monitor-actor-v1-20261012`。CPU9407/GPU9582已退出，最后GPU0MiB/0%、无计算进程；已通知用户可以关卡，不表示实例此后仍开卡。101部署/155运行备份/3 CPU备份及25模型环境保护核验通过。

20次API和40分支均已完成，禁止重新prepare/deploy/launch/API付费请求。密钥曾由用户提供、仅隐藏stdin内存使用，本交接不保存凭据，不假定新进程仍有凭据。当前整理/讨论无需GPU，不发起服务器操作。Ponytail full偏好持续有效，采用最小实现；没有授权新增goal或子代理。

## 可粘贴到新对话

> 请先读docs/SESSION_HANDOFF_20261012.md、docs/PROJECT_PROGRESS.md、AGENTS.md和项目主方案，并核对交接中三份实验报告。FULL20闭环已完成并停止，执行goal已complete，不能重跑。我的当前目标是先验证DeepSeek能否可靠作为Monitor，当前需要解决的是如何制定其输出评判标准。请从实际证据、工具能力边界和Actor规则出发，用已有案例帮我讨论可复核的判据卡，区分明确错误、合理与未决，以及核心修复、反馈正确性和接口可执行性。前两轮只提供局部积极信号，完整闭环C6/20、B13/20，不能称Monitor已可靠或仅Actor太弱。新标准、样本、通过门槛和实验尚未确认；先讨论，不改旧评分、不调用API、不运行GPU、不训练、不使用74预留。重要设计与数据/费用决定按AGENTS.md先确认。
