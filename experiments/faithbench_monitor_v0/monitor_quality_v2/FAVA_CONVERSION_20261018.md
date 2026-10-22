# FAVA现成标注CPU转换交付（2026-10-18）

用户授权利用别人已标好的数据并程序转换。本次下载并转换FAVA作者training.json，实物30,073条（非数据卡概数35k）。未下载460段评估标注，未调用模型、教师API、Actor、GPU、SSH、训练或任何哈希，未新增训练/评估划分。原143份助手全文反馈保留，剩余877份不再逐条手写。

## 实物

`data/fava_existing_annotations_v1_20261018/`保留原始training.json（137,320,668字节）、UPSTREAM_DATA_CARD.md和converted_v1目录。converted.jsonl有28,721条，quarantine.jsonl隔离1,352条并保留原记录索引，summary.json提供实际计数和验证记录。

共97,494个作者问题标注、68,828个明确编辑；7,320条每个已标问题都有编辑，25,364条多问题。635条没有问题标签，不自动认定无错。回答字符数最小43、中位586、最大4,201，均含5张原始参考卡。未实测监督token。

## 格式与缺口

input保留审核范围、证据卡及完整回答。supervision.issues保留错误类型、原句、起止位置和作者明确编辑；original_completion与原记录索引可追溯原文。completion中的delete为错误文本、mark为作者修正，转换已验证方向。

作者未给出逐问题证据绑定、中文理由和正确内容保护项，对应字段保持null。edit_projection仅应用明确编辑，未获编辑的标注内容仍保留；仅当所有已标问题均有编辑时填写corrected_answer，仍不证明不存在漏标或语义错误。完整旧反馈契约合格数为0；这是可复用的合成定位/编辑部分监督，不能冒充完整中文反馈或人审gold。全部human_gold=false、semantic_verified=false、approved_for_training=false。

隔离原因：标签格式损坏646、嵌套结构超出当前支持611、无错误类型编辑60、未知标签或属性29、空参考5、原回答还原不一致1。隔离不等同语义错误，不猜测修复。

## 验证

convert_fava.py与test_convert_fava.py位于本报告同目录。五项测试通过，覆盖编辑方向/重复原句位置、插入/删除、缺失修正、坏标签/文本拒绝、隔离与防覆盖。独立检查全部28,721条原completion一致、原句偏移、编辑回放、缺失字段和标记；成功与隔离互斥且合计30,073。未逐条语义认证或证明模型效果，未冻结训练用途及预算。

复现：python experiments/faithbench_monitor_v0/monitor_quality_v2/convert_fava.py --input data/fava_existing_annotations_v1_20261018/training.json --output <全新目录>

## 来源与署名

Abhika Mishra、Akari Asai、Vidhisha Balachandran、Yizhong Wang、Graham Neubig、Yulia Tsvetkov、Hannaneh Hajishirzi，Fine-grained Hallucination Detection and Editing for Language Models（2024）。数据卡CC-BY-4.0，底层文本权利另行适用；本次仅修改为结构化衍生格式并保留原始标注。

https://huggingface.co/datasets/fava-uw/fava-data
https://github.com/abhika-m/FAVA
https://arxiv.org/abs/2401.06855

文档首次写入因审批服务网络流解码失败而未执行，随后通过同一审批流程重试；没有绕过审批。下一步基于实际适配需求决定定位/编辑任务、核对来源分组及暴露，再冻结训练/评估分配与预算，不自动执行。
