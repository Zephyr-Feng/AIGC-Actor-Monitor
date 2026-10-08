# FaithBench 开发与离线 Monitor v0

用户于2026-10-08授权无卡准备；本目录实现文字审核的输入适配、中文规范/提示词、输出 Schema 和引用校验。**没有模型推理、训练、正式分割或效能评价。** Actor-B0-C 保持原冻结版本，B0-D正式 gate 仍 INCONCLUSIVE。

## 文件与运行

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
