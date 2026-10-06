# Mini FaithBench v0：归因边界及 STOP 契约修复小样

**日期：2026-10-06。结论：未通过；正式 900 条未启动。**

按用户给定的最后一轮最小修复范围，只修改 `config/system_prompt.txt` 和 `run_mini.py` 的 `rationale_prompt()`：明确区分 PROBE observation、非结论性 interpretation 与 Actor synthesis，并重申 STOP 时 `final_verdict` 只能为 `real` / `fake`。未改 Evidence v1、其他工具、样本、输入卡片、crops、模型/processor、生成配置、parser、callable、调用或 STOP 策略。原固定 6 张、原顺序分别跑 FULL、SUMMARY-MASK、OUTPUT-RENAME。

## 版本与输入

| 项目 | SHA-256 / revision |
|---|---|
| 旧 Actor-0 prompt material | `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d` |
| 前一轮 Evidence-compatible 候选 | `cc128afa3e4f6ec0f0cc68509386c2668f6375f551fdc45803369746b6c8882f` |
| 本轮 prompt material **候选** | `5cc7a1cd8ffda55b7d2b94b7546619944073c933ed1a064c0a2d07c0c94604f2` |
| 本轮完整 `system_prompt.txt` | `bda151c9725d7086da1cac36e463de99ff5722bc24f0c8c57d457f23c6d6b3ee` |
| 本轮 `rationale_prompt()` 文本 | `e730d7bf4acab605c9ed62adcb121cc836fd6570c11871e169184774968b0d92` |
| 本轮完整 `run_mini.py` | `04b8e8915dfa42f53f92f0864ecaa185f647c94a0c03825125b1e702a959f06c` |
| 模型及 processor revision | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` |

三条件的轨迹均记录同一个本轮 prompt material SHA 和上述同一 model/processor revision。输入 JSONL、固定六图清单与前轮 SHA 保持一致；远端新输出目录为 `/root/autodl-tmp/mini-faithbench-v0/technical_sample_v3/`，未覆盖前两轮。

## 工程检查

| 条件 | 最终可解析 | 中间解析错误 | PROBE 调用 | 四图 Actor 步骤 | PROBE 后调用其他工具 | 非法 callable |
|---|---:|---:|---:|---:|---:|---:|
| FULL | 6/6 | 0 | 6 | 23 | 6 | 0 |
| SUMMARY-MASK | 6/6 | 1 | 6 | 23 | 6 | 0 |
| OUTPUT-RENAME | 6/6 | 0 | 6 | 21 | 6 | 0 |

三条件均以 `pixels` 模式把原图与 top-3 crops 送入 Qwen；多图步骤的 processor grid 数与输入图像数一致，同图跨条件 crop SHA 一致。Actor-facing PROBE 卡片 classifier 结论字段扫描为 0 命中；三条件的 callable 均保持 `global_forensic_analyzer`，其他工具可调用。已解析的 PROBE `evidence_summary` 中没有凭空补写 `signal/score`。自动关键词检查出现 4 个命中，其中“无真假倾向”和将 PROBE 非方向观察与 classifier 工具结果分开陈述的句子不能直接判作泄漏，因此另行逐条人工阅读所有 PROBE 调用后的推理字段。

## 预设门槛失败

- OUTPUT-RENAME，`r1639a65ct:raise` 第 4 步 `unresolved_conflicts` 写出 **“全局表征偏离证据倾向真实，局部纹理证据倾向合成”**。前半句将没有真假方向的 PROBE 观察归因为真实倾向，明确越界；自动检查未覆盖这一字段。
- SUMMARY-MASK，`r0527f7e6t:flux` 的 STOP `evidence_gap` 写出 **“局部纹理与全局表征已形成倾向”**；OUTPUT-RENAME 同图 STOP `action_reason` 写出 **“局部纹理高分支持合成，全局表征偏离与之吻合”**。两句都把 PROBE 偏离纳入方向性取证支持，未保持该工具的非结论性边界。
- SUMMARY-MASK，`r1bca2388t:sd3_5` 第 5 步原始输出为 `next_action=STOP, final_verdict=uncertain, final_confidence=low`，被原 parser 拒绝；第 6 步重试后最终输出可解析。验收要求是**所有** STOP 输出都使用二分类 final verdict，因此这次原始 STOP 仍违反契约。未修改 parser 容忍该值。

因此，虽然 18/18 最终文件可解析且工程链正常，**Evidence-only 归因边界和所有 STOP 输出契约仍未通过**。按预设规则，本轮停止，不再叠加 prompt patch，不冻结 `actor0-evidence-v1`，不启动正式 900 条或 SFT。该结果记录为：**Prompt-only schema adaptation is insufficient to reliably enforce evidence attribution boundaries.** 这一现象可作为以后另行批准的 Actor SFT 训练目标，当前没有启动训练。

本地与远端原始结果 SHA-256 一致：`full.jsonl` 为 `f7a8a4857819c27a3b64fa38426b260b05026c81b6ccdf7dad90963931dd99f2`，`summary_mask.jsonl` 为 `8f26d9e2e02c9cfe9afd4d6793ab526e4b4216aaad1a45dddbb603e693408f84`，`output_rename.jsonl` 为 `ca30257c2066c6549514744c707eaafc3c69a0e175cdb05f5493941818ff55d7`，`check.json` 为 `3a4bbf2764efe919d2f6bacbd9a47fd775cf44be292c21cc328a646d4dcca182`。远端推理进程已退出，GPU 显存 1 MiB、利用率 0%，用户可以关卡。
