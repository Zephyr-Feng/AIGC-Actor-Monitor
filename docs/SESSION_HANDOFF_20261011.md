# Monitor局部进展：2026-10-11交接

**最新状态：事实表12次配对诊断完成，GPU进程退出，可关卡。** 先读[结果报告](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BINDING_TABLE_PROBE_V1_20261011.md)及PROJECT_PROGRESS顶部。两组完整无截断/标签均5/6；条件+理由+标签4/6→3/6，完整绑定引用联合3/6→2/6，0修复、1新增矛盾。表明确第三缺值仍称全部100并支持；99=99.0例表组checks写严格大于满足但reason/拒绝正确；异常数缺失仍未做到未知/不满足区分。50ref/value抄对不保证正确推理。12同助手非盲首审复核0修改、非独立gold，六开发例不能泛化。worker8504于20:30:38前后保护通过后退出、GPU0MiB/0%，已通知关卡；8备份36,087字节hash通过，private binding_table_probe_v1_20261011含raw/日志/审阅/metrics/worker_exit/final25。raw SHA `218696a5ebff0e0ac4dfd748df15d73c2913500275f9672605b21a45a699e365`。prepare/deploy/preflight/launch/fetch/review/lock均完成勿重跑，旧freeze不改，36/74禁用、Actor不执行。下一步讨论必要条件选择、三值判定与判断汇总分开验证，可核验约束设计及新预算须按第1条讨论确认；无新任务在跑，完整Monitor目标未达成。下方运行中和待开卡是历史。

**运行中：事实表12次配对推理worker8504已单次启动。** 用户“一直开着卡”，14601同实例4090空闲核过；6新增上传/95hash及12远端CPU长度通过，新binding_table_probe_v1_trial/operation。不要重跑prepare/deploy/preflight/launch，从control_binding_table_probe_v1.py status接续；完成后fetch/保护hash及进程GPU退出即通知关卡，再按冻结设计逐例语义首审复核保存。0训练、36/74未用、Actor未执行，下方待开卡已解除。

**最新状态：事实表12次配对诊断已获批，本地材料冻结，等待本轮开卡。** 先读PROJECT_PROGRESS顶部、[执行设计](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_BINDING_TABLE_PROBE_V1_20261011.md)及[准备报告](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BINDING_TABLE_PREPARATION_V1_20261011.md)。同六例两条件唯一差异是核验事实表；两组1024预算，不复用旧384 raw当基线。事实表只含16字段与6身份，无关系/最终答案，提供人工字段选择/关联/缺失辅助，不等于模型自建表。12CPU输入1111–2253/目标111–222无截断、93本地依赖hash和freeze8通过，输入SHA `63278a0347df9301029d9badcb85a1942510d363c87a73fd68d93dd64ed3dc45`。新private binding_table_probe_v1_20261011和三脚本已保存，prepare完成不可重跑，deploy/preflight/launch/fetch均未执行；未上传目标、0新请求/训练、未读36或74。已告知4090用卡5–10分钟，收到开卡和有效入口后从control_binding_table_probe_v1.py deploy/preflight/launch接续，每步顺序检查、不临时加题；完成备份/退出核验即通知关卡，逐例事实/关系/理由/引用首审复审。Goal工具实查paused，未自行恢复；完整目标未达成。旧前缀事后核查已补报告及posthoc_prefix_freeze4；旧raw、审阅、final22不变。下方为历史阶段。

**最新状态：六例紧凑绑定base预检完成，GPU任务退出，当前无需卡。** 先读[结果报告](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BINDING_COMPACT_PROBE_V1_20261011.md)和PROJECT_PROGRESS顶部。6次推理/0训练，三简单关系完整且联合正确，三复杂384截断；第三百分位缺失时已输出“全部条目100：满足”，缺失步骤错误，最终标签未生成，不能猜成误支持。条件文字/对象绑定仍未忠于缺失证据，紧凑目标可装入预算不等于模型会执行。6首审/同助手非盲核读0修改，raw SHA `d6e8aa493f6205e3c0d2868ee32d2e1ccb4119ef3c443c42825c50c5f6f04de8`，私有binding_compact_probe_v1_20261011保存8备份/审阅/metrics/worker_exit/final_audit。worker7085于19:48:35核前后保护后退出，GPU0MiB/0%，已通知关卡；旧保护/adapter/协议及新freeze不变。只用原训练6题，非独立gold/对照/泛化或SFT验证。完整goal active未完成；接续讨论必要绑定范围与缺失条件监督，新增条件另确认，不再prepare/deploy/preflight/launch/fetch或追加请求。下方运行中和blocked为此前历史状态。

**当前运行：用户确认精简并开卡，六例基座预检worker7085已单次启动。** [冻结方案](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_BINDING_COMPACT_PROBE_V1_20261011.md)，输入SHA `a92dc9087bf5516d4ab7bc709db5796059145af7c59889dc61b106a971ae04dd`，新私有binding_compact_probe_v1_20261011。仅6次冻结base推理、0训练，完整原payload不变、目标111–222tokens且不进入model input；prefix1076–1949、本地/远端一致，无截断，六新文件部署91hash通过。14601同hostname，4090开启空闲、14GB可用；预计5–10分钟。goal已由用户恢复active；下方blocked是历史。不要重复prepare/deploy/preflight/launch，先control_binding_compact_probe_v1.py status，完成后fetch及备份核hash/进程退出/GPU0并通知关卡，再六例事实/关系/理由首审与同助手非盲复审。此为可实施性预检不是训练或泛化证明，完整目标未完成。

**当前goal接续位置：blocked，等待输出形式取舍。** 六例/长度核查已完成；第一次发现三例超过384并提问、第二次只读核查、第三次当前核查均未收到人类确认。本轮重新核freeze10与长度freeze5 hash通过，后两轮没有新技术进展或活跃模型任务；已授权步骤用尽，不追加新材料/推理/训练/远端调用。依据AGENTS.md第1条，输出设计和预算变化须讨论确认；将goal设blocked，完整目标仍未完成，下面active是历史记录。待用户选择先精简六例并CPU核查、先讨论字段取舍，或保留详细形式并讨论扩大输出预算；未授权新训练，也无需开卡。旧六草稿/长度报告/冻结原实验保留，不重跑prepare或GPUlaunch。

**最新无卡核查：六例详细目标有3例超过旧384输出预算，先讨论简化形式。** [长度核查](research/MONITOR_EVIDENCE_BINDING_LENGTH_AUDIT_20261011.md)实测紧凑正文228–616tokens，全体100支持590/缺失616、异常数缺失427，最后judgement首token587/611/422。不能原样沿用384做验证再把截断归为推理失败；其余三例正文能放下不保证实际生成。尚无新prompt/目标/预算，0模型调用/训练/远端/预留题内容读取。原六例及tokenizer hash不变，新增output_length_audit_v1.json/代码/报告单独保存。建议先保留原稿与完整输入、压缩六例答案中的重复信息而保留关键绑定和核验，再CPU检查；输出设计变化待人类确认。完整goal active未完成，前一轮六例和本轮新长度证据均实质progress，无需开卡。

**最新接续：用户已批准，6个证据绑定→关系核验草稿完成，无需GPU。** 先读[六例讨论稿](research/MONITOR_EVIDENCE_BINDING_DRAFTS_20261011.md)与PROJECT_PROGRESS最新条目。只沿用72训练中的6题，原输入/Actor/主张/标签不变，新目标明确返回范围、同对象身份与字段值或缺失、必要条件核验及理由；两支持/两反证/两缺失，五原型，例1/2同组配对不是独立样本。16字段及6身份绑定、六同助手非盲首审/再次核读、两缺失兼容反例对通过；不读36预留题内容/74真实预留，不做新模型请求/训练/远端调用。私有evidence_binding_drafts_v1_20261011保存drafts/validation/semantic_review/freeze，草稿SHA `6e6fb3765cb7efd42fdb21c32d82658c967d67e99dcbb450dbe41fb873f67eae`；原SFT26/posthoc10冻结hash不变。新目标不是现行接口或可直接训练数据，绑定路径不是新E/S规范；尚未模型验证，不自动重写72题或运行训练。用户“可以，你进行吧”解除下面6草例待确认；下一步讨论草稿/输出长度及验证方案预算，完整goal仍active未达成，不重复已完成prepare或GPU任务。

**最新无卡接续：既有SFT事后诊断已保存。** [失败追溯/token分析](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_POSTHOC_AUDIT_20261011.md)排除第三缺值/全称缺失完全漏训：20失败已连72训练与三次日志；类型已覆盖回归32题两adapter均29正确，未覆盖16题普通16/关系14。Q02关键数值投影与3条已训练缺失例相同，但prompt非同一；Actor/数值组合差异与平均loss无法判因果。144目标新增962token全部reason，判断值144/遍不变、逐题占比4.583%→3.442%，非实测token loss/梯度。0新增推理/训练/材料/远端；旧审阅不改，新posthoc产物独占保存。当前等用户确认6个无卡监督草例（只沿用训练72，不读/训练预留36），不因自动goal继续擅自改监督；goal active未完成，无模型任务或GPU需求。

**最新状态：两种理由监督SFT已完成并保存，当前没有GPU任务。** 先读[结果报告](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_COMPARISON_V1_20261011.md)及项目进度最新条目。432更新/204新生成、252首审复审完成；联合回归41→普通45/关系43，预留34→32/28，两组不通过候选门槛，不默认采用。worker2434于17:24:29完成并退出、GPU0MiB/0%，21文件含两adapter/raw已备份核hash，已通知关卡。85依赖/25保护/旧adapter3/50协议/9执行freeze不变；首审713a4663…、复审91cba101…完整hash见报告。下一步讨论实际对象/字段/值绑定与局部关系监督，当前无新增训练条件授权，goal active未完成。下方“运行中/待确认预算”是历史阶段；禁止重跑新prepare/deploy/preflight/launch或旧96/192请求。status仅必要只读，fetch已完成也不重复。

**运行中：2026-10-11 17:07，worker2434单次启动。** 新relation_sft_comparison_v1_trial：37新文件/92hash及远端CPU检查通过，计划432更新/204生成。只执行新控制器status/fetch，不重新prepare/deploy/preflight/launch；完成前不覆盖新目录，Actor仍冻结。运行完成、GPU退出与备份细审以最新进度为准。

**最新接续：用户已回复“可以”批准两组各216更新、204新推理及上传14601实例。** [执行冻结](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_RELATION_SFT_COMPARISON_V1_20261011.md)已保存，本地CPU预检/旧48结果兼容通过，goal active。当前4090经只读核验开启且空闲；从新relation_sft_comparison_20261011部署、远端CPU预检、单次训练接续，不再询问已批准预算。尚未启动GPU任务，下面“训练待确认/无需开卡”属于此前历史状态；执行期间每60秒更新，结束备份核验后通知关卡。

工作区`D:\Codex\AIGC`。本页为最新入口。关系前测96请求与提示对照192新请求已完成；用户随后明确“同意”材料准备，原材料授权阻碍已解除。72训练/36预留材料无卡阶段现已完成，0新模型请求/训练，目标尚未完成。当前从[材料完成报告](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_MATERIALS_20261011.md)及[训练预算讨论稿](research/MONITOR_RELATION_SFT_EXECUTION_DISCUSSION_20261011.md)接续，新增训练预算与载荷上传尚待确认，当前无需开卡。

**最新接续：** 有效材料私有relation_sft_materials_v2_20261011，108题/27组，72训练（两种正确目标同输入标签引用）/36预留，原48固定已见回归。27缺失反例对/54完整情况、2542引用指针、216目标首审及同助手非盲复审通过；真实tokenizer输入814–1770、目标最长92、mask/最终三字段顺序正确。cases SHA `4107a766d8b0969205d9d4c6d55207b3dd28030c06b194ba26113ba5c563f1da`；manifest SHA `c1a8786e9ac0b297b637fdf17c783b24c5aadc1a7d5eacbb1d1360f8a5e00b03`。v1因6条关系目标额外事实未引用而停用，旧文件保留；仅v1 tokenizer_cache/python_libs作为CPU资产复用，不用v1题。prepare_relation_sft_v2.py、validate_relation_sft_v2.py、preflight_relation_sft_materials.py已执行，不重复排他创建。待确认两组新adapter各216更新、204新推理、同曝光并报告28.26%监督token差异，预计4090用卡25–40分钟；确认后先完成新运行路径/CPU预检，再核实例/资源和开卡，旧基座/adapter/结果不改。此处优先于下方历史待材料确认说明。

**提示实验保存记录（材料准备前）：** 先读[提示对照结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_PROMPT_PROBE_V1_20261011.md)、[关系前测结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_PROBE_V2_20261011.md)及[关系SFT讨论稿](research/MONITOR_RELATION_SFT_DISCUSSION_20261011.md)。base标签+理由基线33/48→理由先43/48、增加关系41/48；adapter31/48→30/48、36/48，且96条新输出均不遵守理由先顺序，关系版仍5显式/1隐含矛盾。192首审及同助手非盲复审完成，0修改，非独立gold。修复与新增失败均报告，不默认采用提示或adapter。私有`relation_prompt_probe_v1_20261011`保留raw/首审锁/复审/metrics/备份hash/worker_exit；raw SHA `d7e6ff6fa8ad13c646325678872810b0fb8b3be0a2c88dcb0be4d9961ef240d4`，首审SHA `419a935a31eeeb968972a90482759c39ae96c9853532f5a731032454c67772f4`，复审SHA `b2e72267000b9c3f7f428c5ca05be839234b3055c5d0fb6dad6f83cc5e31dd96`。两已完成任务均不再prepare/deploy/preflight/launch。当时待确认的72训练/36预留材料现已由用户同意并完成；现行接续以顶部材料报告/训练预算为准。

**当前实例与退出状态：** 入口`root@connect.bjb1.seetacloud.com:14601`，hostname `autodl-container-8fc0409877-3d080f20`，密钥连接和克隆交接已核，密码未保存。远端部署目录无Git元数据，不称干净checkout；25保护/adapter3/50旧协议hash通过。前测worker1413与提示worker2165均已退出；14:32:55提示推理后保护核验完成，后续只读核GPU0MiB/0%，已通知可关卡。这是最后状态快照，不保证未来仍开启GPU。前测/提示各7备份hash通过、提示9本地freeze不变，保存clone_handoff与worker_exit。原控制器不改，新前测使用`remote_control_clone_14601.py`；本轮无正在运行的模型任务，禁止因旧记录重跑。

## 阅读顺序

现阶段先读顶部[两种理由监督SFT结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_RELATION_SFT_COMPARISON_V1_20261011.md)、项目进度最新记录与主方案，再按以下顺序读背景。材料与预算已批准且实验完成；以下历史“待确认/运行中”不作为续跑指令。完整goal active但未达成，新增监督与训练条件仍需讨论。

**新实施核查：** [SFT兼容性记录](research/MONITOR_RELATION_SFT_COMPATIBILITY_AUDIT_20261011.md)核旧manifest/七条目标/四代码hash：旧实际训练reason已经在status前，新三字段若继续嵌套键排序会反而先judgement。固定最终assistant文本顺序、适配评估解析与20步覆盖问题是必要实施条件；未改旧代码、未生成新题、未训练。当时的材料确认已由用户明确同意；当前材料已完成，待确认的是新的训练预算与载荷上传。

1. [项目进度](PROJECT_PROGRESS.md)、[协作原则](../AGENTS.md)、[当前主方案](Actor_Monitor_MVP_Protocol.md)。Actor冻结，74预留组/GT/身份映射禁读，反馈/Actor动作不执行；每60秒有意义更新，用卡由用户开启。
   已完成阶段先读[前测执行冻结](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_RELATION_PROBE_V2_20261011.md)与[提示对照执行冻结](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_RELATION_PROMPT_PROBE_V1_20261011.md)，它们是运行条件历史，不是待开卡续跑指令。私有前测`relation_probe_v2_20261011`输入SHA `3f867425575bacdb3fdfbfdd52459fb8e025d401542d06afa3121f3a43e15082`，提示输入SHA `31e8f53940349dac701f308908df89ace39938866ef3ae550cc5c811dbb3f688`。96+192已完成，v1 Q04准备问题版本始终停用；禁止重新prepare/launch。当前从SFT讨论稿接续，保持已有冻结与raw。
2. [简单判断24请求筛查](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_MINIMAL_SCREEN_V1_20261011.md)：R1/阈值简化条件正常；adapter云层加入上下文后错用路径；缺列表存在标签正确但数量属性理由错位。
3. [输入分组/局部校验实验](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BOUNDARY_PROBE_V1_20261011.md)及[执行冻结](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_BOUNDARY_PROBE_V1_20261011.md)：22新推理+2同提示/模型旧raw复用，24逻辑条件细审复审。分组后本轮adapter原/肯定云层误支持消失；规则挡住两条路径错配，R1证据有/缺能相应接受/拒绝。仅局部开发进展，候选不默认采用；引用冗余、部分理由过宽、对象内容正例误伤率未验证。
4. [12片段扩大验证结果](../experiments/faithbench_monitor_v0/pilot_v3/REPORT_BOUNDARY_EXPANSION_V1_20261011.md)及[执行冻结](../experiments/faithbench_monitor_v0/pilot_v3/PLAN_BOUNDARY_EXPANSION_V1_20261011.md)：12片段/6轨迹、7支持/5依据不足，48条件=38新增+10精确旧raw复用。adapter普通门牌/方尖碑/云层三误支持在分组后拒绝，标签符合9/12→12/12；但9区域分组理由错误地由max100+异常数9推全部100，列表漏中间引用。base分组误把图像真假局限套到9区域观察主张而误拒绝；两展示门牌均引用过长耗尽384预算，JSON失败。新增36/38、合并46/48完整格式，输入未截断；不修复重采样。窄规则挡3语义错配，不能验证数量理由/误拒绝或内容正例误伤率。48项首审锁/同助手非盲复审0修改，非独立gold；25保护/adapter/50协议及7备份hash通过。此前两审批拒绝在用户具体“授权”后解除，无重复运行。背景见[扩大与推理方法讨论稿](research/MONITOR_EXPANSION_AND_REASONING_IDEAS_20261011.md)，过程监督/RL仍仅讨论。
5. 需要此前SFT/CPU NLI/结构展示失败与S范围候选背景，再读[10月10日交接](SESSION_HANDOFF_20261010.md)及其中链接。S规范仍未被确认/启用，本轮分组实验不代表采用S。

## 用户已明确的职责

用户已要求按证据关系学习初步方案实验，前测、提示对照和已确认72训练/36预留材料阶段均已完成。当前只待确认训练预算：同base、同材料/顺序的两个新adapter，各216更新、204新推理、约25–40分钟4090；28.26%监督token差异公开报告，非严格等监督量。物体内容真实支持正例、独立来源、冲突/STOP仍是缺口，材料完成不等于完整目标解决。

Monitor围绕Actor具体主张、所用依据和推理连接审核，不先独立分析全部证据形成真假结论。Actor解释是被审内容，不能自动作为工具事实；必要上下文、完整同源返回和相关反证仍须保留。正确标签不等于正确理由；路径/编号不能独自证明内容语义，异常数/检查数不能替代列表项数。改用“大概率/可能”也不自动满足依据要求。

## 已保存与防重跑

- 代码：`pilot_v3/minimal_screen_v1.py`、`boundary_probe_v1.py`、`run_boundary_probe_v1.py`、`boundary_expansion_v1.py`、`run_boundary_expansion_v1.py`、`assemble_boundary_expansion_v1.py`。扩大准备器/运行器已执行，不再运行prepare或launch；新目录使用exclusive创建。默认Monitor未更改，v3 adapter未采用/合并，0新训练。
- 私有目录：`experiments/faithbench_monitor_v0/private/minimal_screen_20261011/`、`boundary_probe_20261011/`、`boundary_expansion_20261011/`；包含输入、freeze/输入核查、raw备份与hash、首审锁及同助手非盲复审。扩大目录另有授权/统计、报告对应记录，原始输出不修复；不是独立人审/human gold。
- 扩大输入SHA `60425b069fcbaf4ed1a94b705a73f749f7cbf927ce7b401ef4b9f74fb7a6dfde`，38新raw SHA `c34c5d8547b1e51de1365a3018028a391477391ffbe8381033117c2863027fda`；48合并SHA `c6f536fae484deeb342ab905d4c806997b50929606bb45a0a596793198a0872b`。首审SHA `efedccd09701d2ef05555488410eec93d4940855a279babc531fa17f0a035540`，复审SHA `864e31bab836b6c81ed92c5aedb2b36a6a929b19cf1279695cc738ce4c5b573d`。旧保存checkpoint是当时快照，进度/导航后续更新不代表旧raw/冻结代码被修改。
- 新实验输入SHA `64d8151fecf7438b6bf8848f13a4d688e38961b82681f23678801cfe7acc480c`；22新raw SHA `bd37cb5393d5d7cd465e773b5f1d7bb29f1a17352d8ac7cb426cfcbedfdb26a0`。25基座/Actor环境保护文件、adapter前后及50旧协议hash均通过，7远端备份文件hash一致。
- 当前已核实例为14601，hostname `autodl-container-8fc0409877-3d080f20`。34132/hostname `autodl-container-ylgygfuaq4-e9cf5d54`仅是旧扩大验证的历史实例。worker1413/2165均已退出，已通知关卡；新训练前须重新核实例与资源，不从历史状态推断GPU开启。
- 远端项目`/root/autodl-tmp/monitor-pilot-20261009`，隔离模型环境/实验根`/root/autodl-tmp/monitor-sft-smoke-20261010`。`minimal_screen_v1_trial`、`boundary_probe_v1_trial`、`boundary_expansion_v1_trial`均已完成；扩大operation/cpu_preflight保留，旧adapter在`evidence_contract_v3_trial/adapter`。

旧扩大验证、96前测、192提示请求及72训练/36预留无卡材料阶段均已完成保存。接续顶部训练预算稿，用户尚未确认训练预算/载荷传输，当前无需开卡；不要重跑任何完成的prepare/validate/preflight/launch。Actor冻结、74预留真实组/GT/身份映射禁读、反馈不执行；完整Monitor稳定收益尚未证明。
