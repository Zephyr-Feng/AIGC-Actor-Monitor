# Actor-B0-C：STOP 字段约束回放

执行依据为[用户新方案](../../../docs/ACTOR_B_CONSTRAINED_FREEZE_PLAN.md)。本轮只处理 `STOP.final_verdict ∈ {real,fake}`；原 reasoning prompt、schema、工具、Evidence v1、图像和已生成轨迹保持冻结。B1 SFT 暂缓。

## 冻结输入与 CPU 检查

- 原 60 图轨迹 SHA-256：`276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`。
- Manifest SHA-256：`fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`。
- 合并工具输入 SHA-256：`94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`。
- 结构预检已核对 60/60 条工具观察、STOP 前历史，并证明原 JSON 仅替换 verdict 后可解析；见 `input/preflight_summary.json`。
- 无卡 tokenizer 预检检查 60/60 条字段候选边界，并核对 1 条合法、1 条失败轨迹的原始输入 token 数和图像网格数；见 `input/tokenizer_preflight.json`。
- 15 条成功对照从原 55 条合法轨迹按 verdict、confidence、真实冲突和工具路径确定性选取，覆盖成功轨迹的全部 8 种路径；清单为本地忽略的 `input/controls.jsonl`，汇总见 `input/controls_summary.json`。原 5 条失败全部纳入 pilot。

## 约束机制

`contract_replay.py` 按旧轨迹重建最后一次 STOP 生成前的消息与多模态输入。Stage 1 使用原始生成的 JSON 原文；Stage 2 让**同一个冻结模型**在 `final_verdict` 字段处分别计算 JSON 字符串 `"real"` 与 `"fake"` 的条件对数似然，选分数较高者。原始生成 token ID 未保存，因此原文前缀需要由同一 tokenizer 从文本重编码；这点在报告中保留为方法限制。模型不读取 GT 标签，parser 不依据工具分数补判。输出同时保存 `raw_unconstrained_output`、`contract_constrained_output` 和两种合法值的模型分数；只允许最终 verdict 字段变化。Qwen3-VL 仅计算候选后缀所需的 logits。

先运行原失败 5 图与成功对照 15 图。技术检查要求 5/5 失败修复、20/20 合法终态及 20/20 工具序列保持；成功对照的 verdict 保持率按用户方案报告（方案将约 100% 列为理想结果，未设硬阈值）。完整回放报告 verdict 保持率，并须达到 60/60 合法终态、60/60 工具序列保持和 55/55 原合法 verdict 保持，才考虑 `ACTOR_B0_C_FREEZE`。任何异常先核对原因并保留原始输出，不重跑 detector、crops 或工具，也不使用预留的 74 个 Monitor test 来源组。
