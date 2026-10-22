# Monitor 公开训练数据检索与筛选

日期：2026-10-16。范围：证据忠实性、主张与依据对齐、视觉评价与批评、代理轨迹归因。用户指定 anysearch；使用 academic.search / academic.preprint 与一般检索定位，再核对作者论文、仓库、Hugging Face 数据卡及公开文件元数据。非穷尽系统综述。仅检索与有限预览，未下载数据包、纳入训练或调用模型。

## 结论

有实际公开、规模足够开展通用能力训练的相关数据；未找到一套同时覆盖本项目取证工具契约、视觉证据、轨迹审核、中文修正反馈与停止充分性的即用数据。推荐将通用证据核查/视觉批评与项目领域适配分开设计，不能把公开数据数量直接当作本项目有效监督数。

## 优先候选

| 数据 | 已核实规模及发布 | 内容与用途 | 缺口、许可与决定 |
|---|---|---|---|
| [RAGTruth](https://github.com/ParticleMedia/RAGTruth) / [论文](https://aclanthology.org/2024.acl-long.585/) | 约18,000条回答，总规模含训练与测试；作者发布source_info.jsonl、response.jsonl及split | 人工标注无依据/冲突文本跨度；有原始证据，含结构化JSON到文本任务。优先用于忠实性识别和错误定位 | 不自带本项目证据ID、完整修正或工具行动；不能将错误跨度自动当成精确来源归因。仓库MIT，底层源数据另核。每source_id多模型回答须同组；特别处理implicit_true、null、质量问题 |
| [RAGBench](https://huggingface.co/datasets/galileo-ai/ragbench) / [论文](https://arxiv.org/html/2407.11005v2) | 宣称约100k；当前数据卡12子集元数据求和95,381：train73,286、validation10,293、test11,802 | documents、response、逐句fully_supported、supporting_sentence_keys、explanation；很接近“选证据＋判断是否支持” | GPT-4自动标注，不能称全人工gold；非取证轨迹，不保证区分冲突与缺信息。卡标CC BY4.0，各上游来源另核。论文指出不同子集错误比例不平衡；训练取train，其他保留 |
| [Critic-V / critique-VQA](https://huggingface.co/datasets/huaXiaKyrie/critique-VQA) / [仓库](https://github.com/kyrieLei/Critic-V) / [论文](https://arxiv.org/html/2411.18203v2) | viewer显示约29k；datasets-server size实查29,012行，仅train，含image、conversation、chosen、rejected | 同一图与候选回答对应较好/较差批评；适合视觉批评偏好训练，也可筛chosen作SFT候选 | 偏好对不是29k独立图片；预览有同图同问重复及明显注入错误，须按原图/题目归组，检查自然性和正确放行覆盖。偏好不代表Actor修复效用。卡MIT；英文，与中文接口有迁移差异 |
| [LLaVA-Critic-113k](https://huggingface.co/datasets/lmms-lab/llava-critic-113k) / [作者项目](https://llava-vl.github.io/blog/2024-10-03-llava-critic/) | 约46k图；当前卡pointwise72,782、pairwise40,154，共112,936条train | 图片＋问题＋候选回答→分数/偏好与理由；GPT-4o生成评判。适合视觉证据评价和说明理由的通用训练 | 不是逐工具来源核查，也不是保证可执行的修正反馈；部分pointwise含参考答案，不能给部署输入制造参考依赖。卡Apache2.0，原图来源许可另核，防与项目测试重合 |
| [AEGIS](https://huggingface.co/datasets/Fancylalala/AEGIS) / [作者仓库](https://github.com/kfq20/AEGIS) / [论文](https://arxiv.org/html/2509.14295v6) | 论文9,533轨迹为总口径，不当训练条数；HF实查Aegis-Training/train.jsonl和val.jsonl存在，另有Aegis-Bench | 在成功多代理轨迹注入错误，标责任代理/错误类型；含提前终止、不正确验证等。适合轨迹错误归因的补充 | 与单Actor取证不同，无保证完整纠错反馈。首记录有限预览含id、metadata、input、output、ground_truth；需筛掉与监控无关类别，GT/注入信息不进入学生输入。卡MIT；实际条数、重复及来源隔离未全包核验 |

上述许可为发布页标注，不能自动替代底层图片/文本源的许可；这不是因许可不明而暂停本次检索，后续实际纳入时逐来源登记。

## 不应误当现成训练集

- [TRAIL](https://huggingface.co/datasets/PatronusAI/TRAIL)：148轨迹、841错误。卡虽标MIT，Out-of-Scope Use另明确要求仅评价，不训练拟自动化人工评价的系统。对本Monitor用途从训练候选排除，可保留评测候选。
- [Agent Error Dataset (AED)](https://arxiv.org/html/2609.40111v1)：报告50,228错误—诊断对，但正文/附录仍写计划公开，未核实实际可下载官方数据与数据许可。不列为现成可用；也不能将论文总集合、诊断实验子集与具执行验证的修复子集混算。
- [FakeClue](https://huggingface.co/datasets/lingcco/FakeClue) / [作者仓库](https://github.com/opendatalab/FakeVLM)：超100k图，有伪造痕迹自然语言说明，卡Apache2.0。适合视觉伪迹理解；原任务是图像检测/解释，不审核Actor工具使用。若直接以real/fake为Monitor主要目标，会偏离当前研究。作为领域素材候选，不是主监督。
- [AgenTracer](https://arxiv.org/html/2509.03312v1)：论文TracerTraj-2.5K方向相关；本次尚未核实官方数据包与数据许可，不计入已经可用数量。数学PRM、普通工具调用成功轨迹同理，不能仅凭规模替代核查/反馈监督。

## 对项目的建议（未冻结、未执行）

1. 优先用RAGTruth与RAGBench设计“依据是否支持回答”的通用监督，保留各自任务语义，不强行制造原数据没有的精确引用、三分类或修复gold。
2. Monitor接图像时，筛选LLaVA-Critic作视觉评价候选，Critic-V作自然语言批评/偏好候选；图像必须实际输入。可分任务混合SFT，不必为迁就旧五字段强行转换全部数据，也不自动连续训练多个adapter。
3. AEGIS可补轨迹归因；项目自己的工具定义、非方向性、计数/全称、证据冲突与STOP规则仍需领域数据。先复用已授权开发来源，训练/验证/测试按来源分开；44保留组用途保持待定。
4. 训练预算按筛选后的来源数、监督tokens、长度、错误类型和正确放行覆盖确定。先做数据审阅与可训练格式设计，再冻结规模；没有依据承诺某个万条数量一定有效。数据集间源文档/题目可能重复，不能靠随机按行划分宣称独立泛化。
5. 现有数据大多英文，项目输出中文；中文监督如何提供需要明确。不能把翻译及新增教师纠错当作本次已批准API任务。

## 核验范围与留存

- 已读作者数据格式/许可/划分说明，查看公开示例与元数据。RAGBench数量由卡内split计数相加；Critic-V为公开size API；未重算全数据包。
- AEGIS只预览train文件前最多65,536字节并解析首记录，未执行仓库生成/训练脚本。临时网络/审批服务中断经原流程重试解决；anysearch页面提取重试后成功。
- 未下载整包或图像、未安装依赖、未训练/推理/调用教师API、未访问服务器、未读取GT/44保留来源、未重跑FULL20；无任何哈希核验。
- 后续优先项是数据筛选与训练设计讨论；本记录不修改冻结实验或自动恢复goal执行。
