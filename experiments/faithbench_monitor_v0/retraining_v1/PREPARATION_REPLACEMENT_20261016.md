# Qwen3.5-9B替代基座检验：执行范围

2026-10-16。用户明确“允许更换基座，卡仍然开着，换完基座之后继续检验”，替代基座决策已解决。goal恢复active；本批为基础能力诊断，0训练/教师API/Actor动作，不等于批准无条件SFT。

## 模型与隔离

唯一替代候选为后训练版[Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)，[官方模型卡及Apache-2.0许可](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/README.md)已核。保留未来视觉接口，但本批只输入旧文本，不运行视觉编码器取证，也不把视觉事实与工具归因混为一谈。

同实例`connect.bjb1.seetacloud.com:14601`；系统盘启动前约32.15GB可用，数据盘约14.49GB，4090空闲。新权重放在系统盘独立`/root/monitor-retraining-qwen35-20261016/assets/model/`，15文件共19,329,391,890字节，不删除/替换旧8B、27B、adapter或结果。系统盘现有剩余量足够本次推理，不能据此假定后续训练checkpoint空间充足。

HF远端直连失败，改用Qwen官方ModelScope仓库直接HTTP下载。仅检查文件长度、配置/许可证正文及后续权重格式/加载；不使用hub/xet下载器，不做任何摘要计算或核验。ModelScope LICENSE为11,343字节，HF元数据为11,544字节，实际Apache 2.0正文已审阅，不假称两份发布文件逐字相同。下载器首轮日志参数冲突发生在传输前；后续许可证字节差异触发停止，已完成三分片保留，只补缺失七文件。原失败脚本/日志保留。

新依赖仅放独立`vendor/`目录，由本批进程PYTHONPATH优先加载，不改旧venv。Transformers5.3.0、huggingface-hub1.3.0、typer-slim0.21.1、click8.1.8、shellingham1.5.4、annotated-doc0.0.4；复用原torch2.12.1+cu130/tokenizers0.22.2/bnb0.50.0等。两个wheel远端超时，改本地官方直下后SCP；不运行pip或带内置摘要/CRC核验的解包流程，不安装RECORD校验清单。CPU导入Qwen3_5ForConditionalGeneration成功；这不证明GPU推理或LoRA训练可行。

## 冻结请求与预算

- 原13条完整审核包，输入正文逐字复用历史base请求；不重跑8B对照。
- 原6条人工聚焦包，输入正文逐字复用刚完成的minimal请求；否定/缺失保留完整同源返回。
- 共19次，13主张/6旧来源组件；聚焦6条是其中子集，不算19独立主张。私有`retraining_replacement_20261016/requests.json`仅含id/model/view/user_text，不含答案/raw。
- 五字段协议、greedy、seed42、每条384新tokens、NF4 double/BF16、SDPA、4096总长度上界；原生模板显式enable_thinking=False，不增加隐藏思考预算。原input token长度重新记录，不假设跨架构模板相等。
- 新runner只读加载原始9B、冻结梯度，无adapter、不保存模型。相较旧8B经过prepare_model_for_kbit_training的推理路径，本批按原生推理保持非量化模块dtype；架构、模板、权重和运行库差异一并登记，不能将结果差异单独归因参数量。
- 预计GPU5–10分钟，15分钟OS硬上限，任一超长输入、加载失败或生成异常停止，不补采、不自动切换第二个候选/量化/思考模式。
- 结束核自有进程退出并告知可关卡，raw/log/部署源码备份后做同口径逐例开发复核；不以结构通过或标签匹配替代完整联合正确。

19条请求数量/分视图/唯一性/只含模型输入的自检通过，重复请求被拒绝。CPU分词与safetensors头检查记录在远端preflight/header报告，实际状态以这些产物及后续进度为准。

## 判据与接续

沿用现有状态/决定性引用/具体理由/接口联合判据，另外列出语义归因、全称、阈值、缺失和通用理由错误。缺列表短句存在指代歧义，不把继承标签当人审gold；语义否定例必须核完整来源。任何改善仅属已曝光开发材料，不是独立验证。

若替代基座聚焦材料仍反复核心错，按A1停止受影响SFT并讨论，不自动再换模型。若基本核查可行，才进入B监督设计和核验；来源隔离、关键标注争议、准确训练/评价预算尚未冻结，C不能自动启动。Actor固定；FULL20不重跑；不读GT或44保留来源组，不新增假图。
