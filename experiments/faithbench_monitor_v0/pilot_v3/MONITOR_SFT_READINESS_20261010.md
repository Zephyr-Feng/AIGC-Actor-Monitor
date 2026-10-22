# Monitor SFT准备条件与待确认方案

2026-10-10 11:01核验。本次研究者已授权条件允许时启动Monitor SFT，旧交接“不SFT”不再作为永久禁令。当前仅完成只读准备条件核验，未安装/加载/训练，不改Actor环境或权重。

实际条件：18203 RTX4090 24,564MiB，现27B服务占17,519MiB；数据盘剩15,565,819,904字节。27B仅Q4_K_M GGUF，基础Python有torch2.12.1+cu130，无transformers/peft/trl/bitsandbytes，不能直接当现成Transformers训练checkpoint。冻结8B safetensors可读取，架构Qwen3VLForConditionalGeneration/qwen3_vl，四分片共17,534,339,512字节，大小与原交接一致。Actor venv有transformers4.57.4，无后三个依赖；此环境仅查看包元数据，不用于安装或训练。

拟定对象：建立独立Monitor环境和新adapter目录，只读加载8B基础checkpoint，训练Monitor adapter，不保存回基础模型、不改Actor推理配置。复用基础权重文件避免磁盘不足；“复制基座”应指独立模型实例/adapter，而不是复制17.5GB权重。具体是否选择文字8B、多模态8B或27B尚待研究者确认。

拟定数据边界：新受控诊断仅12fixture/4原型；原8例和另12终态均为相关开发数据；人工确认/gold0。不能直接把七轮有错误的模型输出当训练真值。可准备另存、逐条来源核验并同助手复审的agent_proposed_silver及清楚标注的synthetic targets；它们不升级为gold、不改变原silver。74预留组/GT/身份映射不读。若用开发集训练，后续这些来源只能作为回归/训练诊断，不能再称独立测试；正式来源划分和未见来源验证另行确认。

第一阶段只试工程可行性：验证中文输入/输出契约、loss只覆盖Monitor回答、输入不含期望标签/未来结果/GT、文本模板兼容、base hash不变。候选QLoRA需实际确认当前CUDA/torch、bitsandbytes及Qwen3VL架构兼容，不能以已有GGUF显存占用估算训练峰值；先20步左右资源试跑，记录OOM/梯度、显存与吞吐，再决定是否全训。20步只是拟议上限，未冻结配置、训练数据或实际时长。

推理服务和训练不并发。确认启动后先备份诊断、核验自有PID并停止27B服务，再在独立环境试训，给出实际峰值和时长。当前未停止PID1503，未开始试跑，因此没有可信的SFT用卡估时。不会直接启动长epoch或下载新27B checkpoint。

待决定事项已通过界面询问：仅准备并复核后启动、允许隔离8B小试训、或等待人工标注/正式划分。最终以研究者回复为准，不把未回答当批准。

优先查阅官方[Qwen3-VL训练入口](https://github.com/QwenLM/Qwen3-VL/tree/main/qwen-vl-finetune)与[PEFT量化训练说明](https://huggingface.co/docs/peft/developer_guides/quantization)。本页是准备条件和方案记录，不代表这些代码已在当前实例复现，不安装整个框架。
