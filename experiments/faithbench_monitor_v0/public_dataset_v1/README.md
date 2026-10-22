# Monitor公开能力数据首版

已完成实际构建，交付见[数据卡](../../../docs/research/MONITOR_PUBLIC_DATASET_BUILD_20261016.md)。数据位于仓库已忽略的`data/monitor_public_v1_20261016/built_v3/`。

**默认入口是`train.primary.sft.jsonl`，不是`train.sft.jsonl`。** 前者为12,141条RAGTruth人工来源监督；`train.visual_aux.sft.jsonl`是3,638条带图反馈选择辅助数据。RAGBench已降为`silver_candidate`，默认不训练。先读`tiers.json`、`audit.json`与数据卡。

中文指令/状态保持，英文来源原文不伪装成人工中文翻译。基础任务为错误跨度定位、候选证据支持及视觉反馈选择；完整中文反馈生成、项目工具边界与STOP监督仍缺。没有模型训练或能力提升结论。

脚本仅本地数据处理：`fetch.py`获取选定公开子集；`build.py --output 新目录名`创建独占新构建；`export_tiers.py 新目录名`分级；`audit.py 新目录名`逐条检查及生成训练/开发样例；`test_build.py`为四项合成检查。使用`D:/python/python3.11/python.exe -B -X utf8`。Parquet解析库独立位于数据目录runtime，不安装到Actor环境。

`make_mix.py`和`pre_review_*`只记录抽查前的混合尝试，不用于默认训练；原始及失败资料保留。分词长度和实际图像token预检属于选定训练模型后的必要准备，不得静默截断。不要运行旧项目含哈希核验的准备/训练脚本。
