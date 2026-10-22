# 公开核验基线的适配核查

2026-10-10。回应用户“其他论文方法是否试过”：此前借鉴了细粒度核验、多阶段来源/最终聚合、结构程序核验；最新v3试了统一中文输出契约。**没有直接运行MiniCheck官方模型、RefChecker完整作者基线或Distilling Step-by-Step原训练器。** 论文方法未被完整复现，不能依据本项目失败宣称它们无效。此页只读适配核查，权重下载/新推理/新训练均0。

## 现成资源与限制

| 资源与已核原始来源 | 已核事实 | 项目用途及差异 |
|---|---|---|
| [MiniCheck官方模型](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large)、[文件列表](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large/tree/main) | 770M，英文，文档—句子支持二分类，模型卡MIT；主要权重约3.13GB。卡述训练包括21K ANLI和14K合成材料。 | 是真正可运行的现成核验基线，但不能把0直接映射成项目未知/未返回/反证。中文效果需要单独验证；不把模型卡英文测试收益外推中文工具归因。 |
| [MiniCheck inference.py](https://github.com/Liyan06/MiniCheck/blob/main/minicheck/inference.py)、[minicheck.py](https://github.com/Liyan06/MiniCheck/blob/main/minicheck/minicheck.py)、[LICENSE](https://github.com/Liyan06/MiniCheck/blob/main/LICENSE) | 作者代码Apache-2.0；Flan默认最大2048、500词分块，NLTK分句；tokenizer使用truncation，分块支持概率取最大并按0.5二分。 | 必须记录是否截掉决定性依据；任一块支持不能证明全称断言/多工具冲突被覆盖。不能直接运行main安装命令并让依赖改动Actor环境。正式使用前固定commit和权重revision/hash。 |
| [C2D/D2C公开数据卡](https://huggingface.co/datasets/lytang/C2D-and-D2C-MiniCheck) | 英文、MIT，claim/doc/二分类label；官方提供两类决定性事实对照材料。 | 可吸取配对设计；不是本项目中文工具归因或STOP数据。未下载训练文件、未混入本项目SFT，也未将标签自动映射为未知/未返回。 |
| [多语NLI模型卡](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli)、[文件列表](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli/tree/main) | MNLI/XNLI训练，中文在已评语言内；entailment/neutral/contradiction三类，MIT，safetensors约558MB，模型卡提示不支持FP16。 | 更轻的中文语义基线候选；可先评“被选引用是否足够支持当前断言”。NLI neutral仍不等于项目未知，选中叶子也不能证明完整来源缺失。应使用FP32及实际config标签顺序，长度先检查。 |

这是实现/模型卡核查，不是公共基准复现、独立效能证明或对英文模型的否定。上述main链接可变，下一运行方案须固定版本。未下载权重/数据，未执行外部代码、未向外部推理API发送项目材料。

## 建议的可审下一步

先补一个**公开模型的引用充分性基线**，再决定下一轮SFT。建议先准备小型多语NLI候选材料：仅复用v3已审十三条的当前断言、模型实际选中叶子与原有预审引用；分开支持声明的依据充分性与完整来源的缺失判断。原始返回、目标及raw都保留。它只能帮助定位编号/信号/计数字段是否支持属性，不能代替完整Monitor或用程序修复其标签。

CPU材料需要逐条预审“所选证据集合能支持哪些属性”，不能从v3状态匹配自动生成NLI真值。支持正例必须保留，缺列表未知与物体未返回仍按用户确认口径在完整来源层评价。若此小型模型也错误，不立即蒸馏；若有效，再讨论是仅作评价器、辅助证据选择还是训练教师，不能自动升级为gold。

预计小模型可在现有隔离环境以CPU运行，先核依赖/内存及长度，无卡也可准备；下载限选单份safetensors及tokenizer/config，约0.6GB，不取ONNX/重复bin。具体下载时间取决于已核网络速度，不能先保证时长。若改用GPU，应另告知预计2–5分钟并重新核资源。MiniCheck英文模型/翻译配对与新训练数据属于另一设计，不与多语NLI同时上马。

当前仅提出候选，尚未冻结运行包。按AGENTS第1条，选择新基线及其评价范围会影响实验结论，需要在材料具体化后向用户说明事实、范围、建议和费用，再确认执行。当前v3复审已完成、adapter不采用，GPU已释放；目标继续active。
