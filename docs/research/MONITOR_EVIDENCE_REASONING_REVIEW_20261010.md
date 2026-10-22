# Monitor证据推断：论文经验与当前失败的对应复盘

日期：2026-10-10。状态：定向方法审阅与候选设计，未执行新的模型实验或SFT。延续[主方案](../Actor_Monitor_MVP_Protocol.md)、[既有相关方法](../MONITOR_RELATED_WORK_AND_IDEAS_20261009.md)、[36请求复盘](../../experiments/faithbench_monitor_v0/pilot_v3/REPORT_TYPED_SOURCE_FACTORS_20261010.md)及[CPU复盘](../../experiments/faithbench_monitor_v0/pilot_v3/REPORT_WORKFLOW_CPU_20261010.md)。Actor冻结，74预留来源组、GT、身份映射未读取；未向检索服务提供项目案例。

## 检索与证据范围

使用 nature-academic-search 的 multi-source-search 流程。学术检索MCP未挂载，改用技能提供的OpenAlex脚本、arXiv/ACL原文及GitHub作者仓库。OpenAlex初筛查询为 `grounded claim verification evidence entailment`，2020年起、8项；原始结果在[检索记录](monitor_literature_openalex_20261010.json)，元数据仅供发现，随后以原文核对。另从已有方法沿引用定向补充。首次脚本stdout编码失败，UTF-8重跑成功。

这是有边界的方法审阅，不是穷尽检索或系统综述。本轮核读下表9篇的方法关键段、相关消融/局限；未复现其模型或下载其数据。SymbCoT、Complex Claim Verification仅作补充筛选。论文中的改善限于各自任务，不能当成本项目收益；下面“应用建议”均为项目推断。

## 核心方法对照

| 原文与核读位置 | 可以吸取的经验 | 对应本项目错误与应用建议 | 不能直接照搬的部分 |
|---|---|---|---|
| Hu等，**RefChecker: Reference-based Fine-grained Hallucination Checker and Benchmark for Large Language Models**，2024；[v1原文](https://arxiv.org/html/2405.14486v1)，§4–5及官方checker prompt | 将可核验内容表示为细粒度三元组，再判蕴含/中立/矛盾。抽取本身也是待评价步骤。 | 分开“R1存在”与“R1具有某物体属性”；先确认当前断言覆盖，再审引用。 | 已核官方prompt存在“任一段支持即可蕴含”的优先规则；若用于监察多工具冲突，可能遮蔽另一段的反向证据，不能原样作为冲突聚合规则。 |
| Tang、Laban、Durrett，**MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents**，EMNLP 2024；[v2原文](https://arxiv.org/html/2404.10774v2)，§2、§3、§7.1及局限；DOI `10.18653/v1/2024.emnlp-main.499` | 训练材料要求核验句中全部事实；构造保留其他事实、只缺少决定性事实的对照，并检查剩余内容是否仍可支持。其测试中显式原子拆分没有一致收益。 | 保留R1、路径和数值，考察物体属性是否真的有来源；配以仍充分支持的正例，防止学成一律拒绝。 | 二分类unsupported混合了本项目需要区分的状态；单文档/任一文档支持假设不承担工具冲突监察。不要据此默认增加多阶段调用或直接移植其阈值。 |
| Metropolitansky、Larson，**Towards Effective Extraction and Evaluation of Factual Claims**（Claimify），ACL 2025；[v2原文](https://arxiv.org/html/2502.10855v2)，§2–3及抽取流程 | 抽取需要保留限定条件、消解歧义，并评价信息元素的覆盖，而不只看是否抽出一条句子。 | 拆分若丢掉“附近”、数量、范围或来源主体，后续核验即使正确也答错对象；应记录遗漏。 | Claimify筛掉不可核验内容的做法不能直接筛掉Monitor中的STOP、建议与规范性审查；不明确内容应保留为待核验，不能从分母消失。 |
| Tafjord、Dalvi、Clark，**ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language**，Findings ACL 2021；[PDF](https://aclanthology.org/2021.findings-acl.317.pdf)，§3.2及证明生成；DOI `10.18653/v1/2021.findings-acl.317` | 开放世界明确保留未知；证明链连接事实、规则与结论，缺事实与反证分开。 | 关键列表缺失时不能由“没看到”推成反证；理由应给出决定性的已有依据或缺口。 | 其形式规则/模板英语不能保证真实工具证据正确。项目“未返回”是来源归因状态，不是图像事实为假；沿用用户已确认的未知/未返回边界。 |
| DeYoung等，**ERASER: A Benchmark to Evaluate Rationalized NLP Models**，ACL 2020；[PDF](https://aclanthology.org/2020.acl-main.408.pdf)，§4.2；DOI `10.18653/v1/2020.acl-main.408` | 看起来合理的理由与实际决定依据有别；用保留/去除理由依据检验充分性与完整性。 | 对明确阈值证据做保留、删除决定性依据与删除无关依据的控制，检查判定是否按预审预期变化。 | 当前未计算ERASER概率指标；文本干预可能改变输入分布或造成关键字段缺失，需先审查干预后的状态，不能直接把任何翻转都计为成功。 |
| Hsieh等，**Distilling Step-by-Step! Outperforming Larger Language Models with Less Training Data and Smaller Model Sizes**，ACL 2023；[v2原文](https://arxiv.org/html/2305.02301v2)，§3.2、§4.4及作者代码 | 用明确任务前缀区分标签预测与理由生成；原文在其四项NLP任务上比较了分任务与串接理由/标签监督。 | 现有监督混用两种输出格式，值得用明确任务契约消除歧义；单独观测自由生成理由与标签的学习。 | T5双前向加权损失不等于8B decoder-only LoRA的现成修复。论文结果不能证明当前退化由schema混合造成，也不支持未经审阅的27B理由自动作gold。 |
| Lyu等，**Faithful Chain-of-Thought Reasoning**，2023；[v2原文](https://arxiv.org/html/2301.13379v2)，方法与局限 | 将自然语言问题转换为符号表示，再由确定性求解器执行；结论对所执行程序可追溯。 | 已确定的列表存在性、成员数、时间与预算等交给固定CPU核验，模型承担语义归因。 | 程序忠实执行不代表自然语言到程序的转换正确；不执行模型任意生成代码，不把结构验证等同于语义蕴含证明。 |
| Wang等，**SciLens: Multi-modal Scientific Claim Verification with Agentic Entailment and Grounding**，2026；[v1原文](https://arxiv.org/html/2606.20873v1)，§2、§3及附录提示；KDD 2026 SciSoc工作坊标识 | 为决定性断言绑定具体证据位置、实体、数量和限定条件；全部核心断言得到支持才支持整体。 | 借鉴“属性—证据位置”绑定，避免用区域编号证明物体身份；测试同一断言在配对证据上的一致区分。 | 其二分类把缺失/不清楚也归入Refuted，与本项目未知口径冲突；且允许背景解释不被证明，不能省略Actor解释中的越界归因。报告结果来自开发集，多阶段推理成本也不能照搬。 |
| Liu等，**Coverage-Controlled Preference Mining from Noisy Claim Verification for Evidence-Grounded Generation**（VERI-DPO），2026预印本；[v2原文](https://arxiv.org/html/2603.10494v2)，§3、§4、§6 | 自动核验标签有噪声；构造偏好时同时约束信息覆盖，防止通过少说、重复或模板化得到表面高分。 | 评价同时保留支持正例、未知识别、断言覆盖与有效中文解释，不能让一律“未返回”看似监察改善。 | 医疗摘要偏好学习不是Monitor训练验证；本轮仅借鉴覆盖控制，不启动DPO。其Not Supported表示显式冲突，不能按名称套用为本项目未返回。 |

补充筛选：[SymbCoT，ACL 2024](https://aclanthology.org/2024.acl-long.720/)采用LLM进行符号转换、规划与核验，不能因“符号”二字视为确定性执行；[Complex Claim Verification with Evidence Retrieved in the Wild，NAACL 2024](https://aclanthology.org/2024.naacl-long.196/)强调只取主张提出前的证据，其时点限制与项目已有边界相符，但外部政治事实检索流程不适合直接成为当前Monitor的证据来源。

## 作者代码的具体核验

本轮只读公开文件，没有运行外部训练器、加载模型或下载数据。

- RefChecker：[固定commit的checker_prompts.py](https://github.com/amazon-science/RefChecker/blob/1df1b25cee792ba2b171302e31ca4f768bd67703/refchecker/checker/checker_prompts.py)已核读。该多来源prompt优先任一支持，再考虑矛盾。前一日来源审计已记录仓库许可；若移植其他文件，仍应核对具体版本与许可。
- MiniCheck：[官方README](https://github.com/Liyan06/MiniCheck/blob/main/README.md)已读，提供可复用核验模型接口，但未下载模型、未检查全部实现或重新核验各权重许可。其英文文档任务与中文工具归因不同，不能直接当教师gold。
- Distilling Step-by-Step：[model_utils.py](https://github.com/google-research/distilling-step-by-step/blob/main/model_utils.py)的collator分开预测与解释输入，trainer分别前向后加权；[train_utils.py](https://github.com/google-research/distilling-step-by-step/blob/main/train_utils.py)用T5并支持两类训练路径。`LICENSE`核实为Apache-2.0。核读时Git blob SHA分别为 `790b3550630ebdb9ca45205469dbc2334a277520`、`02bc103eff65458f50f6d5d58bab38c3a1d7a3dc`，许可 `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`。未直接复制代码；该训练入口还会删除同名旧checkpoint目录，不能未经改造直接运行。

## 当前问题的更准确解释

项目证据表明：引用可定位仍可能不覆盖断言；缺字段与未返回易混淆；明确文本会被相邻数值遮蔽；既有SFT自由生成丢失解释。训练CPU复盘确认自然任务没有未知监督，且两类输出格式共存。自然支持实际曝光8步，未返回6步，因此“负例次数更多造成一律未返回”不符合这个历史批次。

这些事实提示监督覆盖与任务契约值得改进，却没有证明退化的唯一原因。已有精度路径配对未修复选定输出，mask/目标完整也不等于训练设置充分。不能因论文采用某方法就倒推当前错误的因果解释。

## 建议的下一步，按优先级

1. **先补证据辨别监督，后决定是否增加显式拆分。** 用既有获准开发来源准备候选监督设计：同一主张的决定性属性有/无、关键列表有/缺、直接文本有/无、只改无关字段。每对预审完整来源和可辨别事实，保留支持正例、未返回及未知；不按字符串匹配自动赋语义标签。MiniCheck与SciLens给出不同拆分策略，应先选最简单可核验契约，不能把全部论文模块串起来。
2. **先统一自由生成契约，再做训练结构对照。** 一个清楚的中文监督接口是候选基线；显式label/rationale任务是另一个可比较方案。先检验已训练样例能否生成针对断言的理由、正确叶子引用和状态，再看未参与训练的控制家族；理由是状态/EID一律不能算解释。两种方案不要与新数据、超参和多阶段流程同时改变后声称单因素效果。
3. **评价加入证据依赖与覆盖。** 记录断言遗漏、引用是否覆盖决定性内容、正例保留、未知/未返回混淆、理由与状态一致性。已有反复检查片段只能做回归，控制家族留出也仍是开发诊断；不得宣称独立准确率。论文中的概率或宏观分数不替代当前逐条细审。
4. **最后回到完整监察。** 局部来源核验之外，继续审多工具冲突、推断越界、预算/可用动作下STOP及合法干预。来源正确不能自动推出STOP合理；维持[最终聚合草案](../../experiments/faithbench_monitor_v0/pilot_v3/PLAN_FINAL_INTEGRATION_DRAFT_20261010.md)的研究范围，不执行Actor动作。

下一份可审产出应是候选接口、监督样例规范、对照表和具体用卡预算；当前没有生成新控制、改变冻结协议或启动训练。影响标注/实验设计的未决项按AGENTS第1条确认后冻结执行。用户的SFT授权仍有效，适合条件由数据与验收契约明确后判断，不能仅由论文正面结果判断。

## 细审与复审边界

写后按原文复核：MiniCheck为二分类；SciLens缺失判Refuted与项目口径不兼容；Distilling为显式多任务而非未经区分的schema混用；ERASER概率指标本项目未计算。作者代码仅只读审查。复审为同一助手非盲复审，不是独立双人审核；没有把任何项目开发标签升级为gold。
