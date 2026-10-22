# 已批准分栏接口：13请求开发诊断

2026-10-10。复用既有Qwen3.5-27B Q4_K_M和llama.cpp b11517。输入来自已批准R14的12片段与1删除实际列表控制；CPU材料首审/同助手非盲复审已完成，不读取teacher目标做推理。冻结Actor，74预留组/GT/身份映射禁读，反馈不执行，SFT0。

## 要辨别的问题

A010的卡片限制是否得到内容正确的能力引用；卡片top3定义是否被误当实际列表；门牌/天空/方尖碑/云层是否仍被Actor上下文或正确编号背书；阈值是否引用observation，score是否仅支持分数；9/9是否正确；返回limitations释义是否仍接受。关系、引用内容与解释逐条细审，不以结构通过代替语义成功。

## 冻结执行条件

从R14完整records派生，12自然数据逐字段不变，仅新增准备阶段固定audit_target；terminal_0041_A006另存控制，只删除most_atypical_regions及其field_references，其他返回/计数/卡片/Actor上下文不变。已有含糊三片段排除。使用typed_source_portable的固定键顺序提示词、分栏schema和中文最低解析契约。

模型SHA `84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806`；后端binary SHA `750f3ae1c45f8fca1cef6d064dc92afb7809cf860cf47c9af8f1023e1614a984`。恢复原保存argv：私有Noble loader、原library-path、cwd runtime/llama-b11517，GPU layers99/ctx24576/parallel1/127.0.0.1:8089/thinking off/reasoning off/flash-attn on/batch512/ubatch256。启动前身份/GPU/进程/端口/完整模型hash核验，不重复加载。

温度0、seed42、repeat_penalty1.05、cache_prompt false、每请求max_tokens4096、原生response_format JSON schema、HTTP120秒、重试0。先用服务apply-template/tokenize对全部13请求预检，输入+4096<=24576，否则在生成前退出。中文约束使用输出后的解析，不能假设后端支持正则。提示词/schema/HTTP/响应/raw/usage/finish_reason/耗时逐份保存，失败不修复。

不增加原R14重跑或adapter条件；与R1412既有自然输出仅作历史开发比较，接口、提示词、类别词汇与键顺序组合改变，不单独归因、不声明随机因果或独立准确率。新控制无自然真实性结论。总13新请求，预估服务加载/推理3–6分钟，备份复审另算。服务和runner唯一，任务结束停止自有服务释放显存，及时告知可关卡。

HTTP失败停止，卡顿检查PID/最新日志/GPU/输出/端口；不因观察超时重启。首审保存后锁定，再回原HTTP、原始返回/卡片与原字段核第二次；复审保持同助手非盲性质。若错误依据、错误关系、卡片填补缺观测或解释不足，先复盘，不扩训练/整池蒸馏。即使本诊断通过，完整最终Monitor聚合、冲突/STOP/干预方向仍须验证，goal不按分类接口完成。
