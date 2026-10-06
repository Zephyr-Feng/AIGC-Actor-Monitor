# P0 无 GPU 接线记录

> 历史实现记录：本文主体记录旧六臂方案下的结构校验工作，不再定义当前研究主线。当前研究目标和 `A0`、`A1`、`A2` 三动作设计以 [Actor_Monitor_MVP_Protocol.md](Actor_Monitor_MVP_Protocol.md) 为准。2026-09-27 已将校验器和合成文件流改为三动作；下文提到的六臂、60 条结果及旧验收步骤仅描述历史工作。

当前 Actor 检查点与三个动作已统一采用中文提示，最终答案要求中文解释；提示文本见 `src/actor_monitor/checkpoint.py`。`scripts/smoke_chinese_checkpoint_qwen.py` 用单张图核对模型能否遵守这一输入输出格式，不调用取证工具，也不产生研究结论。此脚本需要 GPU；无卡时只运行结构校验和本地测试。

`scripts/validate_p0.py` 只做结构校验；10 图模拟数据由 `tests/test_p0.py` 生成，不属于真实试点。

## 文件流

```text
manifest (独立真值、来源簇、图像 hash；与前缀分开存放)
    -> Actor 检查点前缀 (prefixes.jsonl，不含真值)
    -> 从同一前缀恢复 A0/A1/A2/A3/C1；A4 直接弃权
    -> outcomes.jsonl (每个触达 episode 六行)
    -> P0 结构校验 + 人工逐图状态核对
    -> P1 才能估计帮助/伤害与成本
```

P0 manifest 至少含 `sample_id`、`source_group_id`、`label`、`image_sha256`、`split`。每个前缀至少含 `episode_id`、`sample_id`、`source_group_id`、`checkpoint_id`、`reached`、`prefix_hash`、`image_sha256`、`messages_sha256`、`tool_outputs_sha256`、`actor_hash`、`prompt_hash`、`tool_hash`、`channel_hash`、`decoding_seed`。未触达检查点的 episode 也要保留前缀行，并记录 `reason`。前缀不得混入真值或干预后结果。校验器用独立 manifest 核对来源簇、图像 hash 与 `correct` 字段，同时拒绝跨集合的来源簇。

每个 outcome 至少含 `episode_id`、`arm`、`prefix_hash`、`arm_version`、`answer`、严格布尔型 `correct`/`abstained`、非负有限数值 `compute_cost`。还需记录该臂**接收干预前**的 `image_sha256`、`messages_sha256`、`tool_outputs_sha256`、`actor_hash`、`prompt_hash`、`tool_hash`、`channel_hash`、`decoding_seed`，供校验器逐项比对。同一触达 episode 必须有 `A0`–`A4` 与 `C1` 六行；`A4` 的答案是 `abstain`。扩展字段应保留模型 token、延迟、工具调用、失败原因与后续生成 seed，以供成本与失败审计。

## 无 GPU 可运行

```bash
python -m unittest discover -s tests -v
python scripts/smoke_p0_synthetic.py --output runs/synthetic-p0-20260926
python scripts/validate_p0.py --manifest data/manifests/P0.jsonl --prefixes runs/P0/prefixes.jsonl --outcomes runs/P0/outcomes.jsonl
```

`smoke_p0_synthetic.py` 输出 10 张占位“图”的 manifest、前缀、60 条六臂结果与验证报告，并在目录内写入 `SYNTHETIC_DO_NOT_USE_FOR_RESEARCH.txt`。它只验证文件流，不生成图像或模型结果。

旧 `server-aigc-snapshot/agent/actor.py` 包含工具调用循环，但其 `run_episode` 尚未提供可恢复的固定 `G_late` 检查点。旧 `agent/trajectory.py` 的消息写盘把 PIL 图像缩成尺寸信息，因此不能直接证明分支收到相同图像字节，也不足以重建完整运行状态。服务器接通后需先补不可变图像引用/hash、工具原始返回、完整消息序列、模型及解码参数，再实现同前缀分支。

## P0 真实验收仍需服务器

1. 用独立 manifest 指定 10 张图，保存全部初始 episode，包括未触达者。
2. 逐图比对各臂实际收到的图像字节、消息、工具输出、模型版本和解码参数；仅匹配 `prefix_hash` 不够。
3. 将不中断 `A0` 与保存后恢复 `A0` 配对比较。确定性解码应逐字一致；不一致时先修复恢复路径。
4. 六臂结果齐全后运行结构校验，并保存原始失败记录、耗时和成本。无 GPU 时只进行环境核查与接线，不能把模拟 10 图检查当作真实 P0 通过。

现有 `evaluate_policy` 的预算按测试批次排序，只适用于探索。确认性报告仍需验证集冻结阈值、Monitor 公共成本与源簇区间的独立实现。

## 2026-09-26 16:20 执行记录

- 本地完成独立 manifest、前缀、六臂结果三份 JSONL 的交叉校验。检查源图像簇不跨 split、同图像 hash 不对应冲突真值/来源簇、每个初始样本均有前缀、同一样本和前缀 seed 不重复、六臂输入状态 hash 与版本一致、`correct` 与独立真值一致。
- 运行 `python scripts/smoke_p0_synthetic.py --output runs/synthetic-p0-20260926`：生成 10 个合成源图像占位记录（real/fake 各 5）、10 条前缀、60 条六臂结果，结构校验通过。生成目录显式标记为模拟，不能用于帮助/伤害或成本估计。
- 运行 `python scripts/validate_p0.py` 对上述三份文件复核，通过；`python -m unittest discover -s tests -v` 的 14 项测试通过。
- 两次只读 SSH 连通性核查均显示旧记录中的 AutoDL 地址/端口拒绝连接。未读取远程目录、数据或模型，也未运行任何模型推理。需要服务器本次有效的 SSH 地址与端口后才能继续远程环境核查。

### 接入旧 Actor 的下一步

旧 `run_episode` 在每次工具返回后直接进入下一轮，且没有可恢复的固定检查点；当模型不再调用工具时，当前轮可能已经是最终答案。应把循环拆成 `run_to_G_late` 与 `resume_from_G_late`，在预先定义的逻辑位置保存完整前缀与续跑状态。`A0` 和不中断原路径须先完成等价验证，再开启 `A1`–`A3`、`C1`。旧 Actor 系统提示为中文，干预文案应在真实 P0 前确定语言和包装格式，并冻结版本。服务器无 GPU 时可以核查目录、依赖、数据清单和文件 hash；真实模型分支及其成本测量需 GPU。
