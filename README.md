# AIGC Actor Monitor

本项目研究 AI 生成图像的自主取证：Actor 调用冻结的取证工具，基于 Evidence Card 形成可审计轨迹；独立 Monitor 检查证据归因、充分性、冲突处理和 STOP 是否合理，并在必要时要求继续取证。当前研究主线为 **Structured Actor → FaithBench → 离线 Monitor → 在线干预**。

Actor 用中文描述图像中的伪造线索、工具证据和不确定性，并在最终答案中给出中文解释。`real` / `fake` 仅是机器可读的结论标签；这些解释是 Monitor 可观察的输出，不等同于模型内部思维过程。

项目优先复用公开 Actor、取证工具、方法和数据。现有 Mini FaithBench 技术小样已暴露 PROBE observation 被误写为真假倾向的问题；当前尚未冻结主 Actor、建立正式 FaithBench 或训练 Monitor。具体研究设计以[项目主方案](docs/Actor_Monitor_MVP_Protocol.md)为准，已完成工作与续跑条件见[项目进度](docs/PROJECT_PROGRESS.md)。

## 当前结论

- 旧服务器代码提供了可复用的 Actor tool-call 循环、结构化轨迹和工具接口。
- 旧 `monitor/calibration.py` 是工具分数标定器，不是当前方案中的轨迹 Monitor。
- 旧 M3 轨迹适合用于发现问题，不适合直接作为 Monitor 的训练/确认性实验数据。详见 [legacy audit](docs/LEGACY_AUDIT.md)。
- 队友的 training-free 工作作为 discovery baseline 和实验工程参考；新项目需要独立、冻结的确认性协议与数据。

## 已有离线评估代码

`actor_monitor` 中已有一套对应旧版 A0/A1/A2 固定动作方案的离线评估层，保留用于历史复现；它不是新方案的 Monitor 实现：

- `schema.py`：配对干预账本、Monitor 预测和效用定义；
- `evaluation.py`：按预测净收益选择干预，计算收益、误伤、覆盖率、oracle headroom 和 regret；
- `scripts/evaluate_ledger.py`：读取 JSONL 账本与预测并生成 JSON 报告；
- `tests/`：验证策略选择、预算约束和收益计算。

这层不依赖 Qwen、TruFor 或某个特定数据集。后续如复用其中代码，需要先按新方案重新核对指标和数据契约。

## 旧评估层的快速验证

```bash
python -m unittest discover -s tests -v
python scripts/evaluate_ledger.py \
  --ledger path/to/outcomes.jsonl \
  --predictions path/to/predictions.jsonl \
  --threshold 0.0
```

文档入口见[文档导航](docs/README.md)。[Stage 0 复用审计](docs/STAGE0_REUSE_AUDIT.md)、[旧版 research protocol](docs/RESEARCH_PROTOCOL.md) 和 [idea review](docs/IDEA_REVIEW.md) 均保留作为历史决策及实现记录。
