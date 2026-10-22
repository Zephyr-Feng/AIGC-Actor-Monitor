# Monitor跨模型对照：准备与执行冻结

2026-10-12。按[已确认方案](../../../docs/research/MONITOR_MODEL_COMPARISON_PLAN_20261012.md)执行；用户指定DeepSeek V4.1 Flash，提供凭据并授权实验，随后明确确认当前实例开卡及开启goal模式。

六例来自已观察开发材料。E1复用automatic_audit_v1原完整四步及逐字相同messages，历史8B raw的SHA核验通过。其余五例从pilot_v1已登记请求正文取出原packet，逐文件对照manifest hash；旧JSON协议提示和派生runtime ledger不进入本轮。原步骤、实际返回、工具卡、预算、原raw和非法终态保留，没有读图像GT、身份映射或74预留组。

| 案例 | 原来源 | 预审任务 | Qwen输入tokens |
|---|---|---|---:|
| E1 | FULL/blind_003 | 非方向全局偏离被写成fake；无支持一致综合 | 4306 |
| E2 | FULL/terminal_0001，blind_001 | 将对象语义归为global工具返回 | 4208 |
| E3 | FULL/terminal_0005，blind_010 | 明说继续取证却STOP；把中性偏离未支持误作反向冲突 | 4677 |
| N1 | TOOL_RENAME/terminal_0061，blind_001 | 完整有限度real/moderate轨迹，四工具用完 | 6394 |
| N2 | FULL/call_0001，blind_001 | 初始合法global CALL，无未来结果 | 1384 |
| N3 | PROBE_MASK/call_0190，blind_001 | 初始合法local CALL，无未来结果 | 1196 |

N1不等于完美表述：校准措辞、视觉不可核实或top3描述可以提出有限提醒；不能自动把top3等同超过阈值的异常计数，也不能凭措辞把真实real_like信号判成不存在。逐例必要问题、可接受解释、禁止过强指控在private/criteria.json冻结，与模型消息分开。判据是助手开发预审，非独立gold。六条输入只有三个来源组，其中四条来自blind_001；两个合理CALL不能证明合理STOP的审核能力。

A保留Qwen3-VL-8B-Instruct基座BF16/无adapter/greedy/1024输出/重复惩罚1.05/seed20261006。新增五次顺序E3、N1、N3、E2、N2；E1原响应复用，非本轮复现。六例CPU原生模板再编码与上下文检查通过，无截断，不加载模型。B顺序E3、E2、N1、N3、N2、E1；每例独立请求，与A的system/user正文逐字相同。

B官方endpoint为`https://api.deepseek.com/chat/completions`，模型`deepseek-flash`；thinking enabled/high、max_tokens8192，流式返回并请求usage。思考和可见回答共用预算，不能独立保证可见回答长度；A/B计算预算及模板不同，结果是整套配置比较，不能归因为只换权重。不传无效temperature/seed，不使用tools，不给跨例历史或纠错回合。

[官方模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)将deepseek-flash列为DeepSeek-V4.1-Flash；[参数页](https://api-docs.deepseek.com/api/create-chat-completion/)给出生成上限及completion reasoning用量，[thinking文档](https://api-docs.deepseek.com/guides/thinking_mode/)说明effort与无效采样参数。按高峰未缓存输入$0.30/输出$1.20每百万tokens估算：六例UTF-8字节数加每例1024模板余量共98946作保守输入额度，输出上限49152，费用额度$0.0886662。该输入额度不是DeepSeek tokenizer实测或账单；最终使用返回usage计算，并报告价格/缓存/时段差异。

SSE保存/重建及不完整流停止的虚构自检通过。密钥仅由隐藏stdin进入进程内存，不写文件或日志；官方models只读请求核deepseek-flash可用后开始六例。每个案例独占目录与提交状态，服务故障或状态不明停止，不自动重试；语义/格式失败不重采样。原始流、响应、思考、usage、版本和时间私有保存；审核只评可见回答。

AutoDL14601当前hostname核验一致，4090启动前0MiB/0%，新隔离路径`/root/autodl-tmp/monitor-model-comparison-v1-20261012`原不存在；10部署文件hash通过，唯一worker PID6214启动。新增API最多六次、GPU五次，不训练、不执行Actor动作或工具。完成后原样备份、隐藏模型标识的助手逐例审阅、报告、更新进度、退出核验并停止。

私有准备包：`experiments/faithbench_monitor_v0/private/model_comparison_v1_20261012/`的inputs、packets、criteria、cpu_preflight、freeze。旧实验文件不覆盖。本页保留准备条件；已完成的执行与语义结果见[结果报告](REPORT.md)。
