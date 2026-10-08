# 复用核对与来源

核对日期2026-10-08。本轮没有新增数据集、生成假图、下载第三方模型或复制外部代码/数据。

| 材料 | 复用内容 | 许可与适用范围 / 差异 |
|---|---|---|
| 本仓库 B0-D audit_assist | 已盲化输入、条件工具卡、CALL先锁定流程；直接复用 `assemble_audit.readl/writel/verify_lock` | 既有获授权研究数据的本地开发用途；逐样本、图像与身份信息不发布。审计 proposals 仅silver |
| 本仓库 Actor-B protocol | 复用 `extract_object`，不重写JSON围栏解析 | 只提取对象；Monitor自己的检查状态与引用用新协议。Actor工具/STOP schema不修改 |
| Mini FaithBench v0 | 核对6图×3条件技术检查、Evidence边界和原runner | 旧Actor输出格式与B0-D不同；当前适配器限定B0-D，不强加兼容层。旧真假指标/正则归因筛查不作为新标签生成器 |
| [GLEAN 原论文](https://arxiv.org/abs/2603.02798) | 规范与逐步骤证据对齐的设计思路 | Yichi Zhang et al., 2026, *Guideline-Grounded Evidence Accumulation for High-Stakes Agent Verification*。原应用为临床诊断；其证据累积、贝叶斯校准与主动核验未在本原型实现。未引入代码/数据，代码许可不作假设 |
| [Vectara FaithBench](https://github.com/vectara/FaithBench) / [论文](https://arxiv.org/abs/2410.13210) | 核对现有来源支持的忠实性标注及争议保留方式 | 仓库[LICENSE](https://github.com/vectara/FaithBench/blob/main/LICENSE)为CC BY-NC-SA 4.0，不是MIT。原任务为文本摘要幻觉，不能直接覆盖取证工具选择与STOP。未使用其数据/代码；本项目工作名不表示官方数据集扩展 |

标注维度依据本项目主方案，不由外部摘要 benchmark 自动迁移。没有复现或声称上述方法的完整性能。

本轮使用 `experimental-design` 技能检查实验单位、相关重复和未来评估边界，未进行新随机化/分组。按技能要求记录来源：Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel, Aubrey M. Brueckner (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. [arXiv:2609.00065 v2](https://arxiv.org/abs/2609.00065), [DOI](https://doi.org/10.48550/arXiv.2609.00065)。作者/版本从原始arXiv核验，引用不表示本项目获得外部效能验证。
