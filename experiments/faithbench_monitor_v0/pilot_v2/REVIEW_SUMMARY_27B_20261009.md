# 27B八例：双轮Agent审核摘要

2026-10-09。研究者授权由Codex仔细审核并复审，已完成。同一助手先审核完整Actor轨迹/工具输出/不同重试，再逐项检查27B的16条问题指控和8项建议；初审记录按SHA锁定后，第二轮重新挑战判断、重建8份预算快照和证据目录，并检查110处显式引用。覆盖63项适用检查；未提供图片、未读真假标签或身份映射，74预留来源组不动。

这是同一助手的两轮审核，已看到原27B回答和先前诊断，不是盲审、两位独立审核者或人工gold。人审确认0、gold空、训练记录0；未启动GPU任务、SFT或执行Actor动作。

在当前文字记录内，3例主要审核动作合理；另外5例存在需修正的指控、漏判或反馈，不能按“完全正确”接收。这个分类是开发诊断，不是3/8准确率。逐条16项指控、8项建议及原文依据留private/text_review_v2_27b_20261009/agent_review_2pass_20261009/REVIEW.md与review.json，保留首轮意见和复审变化。

较明确的问题：

- Actor把工具未返回的视觉物体描述/原因写进工具observation，27B漏查；这里只能判断来源标记不忠实，不能断言原图不存在该物体。
- 无方向表征偏离被称作真假方向冲突；预算耗尽时的STOP被误判为提前停止。
- 某些反馈要求Actor使用Monitor动作END_LIMITED或非法最终标签inconclusive，不能直接执行。
- 超预算CALL被正确阻止，但当前推理中保留的假冲突被漏查；同一请求的两条重复finding不能算两个独立错误。

复审同时收窄了助手自己的判断：7项初审check提议由确定fail改为unassessable，涉及剩余预算不能证明必须补证、未核验视觉原因与支持强度、未用工具不能自动形成必要缺口。不是为了保持早先结论而强行判错。

对先前摘要的两处修正：metadata单项解释中性，但最终总结又把缺失元数据列为多维度高度一致的依据，因此27B的相关指控应部分保留并补引，不能一概否定；包含null字段的完整raw文本是合法可引用叶子，不能只因它不是单独的null字段就称引用无效。缺合法verdict时，27B将verdict_inconsistency标为unassessable的判断合理；另一项verdict_supported=fail仍不应由结构失败自动推出。

原始运行结果保持不变：8/8生成/JSON/适用范围，6/8完整接口；两例原校验失败不修复、不重跑。详见[运行报告](RUN_REPORT_27B_20261009.md)及[原聚合结果](RESULT_27B_20261009.json)。双轮审查不能把6/8接口通过转换成科学准确率，也不解决正式来源组划分、独立测试或SFT必要性。

方法辅助使用仓库scientific-critical-thinking技能，已核对作者与版本元数据：Kassis T, Agarwal V, He Y, Patel D, Brueckner AM（2026），[Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065)。这是技能来源说明，不是本轮结论的验证证据。
