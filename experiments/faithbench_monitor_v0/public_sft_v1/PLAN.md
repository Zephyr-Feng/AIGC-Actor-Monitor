# RAGTruth 公共能力首轮训练（2026-10-16）

用户明确授权“按照这个新的数据集进行monitor训练”，并恢复当前服务器。此轮固定 Actor，仅对当前官方 Qwen3.5-9B 权重新建独立 adapter，不接续旧 SFT。

## 数据与任务

- `data/monitor_public_v1_20261016/built_v3/train.primary.sft.jsonl`：12,141 条，原 RAGTruth 人工跨度标签，核查来源忠实性并输出中文键 JSON。无问题标签意为原标注未指出问题，不代表外部事实真实。
- 验证 1,379 条；预先固定其中按标签平衡、每来源组一条的 64 条作为本轮开发检查。未用测试 2,595 条，测试文件不上传。
- 不混入默认禁用的 RAGBench 银标、视觉选择辅助、项目 GT 或 44 保留组。
- 当前基座原生非思考模板，13,520 条全部通过前缀与监督边界检查。训练总 token 11,536,649、监督 token 574,972、最长 2,965；验证最长 2,605。无截断，无移除长样本。
- 此任务只训练通用来源核查与跨度定位，不等于完成取证工具契约、STOP 或完整中文纠错反馈。

## 实现与预算

- 独立目录 `/root/autodl-tmp/monitor-public-sft-20261016`；基座 `/root/monitor-retraining-qwen35-20261016/assets/model`。Actor 环境、旧 adapter 和历史结果保留。
- 当前 Monitor venv + 原隔离 Transformers 5.3.0 + 新目录隔离 PEFT 0.18.0；旧 PEFT 0.17.1 与 Transformers 5.3 不兼容，因此不改旧环境而新建包目录。官方说明要求 Transformers v5 使用 PEFT 0.18+：[PEFT releases](https://github.com/huggingface/peft/releases)。
- 单 RTX 4090，NF4 double quant、BF16 autocast、SDPA、非重入梯度检查点。闲置视觉塔移到 CPU，全部冻结；大冻结 embedding/head 保持 BF16。
- 语言层 LoRA rank8 / alpha16 / dropout0.05，覆盖所有 32 层的 full attention、linear attention 和 MLP 线性投影，不训练视觉塔、embedding 或输出 head。
- 1 epoch，microbatch1、累积8，计划1,518次更新；AdamW，峰值LR5e-5、warmup3%、cosine到峰值10%、weight decay0.01、clip1.0、seed20261016。
- loss 为所有 assistant token 的因果交叉熵，每累积窗口按监督 token 数归一。仅计算需要预测的输出位置 logits，等价于完整 prompt-mask CE，避免大词表 prompt logits 浪费显存。
- 首次先做一次反向传播工程检查（不更新参数），再同一准备状态禁用 adapter 做64条基线生成与loss，最后训练；完整epoch后同条件64条复评。generation cap768，高于已选验证目标长度上限；达到上限仍单独记录，不冒称完整输出。
- 原首进程6小时检查点上限，含加载/基线；定期100更新或30分钟保存 adapter 与续训状态。实测前10更新约19–20秒/8条，完整epoch预计8–9小时。用户随后回复“提升”，已授权同一epoch总预算提高到10小时。`continue_run.py`从原加载时间计算总deadline，原进程达到6小时但未完成时仅接续一次检查点、使用剩余时间；失败不自动重启，预算耗尽停止自有worker，不增加epoch或新数据。
- 启动前 GPU 为空闲；用户已授予开卡可用时直接运行权限。最多128次开发生成、0教师API、0 Actor执行、FULL20不重跑。

## 结果口径

比较64条开发样本的格式合法、状态正确、无问题样本误报、跨度精确匹配、Unicode区间合法和开发loss；完整保留raw与截断标志。该集合已用于开发，后续不当独立验证。训练loss下降不单独证明 Monitor 实用能力提升，不为凑通过反复试参。

本地3项自检通过（监督移位与masked causal targets一致、Unicode跨度检查、无效输出不得计成功）；远端全量原生模板CPU预检通过。模型反向传播、显存可行性和实测耗时等待首次实际执行，不据代码存在宣称训练完成。

上述末段为启动前状态。实际执行已于2026-10-17 07:50:26完成，在10小时总预算内遍历全部12,141条、1,518更新并完成固定64条后评；10:15实例恢复后核实与回收，未因断联重跑。见[最终结果报告](REPORT_20261017.md)，后续新增任务须另行确定，不把本计划当自动续训指令。
