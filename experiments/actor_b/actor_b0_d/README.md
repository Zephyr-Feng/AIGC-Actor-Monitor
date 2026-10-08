# Actor-B0-D：执行与产物说明

本目录按已归档的 [B0-D 方案](ACTOR_B0_D_PLAN.md)评估冻结 Actor-B0-C 的取证策略。GPU 阶段已完成，正式汇总见[报告](report/ACTOR_B0_D_REPORT.md)，当前 gate 为 ACTOR_B0_D_INCONCLUSIVE，等待方案要求的真实人工审计。诊断 manifest 与 B0-C 使用同一批 60 图，不构成独立 held-out；PROBE 类是困难代理样本，不是真实历史 PROBE 错误复现。Monitor 预留的 74 个来源组不参与本轮。

## 当前 Agent 辅助审计

按[2026-10-08审计方案](audit_assist/AGENT_AUDIT_PLAN.md)进行80条轨迹与827次CALL独立预审；真实人审范围为80条轨迹全量和风险CALL子集，详见[协议修订](audit_assist/PROTOCOL_AMENDMENT.md)与[人审指南](audit_assist/HUMAN_REVIEW_GUIDE.md)。逐记录输入、Agent标签、图片、配对分析和HTML仅本地保存，不上传GitHub。未完成真实人审前维持`ACTOR_B0_D_INCONCLUSIVE`。

预审已完成，见[Agent汇总报告](audit_assist/AGENT_AUDIT_REPORT.md)。离线页面位于`audit_assist/review_packets/human_review.html`，当前为80轨迹+243去重CALL；P2的RENAME空候选例外待研究者确认。真实人工标签尚未写入。

## 无卡准备命令

```powershell
python experiments/actor_b/actor_b0_d/prepare_b0_d_inputs.py
python experiments/actor_b/actor_b0_d/prepare_b0_d_full.py
python -m pytest -q tests
```

`actor_input_manifest.jsonl` 只含图像标识、相对路径和 SHA-256，不含标签、来源组或诊断类别。`diagnostic_manifest.jsonl` 留在本地作离线评价。`full/trajectories.jsonl` 复用冻结 B0-C 的 60 条轨迹，只应用已经批准的最小 STOP policy。

## GPU 条件运行

启动前必须先核对 `FROZEN_INPUTS.md` 中的模型、prompt、schema、tool cards、Evidence、缓存工具结果、运行时和 Git 版本。本轮审计已找到本地冻结原始工具卡`experiments/mini_faithbench_v0/config/tool_cards.json`，SHA-256为`4bea66b6aad42ff93ed7a4ff128b5094550e81fb72f1b8452fdfb464a98867fb`；运行前仍须核对完整冻结输入。

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

逐样本输入、轨迹、盲审包、per-sample.csv、conflict_analysis.csv、827 条调用审计表和人工标签留在本地并由 `.gitignore` 排除。GitHub 仅存代码、冻结记录、聚合 metrics.json 和去标识汇总报告。人审完成后重跑评价器会保留已填写标签，再更新报告决策。
