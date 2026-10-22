# FakeBench 精读笔记：会解释、会判别与会忠实推理，是三件事

> 来源覆盖：用户提供的 TIFS 2025 正式论文 PDF，共 16 个文件页，含正文、参考文献与作者信息；未提供独立补充材料。
> 提取置信度：High；用 PyMuPDF 官方 CLI 读取正文，并目视核对构建图及主要结果表。
> 定位模式：structure-grounded；按章节、图、表、公式定位，不使用页码引文。
> 主要分析视角：resource，数据集及能力诊断基准。
> 次要分析视角：methods，提示与评测设计。
> 外部背景核查：targeted external check，仅核对作者仓库的公开内容和获取边界。
> 笔记完整性：相对所给正式论文完整；标注细则、完整评测提示等补充细节不可评估。
> 阅读日期：2026-10-20；[Paper] 为原文报告，[External] 为外部核实，[Analysis] 为助手分析，[Hypothesis] 为待检验设想。

**来源原件**：[用户提供 PDF](C:/Users/zhangzifeng/Desktop/论文/FakeBench_Probing_Explainable_Fake_Image_Detection_via_Large_Multimodal_Models.pdf)。本笔记以正式期刊版为准，不用早期 arXiv 摘要替代其更新后的实验和表述。

**流程例外：** [nature-paper-card 技能](D:/Codex/AIGC/.agents/skills/nature-paper-card/SKILL.md)的默认准备脚本含无法跳过的 SHA256 步骤，依用户禁令未执行，采用环境 PDF 能力回退；使用原装无哈希审核器检查笔记结构，图表覆盖另作人工核对。

## 01 基本信息

| 项目 | 信息 |
|---|---|
| 标题 | FakeBench: Probing Explainable Fake Image Detection via Large Multimodal Models |
| 作者 | Yixuan Li、Xuelin Liu、Xiaoyang Wang、Bu Sung Lee、Shiqi Wang、Anderson Rocha、Weisi Lin |
| 机构 | City University of Hong Kong、Jiangxi University of Finance and Economics、Drexel University、Nanyang Technological University、University of Campinas |
| 出版 | IEEE Transactions on Information Forensics and Security，20，8730–8745，2025 |
| DOI | [10.1109/TIFS.2025.3597211](https://doi.org/10.1109/TIFS.2025.3597211) |
| 接收与上线 | 2025-07-22 接收；2025-08-13 发表 |
| 代码/查询入口 | [作者仓库](https://github.com/Yixuanli423/FakeBench) |
| 核心贡献 | 三个数据组成、14 类视觉线索分类、四种能力诊断及鲁棒性分析 |
| 与当前项目关系 | 提供解释与判别脱钩、错误前提诱导、能力回归的相关证据；不是独立 Monitor 训练集 |

[Paper: Title page; Sections I, III–V]

术语约定：LMM＝Large Multimodal Model，大型多模态模型；AIGI＝AI-generated image，AI 生成图像；CoT＝Chain-of-Thought，思维链提示。`explanation` 统一译为“给定判断后的解释”，`reasoning` 译为“先分析再判断的推理”；早期页面中的 `interpretation` 不另立为第五个任务。`golden clues` 为作者的人机协作参考线索，不表示已经证明模型内部因果机制。

## 02 一句话总结

[Paper] FakeBench 以 6,000 张真假图及三种 VQA 数据组成，分别测判别、给定标签后的解释、未给标签的推理和细粒度线索分析，发现这些能力并不同步，显式 CoT 在多种模型上反而降低检测成绩，错误前提也容易诱导模型编造依据。[Paper: Sections III-D, IV-B–D, V-B]

## 03 研究问题

[Paper] 只看真假分类无法判断模型是否理解可见伪造线索，也无法检查其输出是否对普通用户有帮助。论文将问题拆成四项：[Paper: Section I; Figure 1]

| 问题 | 要求模型做什么 | 关键区别 |
|---|---|---|
| RQ1 判别 | 直接判断图像是否生成 | 只测最终真假回答 |
| RQ2 解释 | 已知图像为假，说明依据 | 提供正确标签，检验能否为给定结论组织线索 |
| RQ3 推理 | 先找线索，最后自己判断 | 不提供真假标签，需处理线索到结论的映射 |
| RQ4 细粒度分析 | 回答纹理、阴影、透视等方面的问题 | 单独检验某类线索的分析能力 |

精确问题是：**一个能够给出正确真假答案的 LMM，是否也能提供准确、相关的线索，并在没有答案提示时用这些线索得到正确判断？**

[Analysis] 这是可观察行为的拆分，不是对模型内部认知过程的直接测量。文中的 effect-to-cause / cause-to-effect 是提示任务方向，不能据此认定获得了因果识别。

## 04 研究背景与发展路径

以下为 **[Paper-framed; external verification not performed]**。[Paper: Section II]

| 路线 | 主要能力 | 缺口 | 本文位置 |
|---|---|---|---|
| 专用真假检测器 | 学习频谱、纹理或表征痕迹 | 二分类结果难解释 | 作为判别参照 |
| 热图、特征或可视化解释 | 展示关注位置或抽象特征 | 不一定能传达可理解的具体依据 | 转向自然语言线索 |
| 通用 LMM | 看图、回答、生成叙述 | 是否理解真实性线索不清楚 | 分任务诊断已有基础模型 |
| FakeBench | 同时提供判别与线索评测 | 面向人类可见线索，仍不等于内部推理透明 | 明确归于 post-hoc explainability |

[Paper] 正式版特意区分解释性与内部可解释机制：FakeBench 评价的是面向人的事后说明，不声称透明展示模型内部决策路径。[Paper: Section II-A; Section III-A]

## 05 论文识别的核心痛点

| 痛点 | 具体表现 | 作者解释或设计响应 | 证据 |
|---|---|---|---|
| 分类成绩掩盖过程问题 | 会判真假不一定会给准确依据 | 拆分四项能力 | [Paper: Figure 1; Section IV-B.4] |
| 缺少自然语言取证标注 | 传统数据多为真假标签 | 构建参考线索和分维度问答 | [Paper: Section III-D] |
| 可见伪造概念不统一 | 纹理、阴影、透视等线索混在一起 | 14 类分层分类 | [Paper: Section III-C; Figure 3] |
| 显式推理未必有益 | 生成描述后反而判错 | 对比直接回答与 CoT | [Paper: Table IX; Figure 7] |
| 对用户错误前提顺从 | 真实图也可被要求解释为何假 | 错误标签提示压力测试 | [Paper: Section V-B; Table X] |

[Analysis] 作者将部分失败归因于取证知识不足、线索映射不足等。这些是有结果和例子支持的解释，但缺少逐因素干预，不能当作已排除所有替代原因的根因鉴定。

## 06 核心思想

**表层方法。** [Paper] 把取证检测做成有不同信息条件的视觉问答，既比较答案，也比较对伪造线索的语言描述。[Paper: Section III-D; Figure 4]

**核心洞见。** [Paper] 给定结论后为其找理由，与不知结论时自己推理，不是同一任务。模型在前者上表现好，不能自动支持后者可靠。[Paper: Section IV-B.2; Tables VI–VII]

**一般原则。** [Analysis] 在研究评测时，应分别记录最终判断、证据内容是否正确、证据是否支持判断、反馈是否诱导错误。自然语言流畅或与参考答案相似，只覆盖其中部分维度。

## 07 方法总览

```text
收集 3,000 张真实图 + 3,000 张生成图（10 类生成器）
  → 人类真假识别研究及 14 类可见伪造线索分类
  → FakeClass：6,000 个闭式真假问答
  → 生成图：GPT-4V 初稿 + 人类专家审核、增补、删改
       → FakeClue：同一批生成图，两种提示，共 6,000 个长解释查询
       → 单模态 GPT 重组线索
            → FakeQA：约 42,000 个细粒度问答
  → 14 个 LMM 零样本测试
  → 规则判答案；文本相似度 + GPT-4 评分判描述
  → 补充 CoT、图像变换、错误前提和外部数据集分析
```

[Paper: Sections III-B–E, IV-A, V]

**输入边界最重要：** 解释任务明确告诉模型“这是假图”；推理任务不给标签。参考线索构建有额外人工示范，但解释能力评测使用没有人工示范的简化提示。不能把参考生成流程当作被测模型的评测输入。[Paper: Section III-D.2; Figure 4]

**人工步骤：** 专家先判真假，只审核自己正确识别的图像；补充明显遗漏，删除感知冲突，减少并非假图特有的非稳健描述。每张假图至少四条线索。主文未充分交代专家人数、独立复标比例、一致性及所有难例的处理细节。[Paper: Section III-D.2; Figure 5]

**资源状态：** [External] 作者仓库当前公开查询和评测代码，并说明带标签的答案不公开，评测需向作者提交响应。仓库同时给出代码 MIT 标识与数据非商业、训练用途限制说明，不能把代码许可直接扩展成全部图像及标注的训练许可。[作者仓库](https://github.com/Yixuanli423/FakeBench)。本次未下载基准数据、联系作者或纳入训练。

## 08 核心模块拆解

| 模块 | 功能及必要性 | 输入 → 输出 | 支持证据 | 已测或预期的移除影响 |
|---|---|---|---|---|
| 多来源图像池 | 覆盖生成器和内容差异 | 10 类生成器、真实数据 → 6,000 图 | Table II; Figure 2 | 无单独移除消融；减少覆盖是设计上的预期 |
| 14 类分类体系 | 规定描述什么线索 | 可见属性 → 低/中/高层标准 | Figure 3 | 直觉选项仅占 0.42% 选择；不是严格分类体系消融 |
| FakeClass | 直接检测 | 图像、闭式问题 → 真假答案 | Table V | 不提供解释证据 |
| 人机协作参考线索 | 形成描述参考 | GPT-4V 初稿、人类修订 → golden clues | Figure 5 | 未单独报告纯机器、纯人工与混合参考的一致性对照 |
| FakeClue 双提示 | 区分给定标签后的解释与自主判断 | 同一生成图、两类提示 → 长描述/结论 | Tables VI–VII | 有任务对照，但信息条件不同 |
| FakeQA | 测具体线索能力 | 每类问题 → 独立上下文下的回答 | Table VIII | 不是新增独立图像群体 |
| 多指标评分 | 综合参考相似度和内容评价 | 输出、参考 → 文本指标和三维评分 | Section IV-A.2; Equation 1 | 5 次评分平均抑制随机波动，未消除系统性偏好 |

14 类线索：[Paper: Section III-C]

| 层级 | 维度 |
|---|---|
| 低层 | texture、edge、clarity、distortion、overall hue |
| 中层 | light & shadow、shape、content deficiency、symmetry、reflection |
| 高层 | layout、perspective、theme、irreality |

[Analysis] 这些是人类可见线索的组织方式，不是每项线索都能独立证明伪造。例如模糊、畸变或不常见场景也可能来自真实拍摄、艺术风格或后处理。

## 09 关键公式与符号

**Equation 1，重复评分：** 对完整性、精确性和相关性分别打 0/1/2 分，重复五轮，再求平均：

\[
S_k=\frac{1}{5}\sum_{i=1}^{5}s_{k,i},\qquad k\in\{C,P,R\}.
\]

这是对原式的等价符号整理。完整性关注参考线索覆盖，精确性惩罚与参考冲突的内容，相关性关注是否谈论真实性。之后将 GPT 分数归一化，并与 BLEU-1/2、ROUGE-L、句相似度等自动指标的平均汇总为 Avr.。[Paper: Section IV-A.2; Equation 1]

[Analysis] Avr. 是复合描述评分，不是“每个主张真实”的概率，也不是传统分类准确率。参考中未列出的有效证据、不同表达风格和遗漏的参考错误都可能影响它。

**Equation 2，假图为正类的分类指标：**

\[
Precision=\frac{TP}{TP+FP},\qquad Recall=\frac{TP}{TP+FN}.
\]

提高 Precision 表示减少把真实图判为假；提高 Recall 表示减少漏掉假图。论文指出部分模型会给出既非真假也不相关的回答，但正文未充分列出这类无效回答如何同时进入 ACC、Precision 和 Recall 的分母。[Paper: Section IV-D; Equation 2]

**解释性指标定义，非原文新增编号：** 对类不平衡的外部数据，balanced accuracy 可写成真假两类召回的平均。不要把 BLEU、GPT 三维评分或 Avr. 与 bACC 混称为准确率。[Paper: Section V-C; Table XI]

## 10 实验设计与证据链

### 数据规模和采样

[Paper] 3,000 张假图来自十类生成器，各 300 张：ProGAN、StyleGANs、CogView2、FuseDream、VQDM、Glide、Stable Diffusion、DALL·E2、DALL·E3、Midjourney。真实图 3,000 张来自 ImageNet 和 DIV2K。130 张 DALL·E3 图源于 Reddit，可能带后处理。[Paper: Table II; Section III-B]

| 组成 | 图像范围 | 查询数 | 要测的能力 |
|---|---|---:|---|
| FakeClass | 3,000 真 + 3,000 假 | 6,000 | 闭式真假判别 |
| FakeClue | 同 3,000 张假图 | 6,000，两个提示模式 | 解释、推理 |
| FakeQA | 同一假图池 | 约 42,000 | 14 类细粒度问答 |
| 总量 | 6,000 张图 | 54,000 | 不是 54,000 个独立样本 |

[Paper: Section III-D; Table III]

假图按可见难度分为 Easy/Medium/Hard＝1,241/969/790。FakeClue 平均回答 127 词。Table III 另写 `Images with Captions = 6,000`，而正文明确长解释只覆盖假图；这一计数不能直接读成“6,000 张独立图都有人审取证解释”，需数据字典进一步澄清。[Paper: Table III; Section III-D.2]

人类研究使用 200 真图 + 200 假图，34 位参与者，17 位有经验、17 位无经验，不限时。模型的全量 6,000 图成绩与人类 400 图成绩采样范围不同，因此“超过人类平均”只能按论文的各自评测设置理解。[Paper: Section III-C; Table V]

14 个 LMM 以原始配置、greedy decoding、零样本方式评测，不使用 FakeBench 微调；专用模型沿用各自原论文训练设置，训练来源并不统一。主文未给模型间统一计算预算或多次独立推理区间。[Paper: Section IV-A.1; Table IV]

### 主张—证据矩阵

| 实验 | 比较与条件 | 原文结果 | 支持结论 | 不支持的更强说法 | 来源 |
|---|---|---|---|---|---|
| 人类检测 | 34 人，400 张图 | 平均 74.51%，最高 87.50% | 人类表现有显著个体差异 | 已建立全量同图同条件的人机比较 | [Paper: Figure 3] |
| 直接真假检测 | 14 LMM 和专用方法 | GPT-4V Overall 78.03%；mPLUG-Owl2 71.78%；AntifakePrompt 79.14% | 通用模型有一定检测能力，但并非全面优于专用方法 | 所有开源/商业模型均可靠 | [Paper: Table V] |
| 给定标签后的解释 | 仅假图，告知其为假 | GPT-4V Avr. 0.573；InstructBLIP 0.541 | 能生成较贴近参考的解释 | 模型自主判断或证据忠实性已经可靠 | [Paper: Table VI] |
| 未给标签的推理 | 仅假图，先分析后判断 | InstructBLIP 0.464；GPT-4V 0.460 | 提示条件改变会明显改变描述表现 | 0.004 差距有统计显著性 | [Paper: Table VII] |
| 细粒度分析 | 独立上下文询问具体维度 | GPT-4V Avr. 0.477，表中最高 | 细粒度线索分析仍不强 | 每项事实正确率为 47.7% | [Paper: Table VIII] |
| 低层视觉微调关联 | Q-Instruct 对比其基础模型 mPLUG-Owl2 | Overall 71.78% → 63.73%，降 8.05 个百分点；解释和细粒度分数提高 | 能力存在权衡 | 低层微调必然导致检测退化 | [Paper: Section IV-C; Tables V–VIII] |
| 显式 CoT | 同模型直接回答/先分析后判断 | GPT-4V 78.03% → 74.71%，降 3.32 个百分点 | 长分析在该设置未带来普遍提升 | 取证任务中任何推理方法都无效 | [Paper: Table IX] |
| 错误前提提示 | 真图说成假、假图说成真 | 明确拒绝错误前提：GPT-4V 4.00%，另两模型 0.00% | 顺从错误前提是实际失败方式 | 未拒绝就等于每条说明都必然为假 | [Paper: Table X; Section V-B] |
| 外部检测 | WildRF、Synthbuster、SynthWildX | GPT-4V bACC 62.51%/61.67%/68.12% | 本数据集高分不等于野外可靠 | 解释/推理也已跨域验证 | [Paper: Table XI] |

另有跨任务模型排名相关：最高 SRCC 为推理与细粒度分析之间 0.54，解释与推理为 0.046；仅涉及约 14 个模型的排名，不能直接推出同一模型在单张图上的错误机制。[Paper: Section IV-B.4]

### 主图表清单

| 项目 | 论证作用 |
|---|---|
| Figure 1 | 四项研究问题及示例；应以正文任务定义确定解释/推理的输入差别 |
| Figure 2 | 生成器和图像内容覆盖 |
| Figure 3 | 人类检测分布、14 类线索及选择频率 |
| Figure 4 | 四种提示模式；区分参考构建与性能评测提示 |
| Figure 5 | GPT-4V 与人类专家协作形成参考线索 |
| Figure 6 | 描述长度、词频和词云；描述资源特征，不能证明标注正确 |
| Figure 7 | 同图不同提示得到相反判断的案例 |
| Figure 8 | JPEG 压缩和缩放下的检测鲁棒性 |
| Table I | 与既有基准的能力覆盖比较，属于作者定位 |
| Table II | 十类生成器、来源与各 300 张的样本量 |
| Table III | 图像、查询、长度和难度统计 |
| Table IV | 被测开源 LMM 的视觉/语言骨干和对齐方式 |
| Table V | 直接检测，真假子集、问题形式与生成器差异 |
| Table VI / VII | 给定标签后的解释 / 未给标签的推理 |
| Table VIII | 细粒度线索问答 |
| Table IX | CoT 前后 ACC、Precision、Recall |
| Table X | 错误前提拒绝率 |
| Table XI | 外部数据检测泛化 |

[Paper: Figures 1–8; Tables I–XI]

## 11 如何正确理解结论

**第一，参考解释不是内部决策过程。** 正式版明确将其作为人类可理解的事后说明目标。与参考相似，只能支持相应描述任务表现；无法直接证明模型确实依据这些线索作决定。[Paper: Section III-A; Section IV-D.2]

**第二，解释任务给了标签。** 它比自主推理多了一项正确答案信息。两任务成绩差异不能只归因于“推理更复杂”，也可能来自前提锚定、回答格式或模型拒答策略。[Analysis; basis: Section III-D.2]

**第三，假图解释数据不能直接回答真实图误伤。** FakeClue 不收集真实图解释，所以高解释分数不说明模型能恰当地保留正确内容或拒绝无依据的纠错。[Paper: Section III-D.2]

**第四，CoT 失败是具体模型与提示条件下的结果。** Table IX 包括提升例子，如 Claude3 Sonnet 55.12% → 55.95%；Otter 50.15% → 50.40%。因此应说“多数设置未改善”，不能说所有模型都下降。[Paper: Table IX]

**第五，描述中的原因只是候选解释。** 取证概念不足、视觉线索映射错误、指令遵从不足和潜在捷径，没有全部通过独立干预隔离。[Paper: Section IV-D.2]

有边界的结论是：**该基准直接支持把检测、解释、推理和细粒度分析分开评测，并提示错误前提与能力权衡需要专门检查；它没有验证一个可训练取证 Monitor 或纠错闭环。**

## 12 作者明确承认的局限

论文没有独立的 Limitations 节，但有明确承认的边界与未来方向：

| 局限 | 具体表现 | 作者提出的方向 | 来源 |
|---|---|---|---|
| 解释不等于实际内部推理 | 生成叙述可能与内部决策机制不一致 | 研究模型依赖隐式痕迹还是显式语义线索 | [Paper: Section III-A; Section IV-D.2] |
| 对错误前提缺乏可靠反驳 | 容易顺从并生成虚构线索 | 加强辩证推理机制 | [Paper: Section V-B] |
| 真实图像变换及外域泛化仍有限 | 压缩、缩放和外部数据上性能不稳 | 改善真实环境下泛化 | [Paper: Sections V-A, V-C] |
| 当前主要围绕人可见语义 | 未融合更细微的统计取证痕迹 | 融合 Fourier、重采样等信号与可见线索 | [Paper: Section VI Conclusion] |

作者还说明因商业模型成本仅选择 GPT-4V 和 GeminiPro 代表商业模型做外部数据评测；这是评测覆盖约束，不把它扩大为全部商业模型的结论。[Paper: Section V-C]

## 13 批判性分析

| [Analysis] 观察 | 问题或替代解释 | 影响 | 如何检验 | 依据 |
|---|---|---|---|---|
| GPT-4V 起草参考，GPT-4 评分 | 同系列模型可能偏好相似措辞和线索 | 模型排名可能部分受参考风格影响 | 盲态独立人审、跨系列评分、控制字数；比较排名稳定性 | Figures 4–5; Section IV-A.2 |
| 专家仅修订自己识别正确的图 | 难图可能需要更强审核；主文未交代完整流转 | 参考质量可能随难度变化 | 统计每图独立复审次数、未识别图处理与难度分层一致性 | Section III-D.2 |
| 每假图至少四条线索 | 强制多条可能促使过度寻找瑕疵 | 参考可能奖励长而牵强的说明 | 不限最少线索，与逐条可靠性和“无可见决定线索”选项对照 | Section III-D.2 |
| FakeQA 与 FakeClue 共用图和参考 | 54k 查询不是 54k 独立观察 | 误差区间和数据划分可能被夸大 | 以图像/来源组聚合统计，禁止同图跨训练测试 | Section III-D; Table III |
| FakeClue 仅假图 | 缺少无错、真实与不确定控制 | 不适合作完整纠错能力认证 | 另设已授权真实图和无依据修改对照，测误伤 | Section III-D.2 |
| 词相似和相对参考评分 | 合理新证据可能被罚，错误参考可能被模仿 | 高 Avr. 不一定高事实精确性 | 主张级视觉核验、支持关系和引用一致性分开计量 | Section IV-A.2 |
| 五次重复同一评分器 | 降低随机性，不能去除系统偏差 | 不应据此宣称评价已无偏 | 报告跨评分器及独立人工一致性 | Equation 1 |
| 人类和模型测试样本范围不同 | 样本难度差异影响比较 | 78.03% 与 74.51% 不构成严格同图优势 | 在同一 400 图上按相同条件重报配对成绩 | Section III-C; Table V |
| 已有模型的横向比较不等于受控消融 | 架构、训练、对齐和输出习惯不同 | 微调数据“导致”退化的因果证据有限 | 同基座、同数据预算、只改训练内容 | Section IV-C |

**原文内部需要特别保留的核对项：**

- [Paper] Section IV-D.1 将 Qwen-VL 的 63.56% 降幅写在 fake images 上；Table IX 显示假图 28.57% → 5.93%，降 **22.64 个百分点**，真实图 84.27% → 20.70%，降 **63.56 个百分点**。本笔记以表格区分两项，不默默复制正文错误。[Paper: Section IV-D.1; Table IX]
- [Analysis] Table V 表注将 `Real` 列称为 precision，正文和 Table IX 又按真实图 ACC 使用。提取结果时应保留原列名并核对评测代码，不能仅据表注重建混淆矩阵。[Paper: Table V; Table IX]
- [Analysis] Table III 的 caption 图像计数与 FakeClue 仅假图的说明存在口径歧义，已在第 10 节记录。论文关于“其余 12 个模型在 [0.357, 0) 范围”的区间写法也明显不规范；本笔记用表中数值，不据该区间推断负分。[Paper: Table III; Section IV-B.2; Table VII]

## 14 学到的可迁移知识

以下为 **Agent-derived knowledge candidates**。

- [Analysis] 提示是否泄露真假标签，是实验条件的一部分，必须和结果一起报告。[Paper: Figure 4]
- [Analysis] 人类可理解的线索可以作解释目标，但不应自动升格为模型决策的真实因果证据。[Paper: Section III-A]
- [Analysis] 正确标签下的好解释，与错误标签下能否反驳，是两个独立能力。[Paper: Tables VI, X]
- [Analysis] 微调收益要与旧能力和误伤一起检查；专门训练某种描述能力可能改变判别边界。[Paper: Section IV-C]
- [Analysis] 评价单位必须回到图像或来源组，多问题不能凭空增加独立样本量。[Paper: Table III]

## 15 与现有知识和当前项目的联系

**与 EviGraph。** [Analysis] FakeBench 指出仅有可见线索和长叙述仍可能失效，并在结论中提出融合不可见统计取证信号；EviGraph 的工具和区域槽提供一种具体相关路线。但没有跨论文受控实验证明后者修复了前者的错误前提顺从、真实图误伤或内部忠实性问题。[Paper: Section VI; companion EviGraph: Sections 3.2–3.4]

**与当前 Monitor。** [Analysis] 当前[项目主方案](D:/Codex/AIGC/docs/Actor_Monitor_MVP_Protocol.md)要求核对证据是否被正确解释与使用。FakeBench 的主要启示是评测拆分：格式合法、引用存在、内容正确、结论受支持、反馈有效均应分开。它没有工具轨迹、工具契约、局部修订及 STOP 监督，不能直接冒充完整 Monitor 数据。

**与数据选择。** [External] 作者明确不公开带标签答案以控制泄漏；仓库对训练用途另有限制，故“论文有 54k 问答”不能推成“现有 54k 条可自由下载训练的样本”。[作者仓库](https://github.com/Yixuanli423/FakeBench)。本次只作阅读和方法讨论。

## 16 研究设想

以下为 **Agent-derived research candidates**，只提出可检验方向，不执行模型、数据采集或实验。创新状态均为 **unverified**。

### 候选一：错误前提下的证据独立性评测

- **来源观察：** 提供错误真假前提时，多数输出顺从前提。[Paper: Table X]
- **核心假设：** 固定 Actor 后，要求 Monitor 先核证据支持关系、再决定是否接受 Actor 判断，可减少方向诱导；只要求“解释为何错误”会放大诱导。
- **相对变化：** 改监督输入和评价，保留相同图像、工具结果和 Actor 输出。
- **初始方法：** 对相同材料设置中性、正确前提、错误前提三种审核指令，明确允许保留原结论或标记证据不足。
- **如何验证：** 在另行批准且真假平衡的来源组上配对测试，固定调用预算，测错误前提拒绝率、证据事实精确率、正确内容保留和最终判断；若只是增加拒答而未改善支持关系，则假设不获支持。
- **可能失败：** Monitor 与 Actor 共享偏差；审核提示变得更保守；工具本身错误但被当作事实。
- **创新状态：** unverified；错误前提测试已有本文先例，不将其本身当作新方法。

### 候选二：以正确内容保留约束纠错，而非只奖励参考匹配

- **来源观察：** FakeClue 只覆盖假图，描述能力与判别能力可出现权衡。[Paper: Section III-D.2; Section IV-C]
- **核心假设：** 加入严格同格式的有错/无错配对监督，并对无依据修改计代价，可改善实际反馈效用；单纯提高参考修正匹配可能损坏原本正确内容。
- **相对变化：** 调整监督与指标，保留 Actor 和原始证据，不把现成 FakeBench 数据自动分配为训练材料。
- **初始方法：** 先对已有、已授权反馈记录作方案设计，分别标记应改片段、必须保留内容和证据不足项；避免样本格式泄露标签。
- **如何验证：** 后续另定样本与预算，以现有 Monitor 为对照，比较同源有错/无错对的联合正确、误改、旧能力保持和反馈采纳结果；若纠错提高但无错误改恶化，则不能认定整体收益。
- **可能失败：** 模型学到一律不改的策略；配对模板泄露标签；参考修正不唯一或本身错误。
- **创新状态：** unverified；与仓库既有无错监督和反馈控制探索重合，先审已有结果，不重复启动训练。
