# 正确反馈帮助 Actor：无卡准备完成

日期：2026-10-11（北京时间）。用户已批准执行[单例方案](../../../docs/research/ACTOR_CORRECT_FEEDBACK_PILOT_PLAN_20261011.md)，本阶段只完成准备，尚无模型生成结果。

## 已完成与验证

从已盲化 FULL 审计包只取 blind_003。原 step_4 是合法 STOP；前三步工具依次为来源、局部纹理、全局表征，额度已用 3/4。四个步骤各一次生成，没有格式重试。原 STOP 的 raw 原样保留到共同前缀；未读取真实标签、identity_map、未来互补工具返回或74个预留来源组。

原图和三个裁片的 SHA-256 与原 input_fingerprint 4/4 一致。复用 `contract_replay.reconstruct_stop_context` 和 `actor_b_protocol.parse_action`，三分支完整前缀相同、分别深拷贝；三段反馈与批准方案逐字核验一致。冻结运行顺序为 **R → T → G**，随机化 seed=20261011。

结构检查通过：4图像引用顺序一致、无评价字段、原STOP可解析、虚构的未用互补CALL可解析、重复CALL被旧parser拒绝、分支修改不影响其他分支。三份新脚本语法检查通过。仅核查必要的结构风险，没有以结构检查代替反馈有效性验证。

完整多模态 processor 在远端 **CPU 内存** 中运行，CUDA_VISIBLE_DEVICES为空、离线读取既有模型快照，未加载模型权重、未生成、未训练、未写远端文件。当前入口只读核验为 connect.bjb1.seetacloud.com:14601，hostname为 autodl-container-8fc0409877-3d080f20；地址只是本次核验实例，不能当永久入口或开卡证据。

|分支|实际输入tokens|图像数|图像grid|输出上限|截断|
|---|---:|---:|---|---:|---|
|R 普通续答|4639|4|[1,64,64] + 3×[1,20,20]|768|无|
|T 具体反馈|4820|4|同上|768|无|
|G 一般提醒|4686|4|同上|768|无|

同一模型 config 的 max_position_embeddings=262144，三组输入+768均在范围内；这项检查不保证GPU运行不会OOM。图像处理保持冻结processor默认配置，没有删图、缩图或套用Monitor的4096上限。

盲化历史 STOP 前缀实际4155 tokens，原非盲运行记录4121，相差34；方案已允许盲化路径/ID的变化。本轮是同源盲化配对回放，不声称逐token重现旧运行。实际运行前应再核对三组CPU token IDs、processor资产哈希和环境。

CPU环境 torch2.12.1+cu130、Transformers4.57.4，与历史Actor runtime所记版本一致。模型revision与config哈希一致；本阶段未核验全部权重内容，也未验证BF16模型加载或实际输出能力。

## 部署缺口与处理

第一次直接检查发现旧Monitor根目录缺少 `contract_replay.py`，在加载processor前退出，0请求、0远端文件写入。记录保存在私有 preparation_issue.json。

随后使用 `preflight_memory.py` 将本地核验过的三个依赖模块、runner、输入和四个图像以SSH标准输入发送至远端内存。现存同名依赖必须hash相符；缺失文件记录为missing，不假装已经部署。完整CPU检查成功。

远端旧目录仍缺少 contract_replay.py、run_b0.py、system_prompt、schema、generation_config和tool_cards。**当前尚未部署GPU任务，也没有launch。** 开卡后应在独立的新执行目录部署本次输入、资产、runner及冻结依赖，避免填写旧Monitor目录；核对freeze通过再启动单一worker。可保持目录布局 `experiments/actor_b/...`、`experiments/mini_faithbench_v0/config/...` 和本方案private目录，以便runner解析ROOT；完整计划文件和逐项审核模板不进入Actor messages。

`control.py` 保留为首次直接核查实现，当前完整CPU入口是 `preflight_memory.py`。两者均没有GPU启动功能；不要重复运行已有完成的CPU入口覆盖结果。

## 保存与冻结

公开代码：pilot.py（prepare/verify/cpu/run）、preflight_memory.py（已成功的CPU内存检查）、control.py（原只读核查）。

私有目录：`experiments/faithbench_monitor_v0/private/actor_feedback_pilot_v1_20261011/`，沿用既有Git忽略规则。包含case.json、inputs.json、feedback.json、四个assets、structural_checks.json、freeze.json、cpu_preflight.json、cpu_preflight_hashes.json、review_template.json和失败说明。review仍pending，不提前填语义结果。

|文件|SHA-256|
|---|---|
|inputs.json|3ef59fad136b0e2ec64270251eee743d9a02055ef2d96814b98db0c111c8412a|
|freeze.json|34c23cee66db4ea1d6d7690342940450ae236536c90281c72c1c8b0d75878f68|
|cpu_preflight.json|79af84b25e3b9effd278f46fae40f3079be19e359f3c2e7500ce04a92f5dce83|

freeze保护输入、四资产、案例、反馈、审核模板、原Actor八个依赖及初始两脚本；cpu_preflight_hashes另外锁定成功CPU结果和新增preflight_memory.py。旧轨迹、旧Actor配置和旧Monitor产物未修改。

## 下一步

等待用户确认**本轮当前实例已开卡**。任务为冻结BF16 Actor的三次单步提议，RTX4090预计5–10分钟，0训练、0实际工具调用、每臂一次、无格式重试。先完成独立部署和输入/权重/资源核验，再单次执行。

三个输出完成后按方案逐项审阅，报告目标误用修复、有效证据保留、新增错误和动作合法性；同助手非盲审核必须明确标记。原最终GT不读取，判别标签变化不自动计为成功。退出核验后通知关卡、更新进度并停止；不扩样或改提示。

当前 **模型请求0 / 训练0 / 工具执行0**。没有 raw、runtime 或结果REPORT；Monitor研究前提尚未验证。
