# Mini FaithBench v0 技术小样记录

**日期：2026-10-06**  
**状态：工程链通过；Evidence-only 语义检查未通过，正式 900 条尚未启动。**

固定样本为 RAISE 2、FLUX 2、SD3.5 2；包含 `r0d0ff43at:raise` 和 `r000da54ft:flux` 两张原 PROBE classifier 错例。每张分别运行 FULL、SUMMARY-MASK、OUTPUT-RENAME，共 18 条。样本清单位于 `../config/technical_sample_manifest.jsonl`，逐条记录和检查结果在本目录。

## 工程检查

| 条件 | 轨迹 | 最终解析 | 中间解析错误 | PROBE 调用 | 四图 Actor 步骤 | 全局后续调用其他工具 | 无效 callable |
|---|---:|---:|---:|---:|---:|---:|---:|
| FULL | 6 | 6 | 0 | 5 | 7 | 2 | 0 |
| SUMMARY-MASK | 6 | 6 | 0 | 5 | 7 | 2 | 0 |
| OUTPUT-RENAME | 6 | 6 | 0 | 5 | 7 | 2 | 0 |

三条件使用同一个 prompt candidate 和 `pixels` crop 模式。所有多图步骤的 processor `image_grid_thw` 数量与提供的图像数一致；三条件同样样本的 crop SHA-256 一致。输入的 PROBE 卡片禁用 classifier 结论字段扫描 0 命中。四项模型权重和配置哈希与旧 Actor-0 一致，processor 可离线加载。样本平均模型生成耗时分别为约 18.45、18.22、17.85 秒/条；这是小样运行时间，不作为正式实验准确率估计。

## 语义失败

尽管 PROBE Evidence v1 卡片没有 `signal`/`score`，三条件中 Actor 在获得该工具后各有 **7 个步骤**自行写出形如 `global_forensic_analyzer | signal=real | score=null` 或 `signal=real_like | score=null` 的摘要。这些值不是工具输入提供的，违反 Evidence-only 的语义边界。

原因可追溯到旧 Actor-0 的 `system_prompt.txt` 和 runner `rationale_prompt()`：两处仍要求每条工具摘要具有 `signal/score`；只替换 global Tool Card 未消除冲突。按照仓库 `AGENTS.md`，此问题影响实验解释，已经停在正式采集前，等待用户决定是否允许只修这两处摘要格式指令并重跑 18 条小样。不得用本小样调整 Evidence 数值、阈值、参考库或决策策略。
