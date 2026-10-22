# 公共来源核查 SFT

**本轮已于2026-10-17 07:50完成**，见[结果报告](REPORT_20261017.md)。最终adapter及原始结果已回收到`data/monitor_public_v1_20261016/training_v1/completed_20261017/`；训练后判定54/64，非空片段区间全部合法0/22，不认定完整Monitor通过。`summarize.py`仅离线复算保存结果，不运行模型。

本轮执行依据：[PLAN.md](PLAN.md)。实际任务输出在服务器独立目录
`/root/autodl-tmp/monitor-public-sft-20261016/run`，外层`worker.log`记录每条开发生成和每个训练microbatch；原始模型与旧结果不写入。

- `prepare.py`：仅CPU，用原生tokenizer核实数据/模板、固定64条开发检查；可在独立目录展开PEFT0.18，不调用包安装器或旧核验程序。
- `train.py`：官方9B独立QLoRA、完整12141条单epoch、assistant-only token CE、开发基线/后评、周期checkpoint与续训。
- `test_train.py`：因果监督移位、Unicode跨度、无效输出边界。
- `continue_run.py`：用户已批准总预算10小时；首进程6小时后必要时仅接续同一epoch一次，总deadline控制不增加epoch。

服务器实际运行环境：Monitor旧venv作Python入口，`PYTHONPATH`依次为本轮`vendor`与旧9B部署的Transformers `vendor`。不得修改Actor环境或运行旧含核验步骤的runner。

`run/latest.json`指向最新`checkpoint-NNNNN`，其中`adapter/`为独立LoRA，`training_state.pt`为本次可信自建优化器/进度/RNG状态。续训必须明确使用该检查点和相同输入/配置，不从头多跑epoch。`status.json`区分完成全epoch与限时部分训练；只有完成全epoch才自动进行`after`开发复评。

开发指标不等于独立测试，也不验证完整取证Monitor或Actor闭环收益。默认禁用RAGBench银标和视觉辅助。
