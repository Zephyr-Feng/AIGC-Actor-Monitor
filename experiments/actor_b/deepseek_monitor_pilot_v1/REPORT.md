# DeepSeek Monitor → Actor：FULL20 闭环配对实验

日期：2026-10-12。执行完成，GPU已释放，本轮停止。依据[已批准方案](../../../docs/research/DEEPSEEK_MONITOR_ACTOR_CLOSED_LOOP_PILOT_PLAN_20261012.md)；准备与故障恢复历史见[PREPARATION](PREPARATION.md)。

**本轮没有观察到检测提升。C（DeepSeek反馈）的有效正确终态为6/20，B（一般提醒）为13/20，净减少7例、下降35个百分点。主要下降来自C的9个非法终态。** 在原A合法、且比较双方均得到合法终态的样本中，没有观察到真假标签纠正。C更常修改部分证据表述，但完整联合修复仍为0，不能把部分修复计为闭环成功。

## 实验范围与对照

固定原FULL审计20图，来自15个来源组；锁定语义审核后读取选中20图既有GT：real 6、fake 14。没有新增样本、生成假图、训练、运行新检测器或使用74预留来源组。沿用既有图像、工具实现与缓存，来源和许可见[复用记录](../../faithbench_monitor_v0/REUSE_REVIEW.md)。

- A：历史Actor结果，18合法、2非法，保留原始输出及历史格式重试，不重新生成。
- B：一般规范提醒后，由同一历史节点独立续跑。
- C：一次DeepSeek自动审核的完整可见content原样交付，再由相同历史节点独立续跑。

B/C保留原始最后STOP、图像、历史证据、工具卡和共同后缀；独立深拷贝状态。剩余工具预算0/1/2分别3/14/3图。按请求才回放真实工具缓存，未来缓存不提前进入模型；新增非法动作立即记失败，不修JSON、不替换标签、不追加重试。20次Monitor顺序及每图B/C先后以seed20261012冻结。

Actor：Qwen3-VL-8B-Instruct基座，revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`，BF16、无adapter，greedy、repetition_penalty=1.05、seed20261006、max_new_tokens=768。原历史最多一次格式修复与新增0次不同，因此A为历史参照，主要比较是共同新增规则下的C对B。

Monitor：服务alias `deepseek-flash`（官方文档对应DeepSeek-V4.1-Flash），thinking enabled、reasoning_effort high、max_tokens=16384，流式保存。服务alias不等于固定权重快照。Monitor只有文字证据和Actor推理，未接收原图/裁片、GT、身份映射、预审或人工纠错。Actor保留原图及实际收到的裁片。

## 主要结果：失败保留在20图分母

| 分支 | 合法终态 | 有效正确/20 | 非法或未完成 | 合法输出条件下正确率（附项） |
|---|---:|---:|---:|---:|
| A 历史结果 | 18 | 14/20（70%） | 2 | 14/18（77.8%） |
| B 一般提醒 | 18 | 13/20（65%） | 2 | 13/18（72.2%） |
| C DeepSeek反馈 | 11 | 6/20（30%） | 9 | 6/11（54.5%） |

| 配对（左→右） | 错/失败→正确 | 正确→错/失败 | 双方正确 | 双方错/失败 | 净变化 |
|---|---:|---:|---:|---:|---:|
| B→C | 1 | 8 | 5 | 6 | −7/20（−35个百分点） |
| A→C | 0 | 8 | 6 | 6 | −8/20（−40个百分点） |
| A→B | 0 | 1 | 13 | 6 | −1/20（−5个百分点） |

C相对B新增正确的唯一一例是blind_040：原A已正确，B输出非法inconclusive，C合法real且正确；这属于终态恢复，不是纠正原A错误。C相对B丢失的8个正确终态为blind_001、003、015、018、030、043、050、053，均因C分支失败。

原A合法的18图另行比较纯标签变化：B/C双方合法9图、A/C双方合法10图、A/B双方合法17图，三个比较的“错→对”和“对→错”均为0。所有在原A合法基础上得到合法B/C终态的预测标签都与A相同；其余样本单列失败，不投影成真假结论。

原A非法两例：blind_010（GT real），B补真实互补缓存后形成合法fake/low，但仍错，C仍非法；blind_020（GT fake），B仍非法，C补缓存后形成合法real/high，但仍错。格式恢复没有带来正确恢复。

### 混淆与分类召回

| 分支 | GT real→real / fake / 失败（n=6） | GT fake→real / fake / 失败（n=14） | real召回 | fake召回 |
|---|---|---|---:|---:|
| A | 3 / 2 / 1 | 2 / 11 / 1 | 50.0% | 78.6% |
| B | 2 / 3 / 1 | 2 / 11 / 1 | 33.3% | 78.6% |
| C | 1 / 2 / 3 | 3 / 5 / 6 | 16.7% | 35.7% |

## 失败链条与证据修正

API阶段20份均完整、非空、finish_reason=stop、无拒绝字段；0 Monitor阶段失败、0重试，全部原样进入C。不是因为API反馈截断导致C缺失。

| 新Actor协议失败 | B | C | C具体样本 |
|---|---:|---:|---|
| CALL_TOOL的最终字段非null | 0 | 3 | blind_001、043、050 |
| STOP的final_verdict为null/inconclusive | 2 | 5 | blind_003、010、018、030、053 |
| 非法JSON，缺分隔符 | 0 | 1 | blind_015 |

B失败为blind_020和040，均非法STOP结论。失败raw和此前有效新增步骤完整保留；没有对非法终态做反事实标签评分。

事前助手预审冻结为16错误、1合理（blind_019）、3未决（blind_026、040、050）。结果审核隐藏条件标识、打乱40份副本，按同一预审和完整联合标准审阅。

| 16个原错误样本的修复 | B | C |
|---|---:|---:|
| 完整联合修复 | 0 | 0 |
| 部分修复 | 7 | 14 |
| 未修复 | 9 | 2 |

“部分修复”可以与新非法终态、残余错误或新错误同时存在；不是成功正确检测数。完整联合要求证据方向、综合、真实返回保留、局限与动作均满足，单独降置信度/加免责声明不算完整修复。两分支在唯一合理样本上均无实质误伤、未追加工具；n=1不能估计误伤率。三个未决保持未决，不能根据事后GT改成错误gold。

有新增语义或协议问题的分支为B 9、C 14（可重叠于部分修复，属于本轮助手判据统计）。例如C盲043撤回global错误real方向，却在CALL中给出low置信度而失败；C盲030修正global方向并补到真实real信号，最终输出null verdict而失败。C盲003撤回非方向global的fake归因，但把实际real互补证据写为未决，最后非法STOP。C盲016纠正“没有工具”的原预算错误，却声称互补工具不适用于单一未校准模态，与工具卡的弱/不完整证据适用范围不符。C盲027仅降置信度，保留global假方向和错误预算陈述。

20份Monitor内容审核分为supported 3、mostly_supported 6、partly_supported 9、incorrect 2；这是开发材料的助手评阅分层，不是独立自动审核通过率。两个明确问题：

- blind_012：错误认可阈值/权重解释，遗漏或认可global与真实方向的伪冲突，还给出“故方向选real”，违背不指定最终标签的要求。
- blind_027：继续认可“两条工具结果支持”和方向一致，未撤回非方向global的fake归因，对汇总数据作过强推断；仅建议降低置信度。

另有反馈一边说global无真假方向，一边仍称其与local“方向一致”或“冲突”；预算剩余不能自动证明必须继续取证。完整反馈、Actor采纳变化、工具与终态逐例记录见私有审核，未按语义质量筛选C。

### 审核争议和接口限制

1. **像素可见性不同。** Actor历史确实收到裁片，Monitor只读文字。复看blind_001的天空/方尖碑/云、blind_010门牌53、blind_015塔尖/屋顶，相关对象实际存在。不能因为工具文字没有对象名就判Actor捏造对象；应区分像素观察与把观察错误归为工具检测结论。其他未核像素的对象主张保留未决。
2. **top-3与阈上异常不同。** blind_001为1/6阈上异常，但“三个高偏离区域”可能指相对排序前三，并不必然表示三个过阈值。保留冻结预审，事后注明这项歧义，不据此额外扩大错误数。高置信度措辞也不自动等于捏造fake概率。
3. **confidence约束不一致。** 原schema与parser允许STOP的final_confidence=null；冻结新增共同后缀/Monitor提示要求low、moderate或high，较parser严格。部分反馈把历史null置信度当硬非法，是提示/parser接口解释不一致；不追溯判A失败，不临时改parser重跑。C五个STOP失败实际是非法final_verdict，三CALL的非null最终字段也违反原CALL规则，不能用该争议豁免。
4. **不能仅归因于8B规模。** 本轮实际组合涉及反馈内容、Actor接收/状态更新、补证据后的取舍及接口要求。C更复杂的状态修订与更多反向证据可能与非法未决终态相关，但未作因果隔离。Monitor自身仍有语义问题，不能据此宣布DeepSeek已可靠或“仅8B太弱”。

## 来源组和历史曝光

| 来源组别名 | 图数 | A有效正确 | B有效正确 | C有效正确 |
|---|---:|---:|---:|---:|
| group_01 | 2 | 2 | 2 | 0 |
| group_02 | 1 | 1 | 1 | 1 |
| group_03 | 1 | 0 | 0 | 0 |
| group_04 | 2 | 0 | 0 | 0 |
| group_05 | 1 | 1 | 1 | 0 |
| group_06 | 2 | 1 | 1 | 0 |
| group_07 | 2 | 0 | 0 | 0 |
| group_08 | 2 | 2 | 2 | 2 |
| group_09 | 1 | 1 | 1 | 0 |
| group_10 | 1 | 1 | 0 | 1 |
| group_11 | 1 | 1 | 1 | 0 |
| group_12 | 1 | 1 | 1 | 1 |
| group_13 | 1 | 1 | 1 | 0 |
| group_14 | 1 | 1 | 1 | 0 |
| group_15 | 1 | 1 | 1 | 1 |

已核此前六例审核原终态精确重合：blind_003/E1、blind_001/E2、blind_010/E3。

| 曝光分层 | n | A正确/失败 | B正确/失败 | C正确/失败 | C对B净正确变化 |
|---|---:|---|---|---|---:|
| 已知六例原终态重合 | 3 | 2/1 | 2/0 | 0/3 | −2 |
| 其余开发案例，曝光未穷尽核清 | 17 | 12/1 | 11/2 | 6/6 | −5 |

全部20图均为助手此前观察的开发材料；其余17不称未见集，其他Monitor/SFT曝光未穷尽建立。分层有来源组交叉，不能把来源组数相加或把同源图当独立重复。本轮不做显著性检验或总体泛化准确率宣称。

## 计算、成本与运行审计

| 项目 | 实际 | 冻结上限 |
|---|---:|---:|
| Monitor请求 | 20，无重试 | 20 |
| 新Actor请求 | B 21、C 29，共50 | 80 |
| 新缓存返回 | B 1、C 9，共10 | 40 |
| Monitor输出tokens，含思考 | 49902 | 327680 |
| Actor新增输出tokens | 22142 | 61440 |

10个新缓存均为complementary_forensic_analyzer，B只在blind_010返回一次，C在9图各一次。没有真正重新运行检测器。B输入102352/输出8911，C输入154171/输出13231；纯生成B 229.92秒、C 341.68秒，共571.60秒，不包含权重加载/processor/备份。新工具返回与标签改善不同，C增加补证但没有原合法样本的成功标签纠正。

Monitor输入101434 tokens，输出49902含43139思考，缓存命中11520、未命中89914；20请求累计346.61秒，可见反馈508–899字符。600字为建议，没有机械截断。请求起点UTC 11:39:33–11:45:02，落在官方低峰时间；按[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)低峰用量估算$0.04346286，高峰保守估算$0.08692572，**未核账单**。事前输入字节额度502296、总输出上限下的高峰费用额度$0.5439048≤$1。

80资产（20原图、60裁片）、原历史及实际缓存来源核验；40分支全processor CPU预检，初始4134–6198 tokens，所有可用工具排列和未来生成余量的最长上下文上界11253≤262144，无截断、删图或降精度。CPU不加载权重、不推理。torch2.12.1+cu130、Transformers4.57.4与执行一致。

独立远端根目录`/root/autodl-tmp/deepseek-monitor-actor-v1-20261012`，当前实例核验为connect.bjb1.seetacloud.com:14601 / autodl-container-8fc0409877-3d080f20。101部署文件hash通过，未发送身份映射、GT或预审JSON。最终清单复查发现`preaudit.py`随依赖脚本上传，其中有人工预审判断；它未被worker调用，但不应声称服务器完全没有预审内容。50次完整模型输入/构造逻辑核验未发现预审判断进入请求；此次是部署范围缺口，保留记录，不更改冻结文件或补跑。CPU9407、唯一GPU worker9582均已退出；最后状态40终态、50请求、10返回，GPU0MiB/0%，无计算进程，已告知可关卡。25模型/环境保护文件前后和预期一致；3 CPU与155运行备份hash一致。

原始输出先锁定，再审阅40隐藏条件副本和20反馈，60处精确引文/40份工具卡与预算核验通过，然后锁定语义审核，最后才为选中20图解析GT。评价器仅先提取非选中行sample_id，不解码其标签；74预留未使用。审核者为同一助手，熟悉案例、文风及运行输出可能暴露条件，**非真正盲审、非独立人审、非独立gold**。

中途新命令审批服务因用量额度无法完成审批，已提交API仍正常结束。重置后通过同一审批入口恢复，没有绕过审批、重复API或补跑。旧实验和用户未提交工作保留。

## 产物与结论边界

私有产物均在Git忽略的`experiments/faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/`：

- [GT配对评价](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/evaluation.json)、[揭示条件后的语义摘要](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/revealed_semantic_summary.json)、[曝光分层](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/exposure_results.json)。
- [原始锁定](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/raw_output_lock.json)、[语义锁定](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/semantic_review_lock.json)、[完整审核与争议](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/semantic_review.json)、[引文核验](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/citation_verification.json)。
- freeze/execution_freeze、完整inputs/历史A/80资产、20 API request/state/SSE/response、原样feedback_delivery、40分支全部输入/raw/实际缓存/terminal、CPU/部署/保护/备份，以及[最终审核](../../faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/final_audit.json)。未记录凭据。

原始锁定SHA256：`38ccbc2cbb93b9afdec2b0c57e55655068a82df2e78f38b75feb4f5dde63177b`；语义锁定：`189e5d4a3878fb1d75d42d47fe71db5ac99201560c680dfb8fb552fa5864ab9c`；语义审核：`d6ff02da4ea710b800fecf5038486c809ee3d7b92f3ac40c66520af712a96028`。

本轮支持的观察是：自动反馈能引发更多局部证据表述修正和补证据动作；当前完整闭环的有效检测表现下降，完整推理修复未通过，协议失败和反馈语义问题都需纳入解释。它不证明所有Monitor方法无效，也不证明换更大Actor即可解决。没有按结果调提示、修接口、强制选标签或再跑一轮；后续研究方向留待讨论。
