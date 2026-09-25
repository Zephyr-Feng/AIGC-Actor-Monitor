# AIGC Actor Monitor

本项目研究一个具体问题：在多模态 Actor 已经开始推理、调用工具并形成证据链之后，外部 Monitor 能否预测**何时干预、采用哪种干预，才能带来正的净收益**。

核心对象不是“检测 Actor 是否可能出错”，而是干预的条件处理效应：

```text
tau_a(z) = E[U(Y(a)) - U(Y(no_intervention)) | Z = z]
```

其中 `z` 只能包含干预前可观测信号，`a` 是一种候选干预，`U` 同时考虑任务正确性、误伤、弃权与计算成本。Monitor 只有在预测最佳干预的净收益超过阈值时才行动。

## 当前结论

- 旧服务器代码提供了可复用的 Actor tool-call 循环、结构化轨迹和工具接口。
- 旧 `monitor/calibration.py` 是工具分数标定器，不是本项目要研究的 treatment-aware Monitor。
- 旧 M3 轨迹适合用于发现问题，不适合直接作为 Monitor 的训练/确认性实验数据。详见 [legacy audit](docs/LEGACY_AUDIT.md)。
- 队友的 training-free 工作作为 discovery baseline 和实验工程参考；新项目需要独立、冻结的确认性协议与数据。

## 仓库中的最小核心

`actor_monitor` 当前实现一个与模型无关的离线评估层：

- `schema.py`：配对干预账本、Monitor 预测和效用定义；
- `evaluation.py`：按预测净收益选择干预，计算收益、误伤、覆盖率、oracle headroom 和 regret；
- `scripts/evaluate_ledger.py`：读取 JSONL 账本与预测并生成 JSON 报告；
- `tests/`：验证策略选择、预算约束和收益计算。

这层刻意不依赖 Qwen、TruFor 或某个特定数据集，目的是先把科学问题和评价口径钉死，再接入具体 Actor。

## 快速验证

```bash
python -m unittest discover -s tests -v
python scripts/evaluate_ledger.py \
  --ledger path/to/outcomes.jsonl \
  --predictions path/to/predictions.jsonl \
  --threshold 0.0
```

JSONL 数据格式和下一轮实验方案见 [research protocol](docs/RESEARCH_PROTOCOL.md)。

