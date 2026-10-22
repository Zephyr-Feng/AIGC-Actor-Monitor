# 关系监督材料准备完成：72训练、36预留

2026-10-11。用户明确同意后完成无卡准备；设计见[已确认方案](../../../docs/research/MONITOR_RELATION_SFT_DISCUSSION_20261011.md)，实现记录见[准备计划](PLAN_RELATION_SFT_MATERIALS_V1_20261011.md)。当前有效版本为私有relation_sft_materials_v2_20261011，未启动训练或模型推理。

## 可用于下一阶段的材料

|项目|数量与条件|
|---|---|
|训练输入|72题，6关系原型、3来源组件，支持/无法支持各36|
|两种目标|普通正确理由、显式必要关系理由；同题、同标签、同充分引用、同输出顺序，各72条|
|预留输入|36题，3关系原型、2来源组件，支持/无法支持各18；不进入训练|
|固定回归|原48条reason_first开发题，与已完成base旧raw的prompt完全相同|
|组结构|9原型×3参数组×4受控版本，27组；数字变体不是独立样本|

训练：全体异常、全体百分位100、max/median严格比较、score舍入、明示阈值、limitations归因。预留：区域编号成员、同一区域bbox坐标、实际列表长度。来源组件和原型均整体分开，没有同组跨训练/预留；共同字段与生成器仍共享结构。全部为明确标识的抽象fixture，来源锚点和108题相对父抽象题的字段修改清单已保存，0真实新工具返回、0图像生成、未读74预留真实组/GT/身份映射。

两种目标都给正确理由。例如“检查7项、7项达到95阈值”：普通目标说明本次统计覆盖全体，关系目标明确异常数必须等于检查数，并对照7=7。缺第三项百分位的题两组都拒绝，关系目标说明max、median或异常计数不能补出缺失逐项值。训练目标是简短可核的证据连接，不以错误理由或空泛对照制造差异。

## 核查与修订

程序核查108题、2542实际字段指针、27Actor控制、27缺失题的兼容反例对与54完整情况。每个缺失题都具有观察完全相同、主张成立与不成立的两种完整情况；相关计数、比例、max/median、排序、局部分数/signal、坐标边界一致。两组标签/引用/prompt一一相同；目标与最终assistant_text均固定reason→return_reference_ids→judgement。

首稿v1通过结构/数值检查，但审阅发现6条missing关系理由额外提及已有信息而未引用；修订为一般关系约束，输入/标签/引用/分组完全不改。v1代码、材料、manifest与preparation_issue保留，0模型请求，停止作为训练材料；v2 revision_audit逐项证明仅6条关系reason变动。不是改题挑结果，也没有覆盖旧锁。

首审覆盖81非Actor题的两个理由及实际引用值，27Actor控制另核事实、主张、目标不变，共108题/216目标。修订版全部接受为工程监督材料，同助手非盲复审216目标0更改；机械验证辅助审阅，未使用额外模型教师。作者与审阅者同一助手，0独立人审，不能称human gold、独立语义验证或正式泛化评估。

## 实际tokenizer与预算

只读复制现有已核AutoDL快照的6个tokenizer/config文件，共11,498,916字节，全部与旧保护hash一致。没有上传新fixture文本或读模型权重、修改远端环境。阶段v1目录中的tokenizer_cache/python_libs仅作为本地核查资产保留，v1题目停用不代表缓存停用。

本地阶段目录安装tokenizer依赖，核心版本transformers4.57.4、tokenizers0.22.2、jinja2 3.1.6；[固定Transformers版本来源](https://pypi.org/project/transformers/4.57.4/)与实际下载/hash见pip_install_report。没有安装torch或改全局/Actor环境；pip对原全局ipykernel/ipython缺psutil的提示不属于本阶段依赖修复，本地tokenizer流程正常完成。

108输入/216目标全部经真实tokenizer核查：新输入814–1770 tokens，目标最多92 tokens，训练最长1836≤4096；输入加384输出预算不溢出。前缀mask及助手后缀监督正确，实际解码后的JSON顺序与答案一致；原48回归的本地输入长度逐条与旧远端raw一致。

|每遍72条|普通理由|关系理由|
|---|---:|---:|
|有效助手监督tokens（含回合结束）|3404|4366|
|助手目标范围|31–69|47–92|
|完整训练序列tokens合计|104706|105668|
|最长完整训练序列|1821|1836|

关系理由多28.26%监督token，完整序列token多约0.92%。相同条数/更新次数不能称完全相同的监督预算。后续若用相同曝光，比较的是两种完整监督方法，不独立证明显式关系形式是唯一原因；具体处理需在训练前确认。

## 保存与下一步

私有v2保留cases/design/modifications、两train、36预留/48回归、27兼容反例、manifest/input_validation、revision_audit、tokenizer_preflight、首审/复审及旧日志预算参考。新代码prepare_relation_sft_v2.py、validate_relation_sft_v2.py、preflight_relation_sft_materials.py；已完成的prepare/validator/preflight排他创建，不重复运行。

- cases SHA256 `4107a766d8b0969205d9d4c6d55207b3dd28030c06b194ba26113ba5c563f1da`。
- manifest SHA256 `c1a8786e9ac0b297b637fdf17c783b24c5aadc1a7d5eacbb1d1360f8a5e00b03`。
- 首审SHA256 `d99540aef4e4e8a4e1891393006c351510ef8a88267184c4f8753f5a0298171e`。
- 复审SHA256 `2ee126184e817d60afdde709160765acd78d79d6d4d8bce1541a50e17900e15a`。

下一步见[训练预算讨论稿](../../../docs/research/MONITOR_RELATION_SFT_EXECUTION_DISCUSSION_20261011.md)，待确认同曝光SFT对照、请求预算及新载荷传输。当前0训练/0模型请求，GPU无需开启，默认Monitor/Actor不变。材料/来源都已见过，预留只表示不进这次SFT；本阶段不证明模型已改善，更不证明物体内容真支持、冲突/STOP或完整Monitor收益。
