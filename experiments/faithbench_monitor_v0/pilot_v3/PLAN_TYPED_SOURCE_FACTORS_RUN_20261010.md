# 36请求两因素诊断冻结执行补充

2026-10-10，承接前13请求复盘及两因素设计。范围固定九已用片段，每片段C00/C10/C01/C11各一次；条件顺序在各片段内按位置循环，实际schedule写manifest。仅提示词增加范围段/状态段，data/schema/引用范围逐字段相同，Card四prompt完全相同；不增加新来源或人工gold。

保持前13请求27B模型、b11517后端、Noble loader/library-path/cwd与原server argv，完整model/binary SHA复验、唯一服务、24,576 ctx/GPU layers99/parallel1/batch512/ubatch256/thinking和reasoning off/flash-attn on。请求温度0 seed42 repeat_penalty1.05 cache_prompt false max_tokens4096，原生JSON schema，HTTP120秒重试0。先原生template/tokenize全部36预检，输入+4096<=24576，否则生成前停止。CPU审核明确C00与前轮输入逐字一致、单因素只增一段、两因素无其他差异。

targets及首审意见单独留本地、不上传、不进request，远端由原13已批准材料派生并核本地manifest相同。所有请求/HTTP/raw/usage/finish_reason/response持久化。C00九raw与前轮是否复现单独记录，不把不复现自动归因因素；比较使用本次配对结果、分病例呈现，不计算总体准确率或p值。关注四语义错误是否纠正、缺列表是否未知及四正控制是否保持；解释不得额外背书，引用需支持内容。

预测与停止规则见原因素设计。HTTP错误停止、卡顿检查PID/日志/输出/GPU/健康端口；观察超时不重启任务。预估服务加载/36推理3–6分钟，先告知用卡窗口并核卡可用；完成停止自有服务并告知可关卡。备份hash、首审锁、同助手非盲复审；保护文件/模型hash后核。Actor冻结、74预留组/GT/身份映射禁读、反馈不执行、SFT0。通过也不计完整Monitor完成，需完整来源回归/最终聚合。
