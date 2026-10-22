# 分栏核验CPU准备与复审

2026-10-10 16:12。用户已批准分栏核验。本阶段GPU使用0、模型请求0、optimizer0；修正已观察到的证据范围矛盾，尚不构成模型能力结果。

`typed_source.py`新增准备阶段固定的返回/能力审查类别和两个互斥引用栏。能力卡不能作为实际返回依据，工具名称不能作为能力定义依据；模型不能改类别。准备时复用既有JSON pointer解析核原值/来源/时点，中文解释仅为最低要求。`typed_source_portable.py`固定提示词JSON键顺序；旧single_source、实验输出和指标不改。

65条R14记录从原R7八可见包重建一致，逐叶子原值/来源/时点通过；16项CPU检查覆盖已观察到的范围风险。准备12个已用自然片段与1个只删实际列表的受控版本，目标单独保存、无模型输出蒸馏。四条否定回到完整返回检查，21个目标引用核对原包。R14冻结的43协议文件hash一致，不将该范围误称整个Actor代码树。Actor未修改，74预留组/GT/身份映射未读。

首次复审发现保存records的键排序与首次prompt的插入顺序不同，prompt逐字节重建失败；未推理。旧 `typed_source_diagnostic_inputs`、首审及锁保留。另存portable版本，13提示词/schema重建一致、13来源副本与原包/唯一删除操作一致，目标0修改。复审为同助手非盲复审，不是gold或独立复审。

可继续版本：private `typed_source_diagnostic_portable_inputs`，manifest SHA `265f7a21c5bf50396d59437e6814e6134e2b1098d3bc349000c8d70614b5ba5c`；首审 SHA `c1ade5e791674b15b520b7eb6aecec8734357b50ef1fac82693f835bab5be0c5`，复审 `typed_source_fixture_portable_review_second.json`。旧manifest `3db1b3f39313c1929709642ddb76dc265d559a80bdb6a99c2d184477ea75f8a4`、首审 `0e2ae862867807a4105361a05ae08373bf0eb79448fb0899d8f4bbc6d89b5eee` 保留为准备失败记录。

仍需模型验证：引用合法不等于引用内容支持理由；中文文字不保证解释质量；缺列表时未知仍是语义判断。三条高偏离限定语继续隔离。方案是类别、提示词与输出接口组合，不能单独归因某个参数或键顺序。没有新SFT收益证据，v1/v2均不采用。

34132只读核验：hostname `autodl-container-ylgygfuaq4-e9cf5d54`，4090显存0MiB/利用率0，无推理服务或旧训练runner，余盘15,047,827,456字节，没有重复加载。下一步先冻结已有模型有界推理条件，核模型/后端及输入长度，告知用卡窗口，再运行。完整Monitor最终聚合、冲突遗漏、STOP与干预方向仍未完成；goal active。
