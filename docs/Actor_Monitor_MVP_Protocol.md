# 项目主方案：面向 AI 生成图像取证的 Evidence-Grounded Actor–Monitor Framework

## 1. 项目目标与研究定位

本项目面向 AI 生成图像检测，研究一个由 **Forensic Tools、Actor 与 Monitor** 组成的自主取证框架。

与直接训练一个更强的真假分类模型不同，本项目关注的问题是：当一个多模态大模型能够自主调用多个取证工具时，它是否能够正确理解工具返回的证据、合理处理不同证据之间的冲突，并在证据充分时停止取证；进一步地，能否设计一个独立的 **Monitor**，持续监督 Actor 的取证轨迹，识别证据误用、归因错误、冲突遗漏和过早停止等问题，并在必要时要求 Actor 继续获取证据。

整体研究重点放在 **Monitor 对自主 forensic reasoning 的验证与干预能力**，而不是重新提出一种复杂的 Actor 训练算法。

因此，本项目的核心问题可概括为：

> **Can a Monitor determine whether an autonomous forensic agent has acquired, interpreted, and used sufficient evidence faithfully before reaching a verdict?**

最终框架为：

\[
Image
\rightarrow
Forensic\ Actor
\leftrightarrow
Forensic\ Tools
\rightarrow
Reasoning\ Trajectory
\rightarrow
Monitor
\]

其中 Actor 负责“取证”，Monitor 负责“监督取证是否可信”。

---

## 2. 总体系统架构

系统由三个相互解耦的部分组成：

### Forensic Tool Layer

底层由多个已经冻结的专用取证工具组成。

不同工具负责不同类型的 forensic evidence，例如：

- 全局表征异常；
- 局部纹理与生成痕迹；
- 频域或统计特征；
- 其他具有互补性的 forensic cue。

工具本身不由 Actor 训练，也不随着 Monitor 更新。

每个工具不直接向 Actor 输出简单的“真假投票”，而是尽可能转换成统一的 **Evidence Card**。Evidence Card 描述：

\[
Observation
+
Evidence\ Type
+
Scope
+
Directionality
+
Confidence/Quality
\]

其中尤其明确区分：

\[
\text{observation}
\neq
\text{interpretation}
\neq
\text{final authenticity conclusion}
\]

例如 PROBE 提供的 representation deviation 可以作为一个 observation，但如果这一 observation 本身没有真实/伪造方向，就不能由 Actor 自动解释为“支持真实”或“支持伪造”。

这部分延续现有 Evidence-only 设计，并作为后续 Actor 与 Monitor 共同使用的基础协议。

这种“把专业感知能力外置成工具，再交给通用 MLLM 使用结构化取证上下文”的思想与 PATE-Forensics 的 Perception-as-Tool 范式一致。PATE-Forensics 明确将 forensic perception 与 MLLM explanation 解耦，使通用 MLLM 可以消费外部取证结果，而不必自己重新学习全部 forensic perception 能力。

---

## 3. Actor：采用成熟 Tool-Using MLLM 范式

### 3.1 Actor 的定位

Actor 不作为本项目的主要方法创新。

其职责仅包括：

\[
Observe
\rightarrow
Plan
\rightarrow
Call\ Tool
\rightarrow
Read\ Evidence
\rightarrow
Update\ Evidence\ State
\rightarrow
Continue/Stop
\]

即：

1. 观察原图和已有证据；
2. 判断当前还缺少什么信息；
3. 选择合适的 forensic tool；
4. 接收真实工具返回的 Evidence Card；
5. 更新当前 evidence state；
6. 判断继续调用工具还是停止；
7. STOP 时给出 `real/fake` verdict。

这一设计主要借鉴 **ToolDF 的 supervised tool-integrated reasoning**。

ToolDF 将大模型作为 orchestrator，通过结构化轨迹学习场景理解、工具规划、工具调用、证据聚合与最终判断，而不是要求模型端到端承担全部 deepfake detection。它使用 supervised tool-use trajectories 来训练 orchestrator，这与本项目所需要的 Actor 结构高度一致。

类似地，ToolLLM 通过 solution paths 教模型学习多步 API 调用，AgentTuning 则通过高质量 agent interaction trajectories 提升 planning 和 tool utilization；MLLM-Tool进一步说明，多模态模型可以根据视觉输入进行工具选择。

因此，本项目不再继续发明新的 Actor algorithm，而采用成熟的 trajectory-based tool agent 设计。

### 3.2 Actor trajectory

主 Actor 使用统一的结构化轨迹，例如：

\[
Image\ Understanding
\]

\[
\downarrow
\]

\[
Current\ Evidence\ State
\]

\[
\downarrow
\]

\[
Plan
\]

\[
\downarrow
\]

\[
Tool\ Call
\]

\[
\downarrow
\]

\[
Tool\ Observation
\]

\[
\downarrow
\]

\[
Evidence\ Update
\]

\[
\downarrow
\]

\[
CONTINUE / STOP
\]

Actor 可以保留必要的 reasoning，但不追求自由形式的长 Chain-of-Thought。

重点是得到一个**结构清楚、可审计、可被 Monitor 逐步检查的 trajectory**。

JSON 合法性、tool callable、STOP 时只能输出 `real/fake` 等纯结构性要求由 schema/parser/constrained decoding 保证，不再作为 Actor reasoning 能力的一部分。

### 3.3 Actor 是否微调

后续首先尝试基于上述结构化协议运行 Actor。

如果 prompt + schema 已经可以可靠完成工具调用，则不必为了追求更高 Actor 性能额外训练。

如果 Actor 在基本 tool orchestration 上仍然明显不稳定，则按照 ToolDF/AgentTuning 的思路进行一次**轻量 supervised trajectory SFT**，主要学习：

\[
tool\ selection
+
multi\text{-}step\ interaction
+
evidence\ state\ update
+
STOP
\]

而不继续开展复杂的 Actor RL、自反思、MiPO、GRPO 或 self-evolution。

SFT 完成后冻结 Actor。

训练时真实 tool observation 作为环境返回的信息，不要求模型预测工具输出；模型主要学习如何根据这些 observation 做后续决策。这与 ToolDF 将工具响应视为外部条件、重点监督 orchestrator 行为的思路一致。

### 3.4 保留两个 Actor

后续建议保留两个 Actor：

\[
Actor\text{-}A:
Prompt\text{-}only\ Actor\text{-}0
\]

作为较弱、错误更多的 Actor。

以及：

\[
Actor\text{-}B:
Structured\ Tool\ Actor
\]

即最终冻结的 ToolDF-style 主 Actor。

这样不仅可以获得不同质量的 reasoning trajectories，而且能够研究：

\[
Monitor_{train\ on\ A}
\rightarrow
Actor\text{-}B
\]

以及：

\[
Monitor_{train\ on\ B}
\rightarrow
Actor\text{-}A
\]

从而测试 Monitor 是否真正学习了 forensic reasoning validity，而不是记住某一种 Actor 的语言和错误模式。

---

## 4. Actor 不负责解决的问题

为了保证 Actor 与 Monitor 的研究边界清晰，本项目不会把过多 verification 功能放进 Actor。

例如 AgentFoX 已经研究了 expert profile、context-aware evidence fusion 以及不同 detector 冲突的动态处理。它非常接近本项目的应用场景，但如果完整采用这套机制，Actor 自己就会承担大量证据可靠性评估和冲突消解任务，从而压缩 Monitor 的研究空间。

因此主 Actor **不额外引入**：

\[
learned\ verifier
\]

\[
expert\ reliability\ model
\]

\[
self\text{-}reflection
\]

\[
self\text{-}correction
\]

\[
hindsight\ evolution
\]

\[
RL\text{-}based\ tool\ credit
\]

等模块。

ForeAgent 已经研究了通过 hindsight-driven self-refining 不断改善 forensic reasoning，而 TACO 等工作进一步研究了如何通过 RL 为不同 tool call 分配 credit。这些方向属于“如何训练更强的 Actor”，不是本项目当前的主要问题。

因此 Actor 达到“**能够可靠执行工具调用，但 reasoning 并不完美**”即可。

这种不完美不是系统缺陷，而是 Monitor 所需要面对的真实问题。

---

## 5. FaithBench：从 Actor 测试转向 Monitor Benchmark

现有 Mini FaithBench 不再主要用于反复修改 Actor prompt，而逐步转变成 **forensic reasoning monitoring benchmark**。

其目标是收集真实 Actor trajectory 中不同类型的 reasoning failure，并构造可验证的 Monitor ground truth。

重点关注以下几个维度：

| Failure type | 含义 |
|---|---|
| Evidence attribution error | 将某个工具没有提供的结论错误归因给该工具 |
| Unsupported synthesis | Actor 的综合结论超出了已有 evidence |
| Conflict omission | 存在工具冲突，但 reasoning 中未识别或处理 |
| Evidence insufficiency | 当前证据不足以支持结论 |
| Premature STOP | 尚有重要 evidence gap 时提前停止 |
| Unnecessary continuation | 证据已经充分但仍无意义调用工具 |
| Verdict inconsistency | 最终 verdict 与前面的 evidence/reasoning 不一致 |

现有 Mini FaithBench 已经发现的一类典型案例：

\[
PROBE:
representation\ deviation
\]

被 Actor 转化为：

\[
supports\ real/fake
\]

就是非常典型的 evidence attribution failure。

相比单纯判断最终分类正确与否，这类错误更符合后续 Monitor 的研究目标：一个 Agent 即使最终猜对，也可能通过错误理由得出答案。

FaithBench 后续应同时包含：

\[
correct\ trajectories
\]

和：

\[
naturally\ occurring\ Actor\ failures
\]

必要时再加入 controlled perturbation / counterfactual trajectories，用于精确控制某一种 reasoning error。

---

## 6. Monitor：项目的核心研究对象

### 6.1 Monitor 的基本定位

Monitor 不重新扮演第二个 deepfake classifier。

它的任务不是：

\[
Image\rightarrow real/fake
\]

而是：

\[
Trajectory
\rightarrow
Is\ this\ reasoning\ justified?
\]

Monitor 主要读取：

\[
Tool\ specification
+
Evidence\ Cards
+
Actor\ trajectory
\]

必要时再加入原图或局部图像。

Monitor 判断至少包含以下几个维度：

\[
Attribution\ Validity
\]

\[
Evidence\ Sufficiency
\]

\[
Conflict\ Resolution
\]

\[
Reasoning\ Support
\]

\[
STOP\ Appropriateness
\]

最终输出可以从最简单的：

\[
PASS / FAIL
\]

逐步扩展为：

\[
PASS
\]

或者：

\[
CONTINUE
+
Failure\ Type
+
Reason
+
Missing\ Evidence
\]

Monitor 的核心价值因此不是“再投一票”，而是判断：

> **Actor 当前有没有资格作出这个判断。**

### 6.2 Monitor 第一阶段：离线轨迹验证

第一阶段先研究 offline monitoring。

给 Monitor 一条完整 Actor trajectory，让其判断：

- 哪一步出现了 reasoning violation；
- violation 属于什么类型；
- 最终 STOP 是否合理；
- 当前 verdict 是否被 evidence 支持。

先把“能不能看出错”解决。

GLEAN 提供了非常有价值的参考：它不单纯判断 agent 最终答案，而是根据领域 guideline 对 trajectory 做 step-wise alignment evaluation，并沿轨迹累积 evidence，最终估计决策可靠性。

本项目可以对应地建立：

\[
Forensic\ Evidence\ Guidelines
\]

例如：

> 哪些工具提供 directional evidence；

> 哪些 evidence 只能作为 observation；

> 什么情况下两个 evidence 构成冲突；

> 什么情况下 evidence 足以 STOP。

于是：

\[
Forensic\ Guidelines
+
Trajectory
\rightarrow
Monitor
\]

成为第一阶段 Monitor 的主要范式。

### 6.3 Monitor 第二阶段：在线干预

当离线 Monitor 能够可靠识别错误后，再进入更重要的 online monitoring。

每获得一个新 observation 后：

\[
Actor\ State_t
\rightarrow
Monitor
\]

Monitor 判断：

\[
Safe\ to\ continue?
\]

或者：

\[
Safe\ to\ STOP?
\]

如果 Actor 想 STOP，而 Monitor 判断：

\[
Evidence\ Insufficient
\]

则拒绝停止，并要求继续获取某类 evidence。

最终系统形成：

\[
Actor
\rightarrow
Monitor
\rightarrow
Actor
\rightarrow
Monitor
\rightarrow ...
\]

但 Monitor 不直接替 Actor 选择具体工具。

它更适合给出类似：

\[
Need\ additional\ independent\ local\ evidence
\]

而不是：

\[
Call\ PatchCraft
\]

这样仍然保留 Actor 的 autonomy。

### 6.4 Monitor 输入信息量

这一部分可以成为很有价值的 ablation。

比较：

\[
M(Image + Full\ Trajectory)
\]

\[
M(Evidence\ Cards + Trajectory)
\]

\[
M(Evidence\ Summary + Critical\ Steps)
\]

以及：

\[
M(Selected\ Evidence)
\]

2026 年关于 LLM Monitor 的研究发现，给 Monitor 更多 trajectory 信息并不一定更好；extract-and-evaluate 方法通过先提取关键内容再评价，反而能够改善部分监控任务。

因此本项目可以进一步研究：

> **For forensic agent monitoring, what information should the Monitor actually observe?**

这个问题与 Monitor 本身非常契合，并且不会重新滑回 Actor 优化。

---

## 7. 后续总体实验路线

整个项目后续按四个大阶段推进：

### Phase I — Actor Finalization

目标不是继续优化 Actor，而是尽快得到一个可信的固定轨迹生成器。

完成：

\[
Frozen\ Tools
+
Evidence\ Interface
+
Structured\ Actor
\]

必要时进行一次轻量 trajectory SFT。

通过基本 tool-use sanity check 后，冻结 Actor-B。

Actor-0 保留作为 Actor-A。

此后原则上不再因为 Monitor 实验结果修改 Actor。

---

### Phase II — FaithBench Construction

系统运行 Actor-A / Actor-B，收集大量真实 forensic trajectories。

建立 reasoning error taxonomy，并进行：

\[
step\text{-}level
\]

和：

\[
trajectory\text{-}level
\]

标注。

Mini FaithBench 逐渐扩展成正式 FaithBench。

这个阶段最重要的产物不是更多图片，而是：

\[
Image
+
Tool\ Evidence
+
Actor\ Trajectory
+
Monitor\ Ground\ Truth
\]

---

### Phase III — Monitor Development

首先建立简单 baseline：

\[
Prompt\text{-}only\ LLM\ Judge
\]

随后逐步加入：

\[
Evidence\ Guidelines
\]

\[
Structured\ Verification
\]

\[
Evidence\ Selection
\]

以及必要的：

\[
Monitor\ SFT
\]

重点提升：

- attribution violation detection；
- evidence insufficiency detection；
- conflict detection；
- premature STOP detection；
- calibration。

Monitor 是否需要 SFT、preference learning 或其他训练方式，在 FaithBench 建成以后再根据 baseline 结果决定，而不是现在提前锁死。

---

### Phase IV — Online Actor–Monitor System

最后把 Monitor 接回 Actor loop。

比较：

\[
Actor
\]

与：

\[
Actor + Monitor
\]

在以下指标上的差异：

\[
Final\ Accuracy
\]

\[
Balanced\ Accuracy
\]

\[
Faithfulness
\]

\[
Unsupported\ Claim\ Rate
\]

\[
Premature\ STOP\ Rate
\]

\[
Conflict\ Resolution
\]

\[
Average\ Tool\ Calls
\]

最终验证：

> Monitor 能否在不大幅增加 tool cost 的情况下，提高自主 forensic agent 的可靠性。

---

## 8. 最终论文贡献预期

如果上述路线成立，论文贡献不应描述为“提出一个新的 deepfake detection Actor”。

更合适的贡献结构是：

**第一，提出一种面向多工具 AI 图像取证 Agent 的 evidence-grounded monitoring formulation。**

研究的不只是 final prediction，而是整个：

\[
evidence\ acquisition
\rightarrow
evidence\ attribution
\rightarrow
synthesis
\rightarrow
STOP
\]

过程。

**第二，构建 FaithBench。**

专门评估 forensic agent 是否正确使用证据，而不是只评估最终真假准确率。

**第三，提出 Forensic Monitor。**

让 Monitor 基于工具语义和已有证据判断：

\[
reasoning\ validity
\]

和：

\[
evidence\ sufficiency
\]

并识别 subtle forensic reasoning failures。

**第四，将 Monitor 接入自主取证循环。**

验证 Monitor 是否能够阻止错误 STOP、要求补充证据，并改善完整 Actor–Tool 系统的可靠性。

**第五，验证跨 Actor 泛化。**

使用不同质量、不同训练方式的 Actor，测试 Monitor 学到的是通用 forensic reasoning rules，还是仅仅拟合某个 Actor 的行为模式。

---

## 9. 当前路线决策

截至目前，项目路线正式从：

\[
\text{不断优化 forensic Actor}
\]

转变为：

\[
\boxed{
Standard\ Actor
\rightarrow
FaithBench
\rightarrow
Monitor
\rightarrow
Online\ Verification
}
\]

Actor 采用已有成熟 tool-agent 范式完成必要的工程适配即可。

后续不再把主要实验预算投入 Actor prompt engineering、复杂强化学习或 self-evolution。

项目最重要的研究问题转向：

\[
\boxed{
When\ should\ a\ forensic\ agent's\ reasoning\ be\ trusted?
}
\]

以及：

\[
\boxed{
Can\ an\ independent\ Monitor\ detect\ when\ the\ Actor\ has\ not\ earned\ its\ conclusion?
}
\]

这将作为后续 FaithBench、Monitor 设计和整篇论文实验的主线。