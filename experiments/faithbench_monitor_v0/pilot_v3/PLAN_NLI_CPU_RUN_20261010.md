# 已确认中文NLI CPU基线执行条件

2026-10-10。用户对二十既有摘录、多语NLI、约0.6GB公开权重、FP32 CPU分层诊断答复“是”。本文件固定执行条件，不改变Monitor既有状态或Actor。

- 模型MoritzLaurer/mDeBERTa-v3-base-mnli-xnli，revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`，模型卡MIT。官方树最新commit与镜像API一致；文件从可达镜像下载。单份model.safetensors预计557652046字节、LFS SHA `65af59b1ff4450b09ecbf13ca35c840dbf038b26ff8e10e5ea89ca724828ed1e`；另取README、config、added_tokens、special_tokens_map、tokenizer_config及tokenizer.json，不下载重复bin/ONNX/训练集。
- 输入仅先前生成的20去重premise/hypothesis，原片段不扩写，按原pointer/quote序列化，输入SHA `e5ff843eabcbd3f35f4eb3ca8bba7aadeaad253361ef4e135e549be8e7666508`。十三旧例/26选择条件，不当26独立观测；原审阅理由、目标答案和状态不入模型。完整来源层另审，叶子不证明来源缺失或列表穷尽。
- runner为已准备run_nli_candidate_v1.py，SHA `98d9b8235b6e2e7d2e624dc13222f070841f406607082025b941cea0aee9fe51`。复用现有隔离SFT venv依赖，使用fast tokenizer已有tokenizer.json；不安装依赖、改Actor环境或Actor/8B基座。local-only、safetensors、FP32 CPU、四线程、eval/inference_mode、batch1、恰20次forward，无训练或GPU调度。
- 在任何forward前预检20输入实际token长度<=config.max_position_embeddings 512，不静默截断；固定id2label 0 entailment/1 neutral/2 contradiction，保留每条原始概率及耗时。不调整阈值、不换模型筛选，不将neutral映射成未知、不产生训练标签或自动修复Monitor。
- 当前34132容器身份已核：原hostname、无旧runner/服务、GPU0。CPU/NLI根 `/root/autodl-tmp/monitor-nli-cpu-20261010`新建，不重复启动。Actor/基座环境25保护文件执行前后hash，输入/runner/模型两端hash；保持74预留组、GT、身份映射禁读，Actor反馈不执行。
- 直连HF不可达、实例镜像403；本机镜像可达，故本机下载并核验后传原实例。首权重连接提前EOF留36460779字节，已核1KB Range返回206，采用16MiB分块续传，完整LFS SHA通过才加载。所有失败保留，不以下载技术失败评价NLI效能。
- 长任务每60秒反馈，检查同一PID/session、日志、资源和半成品；无输出不自动重启。结果备份/hash、逐例细审与同助手非盲复审，非gold/非独立测试。二十组件诊断不代替原八例65片段、5冲突槽、STOP及最终处置一致性目标；模型不自动采用为教师或默认Monitor。

原问题与适配限制见[研究草案](../../../docs/research/MONITOR_BINDING_DIAGNOSTIC_DRAFT_20261010.md)、[准备范围核查](../../../docs/research/MONITOR_NLI_INPUT_AND_SCOPE_REPORT_20261010.md)。当前Goal工具仍blocked，用户已解除确认条件；工具不支持恢复，不误标目标完成。本轮继续全部已批准工作。
