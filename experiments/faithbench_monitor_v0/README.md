# FaithBench 开发与离线 Monitor v0

> 当前（2026-10-13）：[自然30组结果](independent_evaluation_v1/REPORT.md)已完成Actor/30次DeepSeek/逐例初评，找全核心10/23、可用反馈5/23、新增错误4/30。局部能力有，但本配置不能认定独立自动审核通过。GPU/API退出，研究者确认0；FULL20不重跑、不训练、不执行反馈。下方旧日期服务状态属于历史。

> 2026-10-10：按持续用卡自主授权完成七轮实验及复审，尚未采用默认。当前18203实例服务PID1503健康、无runner；G完整接口8/8，H来源6/6但语义不稳定，第八轮尚未实现/启动。接续先读[最新交接](../../docs/SESSION_HANDOFF_20261010.md)、[阶段总结](pilot_v3/ITERATION_REVIEW_20261010.md)与[最新进度](../../docs/PROJECT_PROGRESS.md)。下列v2结束/待人审状态是旧阶段记录；仍不SFT、不执行Actor反馈，人工gold0、74预留来源组未读。

用户于2026-10-08授权初始无卡准备；本目录实现文字审核的输入适配、中文规范/提示词、输出 Schema 和引用校验。8例Monitor v1/v2冻结8B及27B单次推理均已完成，27B完整接口6/8、语义待人审，服务退出、显存0 MiB，可关卡；现行入口见[pilot_v2](pilot_v2/README.md)、[27B报告](pilot_v2/RUN_REPORT_27B_20261009.md)和[新对话交接](../../docs/SESSION_HANDOFF_20261009.md)。Actor-B0-C保持冻结，B0-D正式gate仍INCONCLUSIVE；未训练、正式分割或独立效能评价。

## 文件与运行

以下入口说明初始开发包；接续8例任务使用v2的`private/pilot_v2_locked`，不重新运行准备器。

- [标注规范](ANNOTATION_GUIDELINES.md)：七类问题、引用、时间边界、争议标签。
- [Monitor prompt](monitor_prompt.md)、[输出 Schema](monitor_response.schema.json)、[协议与解析](monitor_protocol.py)。
- [复用核对](REUSE_REVIEW.md)：既有实现、公开材料、许可和适用差异。
- [阶段报告](PREPARATION_REPORT.md)：实际生成与验证结果、下一步待决定事项。

在仓库根目录运行（仅本地读写，不连接模型）：

```powershell
python experiments/faithbench_monitor_v0/prepare_dev.py
python -m unittest discover -s tests -p test_faithbench_monitor.py -v
```

首次准备读取已有四条件盲化且 SHA 锁定的输入与预审，输出到 Git 忽略的 `private/`：827 CALL前缀、80终态、单独的 silver annotations/后处理元数据、已观察资产索引、8示例请求和来源/产物hash。已有目录时拒绝覆盖。原图/crop 不复制，原锁及人工标签不改。60个不同盲图ID不是新抽样；80终态是同20图四条件，827请求含相关重试。

`render_request(packet)` 可导出任何开发输入的文字请求；仅从输入、规范、prompt和Schema生成，不读取预审标签。实际模型接入及多模态版本待确认。示例请求含私有轨迹，不能上传 GitHub。

外部确认的 Monitor 原始响应采用 JSONL：每行 `{"case_id":"call_0001","raw":"<模型返回JSON字符串>"}`。校验入口：

```powershell
python experiments/faithbench_monitor_v0/check_responses.py --inputs experiments/faithbench_monitor_v0/private/inputs.jsonl --responses experiments/faithbench_monitor_v0/private/responses.jsonl --output experiments/faithbench_monitor_v0/private/checked.jsonl
```

入口检查结构、引用原文及状态一致性，保留失败原因；不会生成缺失响应、自动修正标签或计算真假准确率。引用正确与语义正确不是同一个指标。真实推理前确认模型、范围、视觉输入、标签依据与评价规则，再告知开卡时段。
