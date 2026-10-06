# MLLM 加工具：公开工作复用评审

**检索与核对日期：2026-09-28**  
**用途：三动作 pilot 后的研究路线证据；推荐的路线 C + 路线 A 实现已于 2026-09-28 纳入 [MVP v2 主方案](Actor_Monitor_MVP_Protocol.md)**

## 1. 本次调研回答什么

本次只回答三个问题：

1. 三动作 pilot 中工具带来净误伤，更像是工具本身无效，还是模型没有学会使用工具？
2. 近期是否已有可直接复用的模型、工具、训练框架或评测集？
3. 哪些已有工作已经覆盖了“MLLM 动态选择工具/干预”的核心主张，从而影响本项目的创新定位？

调研优先检查论文原文、作者仓库、官方模型和数据页面。检索主题包括 `agentic AI-generated image detection`、`MLLM tool image forensics`、`multimodal tool use benchmark`、`forensic MLLM` 和 `AI-generated image detector calibration`。可运行性按 2026-09-28 的公开状态判断；论文报告的性能没有在本项目环境中复验。

## 2. 结论摘要

### 2.1 pilot 不能推出“取证工具无效”

现有证据更支持下面的诊断：

- 当前三个“工具”是 9 项手工统计读数，没有经过跨生成器验证，也没有校准成可比较的置信度；它们更接近低层特征，而不是已经证明有辨别力的取证专家。
- Qwen3-VL-8B 只通过提示词读取这些数值，没有接受工具调用、证据仲裁或取证语义方面的训练。模型既出现区间语义误读，也出现算术和引用错误。
- 输入中没有明确描述每个工具的适用范围、失效条件、阈值语义和冲突处理方式。因此模型容易把“有数字”误当成“有证据”。
- 本批结果中的错误方向是多张假图被改判为 `real`。这说明工具输入改变了模型的信任分配，但没有提供可靠的判别增益。

因此，现阶段最准确的说法是：**未经验证的原始特征，加上未经工具使用训练或校准的通用 MLLM，组合后产生了负收益。** 不能单独归因于工具差，也不能单独归因于未微调。

### 2.2 近期文献给出三条一致证据

1. [ToolVQA（ICCV 2025）](https://openaccess.thecvf.com/content/ICCV2025/html/Yin_ToolVQA_A_Dataset_for_Multi-step_Reasoning_VQA_with_External_Tools_ICCV_2025_paper.html) 报告：未经相应训练的 VLM 加工具可能低于只用 VLM；微调后，工具调用与结果整合才转为正收益。这说明“把工具结果塞进提示词”不是可靠的默认方案。
2. [EvoGuard（2026）](https://arxiv.org/abs/2603.17343) 在 AIGI 检测中发现，调用全部检测器低于按样本选择和编排检测器；去掉工具能力画像后性能明显下降。这说明工具数量本身不是关键，适用范围和选择策略更重要。
3. [Dissecting Agentic Forensics（2026）](https://arxiv.org/abs/2609.24359) 显示，朴素融合多个检测器会严重损害真实图像特异度；为每个检测器设置范围审计、证据质量判断和冲突仲裁后才改善。这与 pilot 中缺少工具可信度管理的问题直接对应。

## 3. 与项目最相关的工作

### 3.1 动态工具编排与取证 Agent

| 工作 | 核心方法 | 公开资产状态 | 对本项目的直接价值 | 主要边界 |
|---|---|---|---|---|
| [EvoGuard](https://arxiv.org/abs/2603.17343) | Qwen3-VL Agent 按图像动态选择冻结的 Effort、FakeVLM、MIRROR、AIDE，结合工具能力画像、多轮反思和停止策略；只用二分类标签进行 GRPO | 论文称录用后公开源码；截至检索日未找到官方代码 | 与本项目最接近的直接竞品；工具画像、选择而非全调用、冻结专家和只训练策略都可借鉴 | 公开实现暂不可用；其“动态工具选择”已覆盖一部分潜在创新点 |
| [Dissecting Agentic Forensics](https://arxiv.org/abs/2609.24359) | 训练外框架；每个专家先做范围、信号质量和上下文审计，再由冲突感知 Judge 裁决 | 未找到官方仓库；论文附录提供较完整提示 | 可直接借鉴 tool card、弃权、逐工具审计和冲突仲裁；适合先做无需训练的最小验证 | 主要面向开放世界篡改，和完整生成图检测不完全相同 |
| [ForgeryVCR](https://arxiv.org/abs/2602.14098) | Qwen3-VL 学习调用 ELA、FFT、噪声图和局部放大；用增益筛选 SFT 轨迹和工具效用奖励训练 | [代码](https://github.com/youqiwong/ForgeryVCR)与[合并权重](https://huggingface.co/youqiwong/ForgeryVCR)已发布，仓库为 Apache-2.0；训练代码尚未完整发布 | 当前最可直接复用的 Qwen3-VL 工具调用循环、轨迹格式和推理框架 | 主要做图像篡改检测与定位；ELA 等工具对完整扩散生成图未必合适；NPP 组件另有用途限制 |
| [ForenAgent](https://arxiv.org/abs/2512.16300) | MLLM 在循环中生成、执行和修正低层 Python 取证工具，结合冷启动和强化微调 | [仓库](https://github.com/zfr00/ForenAgent)已公开 12 个低层工具；完整 Agent、训练代码和 FABench 尚未全部公开 | 可直接复用 DCT、FFT、SRM、JPEG ghost、重采样等工具实现，避免重写 | 当前公开部分主要是工具箱；任务偏通用篡改，不能直接证明 AIGI 有效 |
| [ForeAgent](https://arxiv.org/abs/2606.26552) | 语义、空间、频率多视图感知，利用带真值的反思和双专家筛选形成高质量轨迹，再微调 Agent | 未找到官方代码 | 说明训练数据质量和反思轨迹筛选是工具融合成功的重要环节 | 暂不能直接运行，论文指标待独立复验 |
| [AgentFoX](https://arxiv.org/abs/2603.23115) | 根据语义场景和专家画像融合 AIGI 检测器，并生成可解释报告 | [仓库](https://github.com/suncore946/AgentFoX)为 Apache-2.0，公开最小推理骨架 | 可复用报告生成和 OpenAI-compatible/Ollama 接口 | 论文中的专家调用、校准和聚类核心目前在公开版中停用 |
| [AIFo](https://arxiv.org/abs/2511.00181) | 多 Agent 组合反向搜图、元数据、分类器和 VLM，通过辩论与记忆给出结论 | 未找到官方代码 | 适合真实网络场景的来源核验思路 | 反向搜图和元数据会改变受控检测任务，可能引入来源泄漏，不宜作为主实验输入 |

### 3.2 可作为强工具或 Actor 的取证模型

| 工作 | 方法与公开资产 | 可复用方式 | 注意事项 |
|---|---|---|---|
| [FSD / Forensic Self-Descriptions（CVPR 2025）](https://github.com/ductai199x/Forensic-Self-Descriptions-CVPR25) | 只用真实图训练的法证微结构模型；公开代码与约 55 MB 检测权重，输出连续 z-score | 作为轻量冻结专家和校准输入；与视觉/噪声混合专家形成互补证据 | CC BY-NC-SA 4.0；论文涉及 COCO/ImageNet/MIDB，发布权重的具体真实训练子集未写清，确认性测试应避开这些真实来源 |
| [AIGI-Holmes（ICCV 2025）](https://openaccess.thecvf.com/content/ICCV2025/papers/Zhou_AIGI-Holmes_Towards_Explainable_and_Generalizable_AI-Generated_Image_Detection_via_Multimodal_ICCV_2025_paper.pdf) | LLaVA-1.6-Mistral-7B、CLIP 和 NPR 专家协作；三阶段训练并在解码时融合取证专家。公开[代码](https://github.com/wyczzy/AIGI-Holmes)、[模型](https://huggingface.co/zzy0123/AIGI-Holmes-Model)和[数据](https://huggingface.co/datasets/zzy0123/AIGI-Holmes-Dataset) | 作为冻结的取证 Actor 或一个强专家工具，与通用 Qwen3-VL 做对照 | 模型约 15 GB；仓库示例采用多卡配置，单张 4090 的实际显存和吞吐需另做小测；数据为非商业许可 |
| [FakeVLM（NeurIPS 2025）](https://arxiv.org/abs/2503.14905) | 取证 VLM 与细粒度伪造线索数据；公开[代码](https://github.com/opendatalab/FakeVLM)、[7B 权重](https://huggingface.co/lingcco/fakeVLM)和 [FakeClue 数据](https://huggingface.co/datasets/lingcco/FakeClue) | 可作为冻结专家，输出标签和文本证据；FakeClue 可用于研究解释格式 | 数据页面标注 Apache-2.0；代码仓库和模型页未见清晰许可证，正式纳入前需要确认 |
| [CLASP / PATE-Forensics](https://arxiv.org/abs/2608.18573) | 将训练过的取证感知器产生的全局、块级和区域证据交给通用 MLLM 解释；公开[训练评测代码](https://github.com/yqli00000/CLASP)和检查点链接 | 最值得借鉴的结构：工具输出学习得到的证据图、局部区域和分数，MLLM 负责解释与裁决 | 数据未完整分发，仓库未见明确许可证；任务含检测与定位，生成器迁移仍明显 |
| [FakeScope](https://arxiv.org/abs/2503.24267) | 大规模取证指令与专家 LMM | 暂只适合作为方法参考 | [仓库](https://github.com/Yixuanli423/FakeScope)当前仍标注待更新，没有可用模型和数据流程 |
| [ForenX](https://arxiv.org/abs/2508.01402) | CLIP 特征经轻量取证投影器作为视觉提示注入 LLaVA，并加入辅助检测损失 | 支持“先训练感知器，再让 MLLM解释”的路线 | 未找到可直接复用的官方实现 |

### 3.3 支撑组件与评测

| 组件 | 用途 | 复用建议 |
|---|---|---|
| [AIGI Detector Calibration](https://arxiv.org/abs/2602.01973) / [代码](https://github.com/muliyangm/AIGI-Det-Calib) | 用少量目标域验证样本做冻结检测器的后验 logit 校正 | 可作为轻量基线，检查 pilot 的单边预测是否主要来自阈值与域偏移 |
| [Forensics-Bench（CVPR 2025）](https://github.com/Forensics-Bench/Forensics-Bench) | 63,292 道取证多选视觉问题，覆盖多种篡改和取证视角 | 用来诊断 Actor 是否理解取证证据；不替代本项目的 COCO/SDXL 二分类测试 |
| [AIGCDetectBenchmark](https://github.com/Ekko-zn/AIGCDetectBenchmark) | 多生成器 AIGI 检测基准与公开评测代码 | 用于补充跨生成器外测，避免只在 SDXL 上形成结论 |
| [Effort](https://github.com/YZY-stack/Effort-AIGI-Detection)、[AIDE](https://github.com/shilinyan99/AIDE)、[MIRROR](https://github.com/handsome-rich/MIRROR) | 已训练的 AIGI 检测器；也是 EvoGuard 工具池的重要组成 | 优先作为冻结工具候选，替代未经验证的 9 项原始读数；正式使用前逐项核对权重、许可证、输入预处理和训练集重叠 |

## 4. 哪些可以直接用，哪些还不能

### 4.1 当前可直接复用

1. **FSD 的公开检测器**：与当前 Python 3.12/PyTorch 2.12 环境兼容，检测权重约 55 MB，并直接输出适合校准的连续 z-score。
2. **AIDE 的公开代码与 checkpoint**：适合作为与 FSD 机制互补的冻结专家，但应使用隔离的 Python 3.10 环境。
3. **ForgeryVCR 的 Agent 循环与工具协议**：同为 Qwen3-VL 系列，可选择性借鉴工具消息和轨迹格式；本项目已有同前缀执行器，不需要整包引入其重依赖。
4. **Tool card、范围审计与弃权机制**：可按 Dissecting Agentic Forensics 的附录直接实现，无需先训练模型。
5. **标准后验校准方法**：成本低，可把阈值偏置与工具能力问题分开检查；AIGI-Det-Calib 仓库许可不明，因此不直接复制其代码。

### 4.2 只能借鉴方法，暂不能直接部署

- EvoGuard、ForeAgent 和 AIFo 尚无完整官方实现。
- ForenAgent 当前公开的主要是工具箱，完整训练和 Agent 仍不齐。
- AgentFoX 公开仓库未包含论文中完整的专家调用与校准链路。
- CLASP 虽有代码和检查点，但许可与数据获取边界需要先核对。

## 5. 对当前主方案的影响

### 5.1 应停止沿用的假设

不应继续假设“压缩、噪声、纹理三类手工统计量只要换一种提示方式就能成为可靠工具”。若仍使用它们，必须先由独立数据证明每项读数在目标域有稳定信息量，并给出阈值、方向、适用范围和校准误差。否则对 Qwen3-VL 做微调只会教它更稳定地使用一组可能无效的信号。

### 5.2 可以保留的研究核心

“根据干预前轨迹决定是否干预、采用哪种纠错动作”仍与纯检测器研究不同。可保留的区分点是：

- Actor 与取证专家均冻结；
- Monitor 观察 Actor 的初步结论、置信度、工具冲突和适用范围；
- 动作关注**是否接受、核验哪一条证据、是否请求互补专家或考虑替代假设**；
- 在相同调用成本下比较最佳固定动作、全部调用和轨迹条件干预。

### 5.3 必须面对的创新重叠

EvoGuard 已经用 Qwen3-VL 学习按样本选择多个 AIGI 检测器，并以二分类标签进行策略训练。若本项目把主张改成“Monitor 为图像选择合适工具”，会与它高度重叠。更合适的定位是：

> 研究固定取证 Actor 在已经形成初步轨迹后，何时值得干预，以及哪种纠错操作能在受控成本下带来净收益；工具选择只是干预动作的一部分。

这一定位仍需在执行新实验前由用户确认，并在主方案中明确与 EvoGuard 的差异。

## 6. 建议的复用路线

### 路线 A：保留三动作主线，只替换证据层

- 以 AIGI-Holmes、FakeVLM 或 Effort/MIRROR/AIDE 中的 2–3 个冻结模型替代 9 项原始读数。
- 每个工具配一张能力卡：训练任务、输入要求、输出含义、已知强项、失效范围、是否可弃权。
- `A0` 保持不干预；`A1` 改为核验工具范围与证据冲突；`A2` 改为请求一个互补专家并检验替代假设。
- 先做无训练、小样本、预注册式 pilot，检查三个动作是否产生互补纠错，再决定是否训练 Monitor。

优点是延续现有问题和代码；风险是动作定义发生实质变化，需要重新冻结方案，且仍要和 EvoGuard 做明确区分。

### 路线 B：直接研究检测器编排

- 复刻 EvoGuard 的冻结专家、能力画像和策略学习框架；公开代码缺失部分用 ForgeryVCR 的执行框架补齐。

该路线工程上可行，但创新重叠最高，不建议作为当前论文主线。

### 路线 C：把主问题收紧为“干预收益与成本预测”

- 使用公开取证模型形成可信证据环境。
- Monitor 预测 `A1/A2` 相对 `A0` 的增益与额外调用成本，而不是泛化地学习工具路由。
- 重点报告误伤、纠错、弃权、校准和预算约束下的净收益。

这是目前最推荐的定位。它保留原始 Actor–Monitor 构想，同时避开“又一个工具选择 Agent”的直接重复。

## 7. 已确认事项与待核对事项

用户已确认：

1. 当前 9 项手工读数降级为诊断性特征，不再默认作为正式工具主输入；
2. 以路线 C 为主定位，并采用路线 A 的冻结专家作为实现方式；
3. 前端优先复用已有公开工作，把研究资源集中在同轨迹干预收益与成本预测。

Stage 0 已完成，详细矩阵见 [Stage 0 公开组件复用审计](STAGE0_REUSE_AUDIT.md)。首选栈为现有 Qwen3-VL Actor + FSD + AIDE，ForgeryVCR 只作协议参考；AIGI-Holmes 因 14 GiB 权重、DRCT 训练重叠和官方多卡设置降为条件性外部基线，FakeVLM 因许可与安装边界暂缓。

下一项待确认的是：是否按该组件对进入 Stage 1。确认后才实测单张 RTX 4090 的显存、吞吐、分数方向、独立数据有效性和互补性。

## 8. 当前建议

继续不微调 Qwen3-VL-8B，也不在原 pilot 上调提示。建议用户确认后，以 FSD + AIDE 完成 Stage 1 小样本筛选；若二者不能提供有效且互补的冻结证据，则停在 Stage 1 回到候选矩阵，不进入 Monitor 训练。
