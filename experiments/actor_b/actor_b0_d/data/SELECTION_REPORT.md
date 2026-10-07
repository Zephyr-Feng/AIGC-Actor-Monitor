# Actor-B0-D 诊断样本选择报告

## 数据来源与边界

本清单复用 Actor-B0-C 已冻结的 60 张 eval 图及其 20 个来源组，每组 3 张；不新增图片、不抽取预留给 Monitor 的来源组。
这是一份新建的诊断 manifest，但样本不是独立于 B0-C 的新 held-out 集。所有结果仅用于本轮配对策略诊断，不作总体准确率或独立泛化估计。
历史 PROBE 分类错误共 4 张；与当前 60 张交集为 0 张。按用户确认，PROBE 类由 Evidence-only 困难近似样本组成，不宣称包含旧分类错误例。
未触碰 B0-C 已标记为 Monitor test 预留的 74 个来源组。当前 cohort 的四条件重复测量按 sample 配对，并按 20 个 source_group 作为区组解释；图像不视为独立同分布抽样。

## 预注册分层规则

类别互斥且合计 60。方向标签只从冻结的局部纹理与互补取证 signal 映射得到；global PROBE 的 Evidence-only 偏离不产生方向。GT 仅用于离线类别/最终指标，不写入 actor_input_manifest，也不进入 Actor 对话。

- **EASY_AGREEMENT（12）**：局部纹理与互补取证方向相同，且两者 strength 均为 high 或 moderate。
- **PROBE_FAILURE_COMPLEMENTARY（12）**：real 子类从 real 图中按 frozen Evidence-only `max_deviation_percentile` 排名前 4 形成 false-alarm-like 近似挑战，实际分配 3 张；fake 子类从 PROBE 偏离 percentile ≥95 且两个方向工具冲突者中分配 9 张。没有可用的历史 PROBE classifier 错误图。
- **TOOL_DISAGREEMENT（16）**：局部纹理与互补取证给出相反方向；标签不依赖 Actor verdict。
- **WEAK_EVIDENCE（10）**：两个方向工具至少一方 strength 为 low，或两方均未达 high；代表证据不足或强度不稳定。
- **DIFFICULT_SOLVABLE（10）**：B0-C raw verdict 错误/无效，或历史 image-only baseline 错误；同时至少一个方向工具与 GT 同向，作为有可用互补线索的困难样本。

同一行可能满足多项候选规则；用确定性最大流在候选集合中互斥分配，以满足固定总数及 easy/difficult 的 1:1 标签建议。类别间的实际标签数见表。算法以 SHA-256 对样本键排序，且保留源 manifest 的原始运行顺序。

## 分层结果

| 类别 | n | real | fake | source groups |
|---|---:|---:|---:|---:|
| EASY_AGREEMENT | 12 | 6 | 6 | 10 |
| PROBE_FAILURE_COMPLEMENTARY | 12 | 3 | 9 | 10 |
| TOOL_DISAGREEMENT | 16 | 4 | 12 | 12 |
| WEAK_EVIDENCE | 10 | 2 | 8 | 8 |
| DIFFICULT_SOLVABLE | 10 | 5 | 5 | 8 |
| **合计** | **60** | **20** | **40** | **20** |

## 可复现输入

- B0-C source manifest SHA-256: `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`
- B0-C frozen tool-results SHA-256: `94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`
- B0-C raw trajectories SHA-256: `276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`
- Actor-facing manifest: `actor_input_manifest.jsonl`，只含 sample_id、relative_path、image SHA-256；不含 GT、source_group、generator 或诊断类别。
- Diagnostic manifest: `diagnostic_manifest.jsonl`，含 GT 与类别，仅供本地离线评测。
- Human audit set: 每个 easy、conflict、PROBE-proxy、weak 类别固定抽 5 张，优先跨 source_group 覆盖；四 condition 共 80 份人工审核记录。

## 限制

此诊断样本按既有工具输出和 B0-C/Actor-0 历史困难情况分层，具有结果导向的目的性抽样；balanced accuracy 等只作该挑战集上的背景描述。PROBE 类是近似压力测试，不可写成真实 PROBE 错误复现。来源组内三种 generator 相关，统计解释以配对和组级描述为主。

## 工作流参考

本地元数据盘点采用可复现、限制输出的研究 Agent 工作流；该文献不作为图像取证或工具策略假设的科学证据：Kassis et al. (2026), *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*, arXiv:2609.00065, https://arxiv.org/abs/2609.00065.
