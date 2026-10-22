# Monitor 自动审核：无卡准备

后续状态（2026-10-12）：用户确认开卡，单次审核、备份和人工审阅已完成并停止；结果见[报告](REPORT.md)。下文为运行前准备记录，冻结设置保持不变。

2026-10-12。用户确认[首轮设置](../../../docs/research/MONITOR_AUTOMATIC_AUDIT_DISCUSSION_20261012.md)，并要求使用 Ponytail；按 full 模式复用既有轨迹清理、哈希函数及本地 tokenizer。无新增依赖，无服务器操作，无模型权重加载。

## 已固定的请求

- 原 FULL/blind_003 四步：三个实际工具返回、step_4 原 STOP 提议；预算已用3/4，剩余1次，不能重复调用。完整 Actor 原始输出及解析内容均保留，不预挑错误句子。
- 原四张工具能力卡保持不变。工具返回仅由现成 `clean_step` 将三个裁片路径改为中性 `asset:blind_003_R*.png`，其余字段与数值保留；没有加入像素。
- 独立 system/user 上下文，使用已确认的通用审核提示。原始 Actor 的真假提议是待审数据，图像 GT、身份映射、人工反馈、R/G/T 响应、旧语义审核及 effective 投影未进入输入，也未读取上述反馈或结果文件。
- Qwen3-VL-8B-Instruct 基座 revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`，BF16，无 adapter；单次 greedy，max_new_tokens=1024、repetition_penalty=1.05、seed=20261006。0训练、0 Actor 新请求、0工具执行；暂不把反馈发送给 Actor。
- 事后判据沿用方案：分别记录错误发现、引用与论证、反馈可用性、附带错误指控；局部校准提醒单列。助手审核为非盲、非独立 gold；不按格式差异直接判语义失败。

## 本地验证

`python experiments/faithbench_monitor_v0/automatic_audit_v1/prepare.py` 已成功执行。原 case 与上一轮冻结一致；原轨迹及工具卡 SHA 与已确认来源一致。四步各一次尝试、解析合法、工具调用顺序及返回来源一致、STOP 无新返回；完整 Actor 原句保持不变。人工检查最终 packet，核实原三工具返回、能力限制及数值保留。GPU 运行前仍需核对远端资产和 token IDs，不能把本地检查当作远端部署验证。

现有 Transformers 4.57.4 / AutoTokenizer，使用从既有模型快照核验取得的六个本地文件，六项 SHA 均匹配 provenance。禁用 torch/TF/Flax 后完成 CPU 检查，未安装依赖或读取训练材料。完整输入 **4306 tokens**，无截断，1024 输出预留后总计5330，低于模型配置的262144；不沿用4096上限。chat template 生成 IDs 与渲染文本再编码一致。

本轮模型请求0、服务器操作0；尚无 Monitor 原始输出或语义结论。准备脚本遇到已存在目录会停止，避免覆写冻结材料；不要将它当作续跑命令重复执行。

## 冻结材料

私有目录 `experiments/faithbench_monitor_v0/private/automatic_audit_v1_20261012/` 沿用已有 `/private/` Git 忽略规则。

| 文件/内容 | SHA-256 |
|---|---|
| inputs.json | `4503bdfdaf8ae2a358294fede8c4bc59f24ccd1e9ffc0294deef1c6f24637b73` |
| packet.json | `94a4213d8f3f3cf5ead405b43872b4af81984e2378d992a267e8bc881428c12f` |
| cpu_preflight.json | `fcf8376ff1b78c9af6d9eaf6dc77514564f5c91a38685cb336913874779eac02` |
| review_template.json | `1071963b77ba4203717214165c34c857f4d8893efa2c8335eb543a5b8193635f` |
| freeze.json | `d6a88bda8054743c5d19adc37200f4ea3059bdc543029f7aa40905f5be537c96` |
| canonical input token IDs | `1699fc16d22b4c201e707305ec28b7c614284a6e85edc94c17627d9e52a38ce6` |

freeze 同时记录来源、方案、准备脚本、现有复用代码和 tokenizer 资产指纹；review_template 单独保存，不进入模型 messages。

## 下一步与停止边界

等待用户确认本轮当前实例开卡后，核对实例/模型/资源与冻结输入，复用已有独立部署及输出保存方式完成一次审核；预计 RTX4090 用卡5–10分钟。GPU 执行脚本尚未部署，服务器状态本轮未核验。保存原始输出、逐项审核、报告、确认进程退出后提醒关卡，随后停止；不重采样、改提示、追加案例、训练或自动运行 Actor。

单个已知错误开发案例，只能检验本例的自动审核可行性；不估计误报率、泛化、图像语义审核或最终检测收益。
