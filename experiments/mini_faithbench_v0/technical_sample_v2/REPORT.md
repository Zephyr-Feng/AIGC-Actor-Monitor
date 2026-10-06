# Mini FaithBench v0：接口修复后技术小样

**日期：2026-10-06。结论：未通过预设门槛；正式 900 条未启动。**

用户授权的接口修复只改了 `config/system_prompt.txt` 中工具证据摘要格式，以及 `run_mini.py` 的 `rationale_prompt()` 中同一要求。旧 Actor-0 prompt material SHA-256 为 `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`；第一次仅改 Tool Card 的失败候选为 `78ea83dfcf59a75fb7b9909ffe4492551a3c44635f50566329c5c759fd8f4359`；这次 Evidence-compatible **候选**为 `cc128afa3e4f6ec0f0cc68509386c2668f6375f551fdc45803369746b6c8882f`。完整 system prompt 文件 SHA-256 为 `086c3696b96ca810c1fa8c416a13a0bbb88318e9ac21802ae23d549a5f281384`，runner 文件 SHA-256 为 `807a71d35a54cefd686ec95d797de8ef810b6df4bcb36e21e49433f82619d496`。本候选**没有冻结**；三条件在本次小样使用同一候选 prompt。

固定 6 张图、每张 3 条件，全部 18 条已运行。没有依据小样的准确率、工具选择或真假判断修改 prompt、Evidence 参数、Actor 决策规则或 STOP 规则。PROBE Evidence v1 和其余工具实现保持不变。

| 条件 | 轨迹 | 最终输出可解析 | 中间解析错误 | PROBE 调用 | 四图 Actor 步骤 | PROBE 后调用其他工具 | 非法 callable | 显式/隐式 PROBE 分类摘要命中 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 6 | 5 | 3 | 6 | 20 | 6 | 0 | 0 |
| SUMMARY-MASK | 6 | 6 | 0 | 6 | 18 | 6 | 0 | 1 |
| OUTPUT-RENAME | 6 | 6 | 0 | 6 | 22 | 6 | 0 | 1 |

三条件 crop 模式均为 `pixels`；所有四图步骤的 processor image grid 数与输入图像数相等，同一图被 PROBE 调用时三条件 top-3 crop SHA-256 一致。Actor-facing PROBE 卡片的 classifier 结论字段扫描为 0 命中。OUTPUT-RENAME 正常调用原 callable `global_forensic_analyzer`。四类工具均在小样中实际被调用。与第一次小样不同，检查未发现 Actor 为 PROBE 直接补写 `signal/score`，但出现如下隐式归类：

- SUMMARY-MASK，`r0d0ff43at:raise`，第 4 步 `supporting_evidence`：**“表征偏离证据倾向真实”**。PROBE 卡片没有提供真假倾向。
- OUTPUT-RENAME，`r000da54ft:flux`，第 5 步 `supporting_evidence`：**“全局表征偏离高但集中，局部纹理与互补模型均倾向真实”**。该句把 PROBE 的偏离观察与 classifier-style 工具的真假倾向混合，作为全局证据解释存在语义越界风险。

FULL 的 `r1639a65ct:raise` 在调用完四类工具后两次输出 `next_action=STOP` 及 `final_verdict=uncertain`，不符合既有 final verdict 解析契约，因此该轨迹无可解析最终输出；另一条 FULL 轨迹出现 1 次中间解析错误后恢复。原始无效 JSON 已保存在轨迹的 `actor_output_raw` 中。未因小样修改解析器或 Actor STOP 规则。

**停止条件已触发：**18/18 可解析及 Evidence-only 语义边界均未达到。正式 900 条不启动，`actor0-evidence-v1` 未冻结；下一步需与用户讨论是否以及如何处理这两类失败。AutoDL GPU 进程已退出，显存 1 MiB、利用率 0%，可以关卡。

归档：`trajectories/{full,summary_mask,output_rename}.jsonl`、`check.json`、`run.log`。本地与 AutoDL 对应轨迹、检查文件的 SHA-256 完全一致：

| 文件 | SHA-256 |
|---|---|
| `full.jsonl` | `9563f2fe85acd841feca1d35d9aa705200848eb48c4c811e5976d0f26d94abcc` |
| `summary_mask.jsonl` | `f2ff0212a52845d5527f0be7bfac35e420d91858ac31170e2ecfcaceb2706e33` |
| `output_rename.jsonl` | `f0c784104e2d821c6da55a91cefcc6a13f3f62bf4e763b88cef5ff9024dfce10` |
| `check.json` | `88244dbdc958204ea6dd8c55d1466175dabd586d19709a73cedeccc42e7e58af` |
