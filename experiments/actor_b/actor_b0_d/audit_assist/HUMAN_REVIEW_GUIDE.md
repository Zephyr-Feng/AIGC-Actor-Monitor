# 独立人工复核

本轮为 80 条轨迹全量人工复核，以及 Agent 全量预审后选出的 P0/P1/P2 CALL 子集风险复核。不能称为 827 次独立人工标注。标签锁定前不阅读 GT、Accuracy、正确错误标记、诊断类别或历史检测器准确率；评估的是 Actor 实际观察下的取证和解释。

在仓库根目录运行：

```powershell
python experiments/actor_b/actor_b0_d/audit_assist/render_review.py
```

用浏览器打开 `review_packets/human_review.html`。页面完全离线自包含，原图和已经观察的裁片使用原始图像字节。按盲 ID 独立查看一条轨迹的图像、全部 observation、动作、原始 STOP、有效终态和 Agent 八标签依据；CALL 页面只展示该次请求之前的历史、之前重试、当前请求、预算和可用工具，不展示未来 observation 或最终 STOP。

逐条勾选“已阅读证据”，填写中文理由，选择“单条接受 Agent 建议”或“保存人工修改”。标签包含 `unassessable`；缺源或争议应使用相应状态，待补证据或裁决。Agent 建议不会自动成为人工标签，也没有批量接受入口。每次操作暂存于当前浏览器，按输入指纹隔离；定期下载 `human_reviews.json`，换浏览器时载入该文件。浏览器存储不是长期备份。

同图四条件都完成 confirmed/modified 后，页面才显示配对比较。先完成独立判断，再查看条件差异；不要先用其他条件结果影响本条初始判断。

CALL 队列提供 `HUMAN_REVIEW_QUEUE.csv`，可按优先级与原因筛选。P0 全量保留，P1 按清单复核，P2 分层抽查；工作量以去重记录数为准。80条轨迹的停止充分性均需确认，包含弱证据样本。原始无效 STOP 与最小投影终态分别展示，投影不能替代 Actor 原始独立成功。

导入入口仅在研究者真实完成复核后使用：

```powershell
python experiments/actor_b/actor_b0_d/audit_assist/import_human_reviews.py --reviews D:/path/human_reviews.json
```

导入检查版本、指纹、标签枚举、人工证据勾选、非空理由、时间和记录关联。私有 `identity_map.json` 仅用于恢复原 sample_id，不进入 HTML；CALL 使用保存的零起始 row_index 并核对 sample/condition/step/raw_attempt。原人工标签与新标签冲突时停止，报告盲 ID，不覆盖旧标签。每次写入前备份两份原文件到 `work/backups/时间戳/`，文件名含原 SHA-256。仅 confirmed/modified 写入原评估标签字段；缺源和争议记录只写入状态元数据，不把 Agent 建议填进人工标签。

80 条轨迹以及队列全部 CALL 都完成人工 confirmed/modified、缺源与争议已裁决后，使用同一完整导出加 `--lock`，生成 `HUMAN_LABEL_LOCK.json`。研究者可有理由地最终确认某字段为 `unassessable`，不强迫猜 true/false；锁定记录各字段无法判断数，原评价器的布尔统计仅使用实际布尔标签，必须同时报告可判断分母。锁定文件明确记录 CALL 为 subset risk-review，锁定本身不运行含 GT 评价。

只有锁定后研究者显式执行 `--evaluate` 才调用 `evaluate_b0_d.py` 解盲评价。默认导入不评估，也不修改 gate 决策。入口在评价后恢复包含人工元数据的标签文件；人工导出、备份与锁定记录应长期保留，最终 gate 仍需依据本轮人审范围和争议情况人工讨论，不把子集复核声称为 full human audit。
