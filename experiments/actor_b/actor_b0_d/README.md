# Actor-B0-D：执行与产物说明

本目录按已归档的 [B0-D 方案](ACTOR_B0_D_PLAN.md)评估冻结 Actor-B0-C 的取证策略。诊断 manifest 与 B0-C 使用同一批 60 图，不构成独立 held-out；PROBE 类是困难代理样本，不是真实历史 PROBE 错误复现。Monitor 预留的 74 个来源组不参与本轮。

## 无卡准备

```powershell
python experiments/actor_b/actor_b0_d/prepare_b0_d_inputs.py
python experiments/actor_b/actor_b0_d/prepare_b0_d_full.py
python -m pytest -q tests
```

`actor_input_manifest.jsonl` 只含图像标识、相对路径和 SHA-256，不含标签、来源组或诊断类别。`diagnostic_manifest.jsonl` 留在本地作离线评价。`full/trajectories.jsonl` 复用冻结 B0-C 的 60 条轨迹，只应用已经批准的最小 STOP policy。

## GPU 条件运行

启动前必须先核对 `FROZEN_INPUTS.md` 中的模型、prompt、schema、tool cards、Evidence、缓存工具结果、运行时和 Git 版本。当前本地仓库没有 B0-C 原始 tool cards；远端读到的 card 文件只有在与已冻结的 B0-C `prompt_sha256` 完全一致时才可运行。

每个新条件各运行一次：

```powershell
python experiments/actor_b/actor_b0_d/run_b0_d_condition.py `
  --condition probe_mask `
  --manifest <actor_input_manifest.jsonl> `
  --tool-results <heldout_tool_results.jsonl> `
  --image-root <heldout_image_root> `
  --evidence-dir <evidence_root> `
  --model-dir <frozen_model_revision_directory> `
  --tool-cards <verified_b0_c_tool_cards.json> `
  --b0-runtime <frozen_b0_c_runtime.json> `
  --output-dir experiments/actor_b/actor_b0_d/probe_mask
```

依次把 `--condition` 和输出目录改为 `probe_delay`、`tool_rename`。FULL 不重新推理。三个新条件共 180 条模型轨迹；按 B0-C 实测推理耗时预计约 2.5–3 小时 RTX 4090 时间。只有用户开卡后执行 GPU 阶段。

## 评价与人工复核

```powershell
python experiments/actor_b/actor_b0_d/evaluate_b0_d.py
```

评估器检查四条件样本及顺序完全一致；冲突由冻结的局部纹理和互补取证方向输出预先定义，不使用 Actor verdict。它生成逐样本、冲突和逐调用表，以及 20 图 × 4 条件的盲审包。按 [人工审计说明](evaluation/HUMAN_AUDIT_GUIDE.md) 完成 `evaluation/human_audit.jsonl` 与 `tool_selection_audit.csv` 后再解释 SFT gate。评估重跑会保留已填的人工标注。

逐样本输入、轨迹、审计包和标签表留在本地并由 `.gitignore` 排除；GitHub 只存方案、代码、去标识的汇总报告与必要的冻结记录。
