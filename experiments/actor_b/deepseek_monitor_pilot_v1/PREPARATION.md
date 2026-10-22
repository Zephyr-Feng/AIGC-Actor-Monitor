# DeepSeek Monitor → Actor FULL20：准备与执行交接

更新：2026-10-12。执行依据：[已确认方案](../../../docs/research/DEEPSEEK_MONITOR_ACTOR_CLOSED_LOOP_PILOT_PLAN_20261012.md)。用户已确认本轮开卡并要求启动目标模式。

**当前已完成并停止，以下待运行/阻碍条目保留为阶段历史。** 结果与争议见[REPORT](REPORT.md)，本轮不追加模型请求。20 API完整原样反馈、40分支续跑共50Actor请求/10真实互补缓存返回；CPU9407/GPU9582退出，GPU0MiB0%无计算进程，已通知可关卡。101部署、3 CPU和155运行备份、25模型环境保护前后通过。raw锁定后完成40隐藏条件助手审阅与20反馈审核，60引文/40工具预算核验后锁定语义，再仅解码选中20图GT评价（real6/fake14、15组）。A/B/C有效正确14/13/6，C对B净−7，C9非法终态；原合法且双方合法子集没有纯真假标签纠正。16原错误的部分修复B7/C14、完整联合均0。接口歧义/反馈问题/视觉对象争议明确记录，审核非真盲或独立gold，开发队列不能外推泛化。最终hash与逐项检查保存在private的final_audit.json；74预留、旧实验与原配置保留，0训练/新检测器/格式修复/重试。

固定使用原 FULL 审计20图；历史A保持18合法、2非法终态，不投影非法输出。B一般规范提醒、C一次DeepSeek原样反馈后，在共同历史节点上分别独立续跑。原图、历史格式重试和原始最后STOP均保留。

## 已核验的准备

- 原审计轨迹SHA：`aede0ace6b158be188b98b8f70d1ec2e30cb5cbd2c34b0a105ad60f5b90eae20`。
- 冻结工具缓存SHA：`94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`；与历史同批运行凭据一致，选中20图历史实际返回逐项一致。
- 20原图及60裁片齐全；历史资产指纹匹配，未调用全局工具的可用裁片也已核对原缓存对应图块。
- 剩余工具预算0/1/2分别3/14/3图；新增Actor上限80请求、缓存返回上限40。新增格式重试0，无训练、无新检测器运行。
- 工具缓存仅在调度文件；Monitor输入仅含历史可见文字、工具定义与限制、完整Actor schema、当前STOP/解析状态及预算。B/C共同前缀和深拷贝隔离检查通过。
- CPU虚构动作检查覆盖零预算STOP可修订、零预算CALL失败、重复CALL失败、非法JSON/非法STOP失败；SSE完成/缺DONE自检通过。
- 助手逐图语义预审20条冻结、引文复核通过。属于已观察开发材料的同助手预审，非独立gold；合理/未决不强行改成错误样本。
- 仅选中20图身份映射用于缓存匹配，不进入模型。来源组准备投影丢弃GT/label字段，尚未读取逐图GT，74预留未使用。
- 完整Monitor消息UTF-8字节数加每请求4096模板余量的输入额度502296；按已核高峰未缓存输入$0.30/百万、输出$1.20/百万，20×16384总输出上限的费用额度为$0.5439048，低于$1。

私有材料保存在`experiments/faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/`，已确认Git忽略；包括inputs、dispatcher_cache、monitor_packets/inputs、historical_A、selected_identity_map、group_inventory、structural_checks、preaudit和freeze。无密钥写入文件或命令参数。

## API阶段的当前证据

官方`deepseek-flash`账户alias核验通过。20图各一次thinking enabled/high/max_tokens16384流式请求已运行，复用隐藏stdin、SSE原样保存、usage和不明状态不重试原则。已启动进程的终端输出报告20图全部`finish_reason=stop`，最后为`API batch completed; no further requests`；进程退出码0。

这只是API批次完成的进程证据。尚未重新打开全部response/SSE核对完整非空content、拒绝字段、usage汇总及文件hash，尚未生成feedback_delivery/execution_freeze。没有先做人为反馈修补或语义筛选，不能由API正常结束宣称Monitor反馈全部正确。

## 尚未执行与阻碍

Actor GPU worker源文件已草拟，尚未完成部署控制器与全套执行前校验。Actor完整图像processor CPU长度与未来工具最长上下文检查未运行，0新增Actor推理，未部署或启动新GPU worker。

新的命令被自动审批服务拒绝执行，返回原因是审批服务用量额度耗尽、审批无法完成，并非操作安全性被否定。没有绕过审批。已有API进程可正常读取并已确认结束；该故障不表示已提交的API批次失败，不得因此重跑API。

目标仍未完成：恢复正常命令审批后，先核API产物并冻结原样反馈，完成Actor CPU/资源检查，再按同一固定20图计划仅运行B/C续跑。所有输出与语义初审锁定后，才可读选中20图GT作离线配对评价；最后审核、报告、更新进度、核验GPU释放并停止。若用户已关卡，续跑前须按AGENTS.md第5条重新确认当前开卡状态。

当前没有闭环性能结论，未追加实验。

## 恢复后的执行进展

审批提示重置时间过后，通过同一审批入口再次只读核验成功；未绕过审批。20 request/response/state/SSE全部核验、原始反馈交付与execution_freeze已锁定：20份均正常stop、完整非空且无拒绝字段。原样反馈508–899字符，未机械截到600字符；输入101434、输出49902含思考43139，累计API346.61秒，高峰用量估算$0.08692572、低峰$0.04346286，尚未核账单。

选中20原始身份串均未进入inputs/monitor_inputs/dispatcher_cache。远端没有发送selected_identity_map、group_inventory、preaudit.json或GT；101个文件部署hash通过。最终复查更正：依赖代码中包含有人工判断的preaudit.py，故服务器侧并非完全没有预审内容；worker没有调用该脚本，完整模型输入核验未发现人工判断进入请求。部署范围缺口保留在最终报告和审核，不补跑或更改冻结产物。

40分支完整processor CPU检查全部通过，初始输入4134–6198 tokens；每图所有尚未调用工具的排列作CPU长度探针，额外保留未来动作生成与模板余量，均低于模型上下文262144，无实际模型调用、截断、缩图或删历史。CPU PID9407已退出，3个备份文件hash通过。

重新核同AutoDL hostname、4090/24564MiB、0MiB0%、无计算进程、14GB可用及新目录原不存在后，唯一Actor GPU worker PID9582已启动。基座BF16无adapter、greedy/768/seed20261006保持原配置。当前须继续观察唯一worker；没有完整闭环审核或GT评价，仍不可宣称检测收益。
