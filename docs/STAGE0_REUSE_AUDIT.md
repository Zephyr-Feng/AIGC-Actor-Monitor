# Stage 0：公开组件复用审计与推荐栈

**核对日期：2026-09-28**  
**状态：审计完成；等待用户确认候选组件后进入 Stage 1**

## 1. 审计目标与边界

本阶段只核对公开论文、官方仓库、权重、许可证、训练数据、接口和单张 RTX 4090 的可行性，不下载新权重、不改写 v2 实验代码、不运行模型推理。目标是选择一个足够小、许可清楚、证据互补的冻结前端，把后续研究资源留给本项目的同轨迹反事实账本、动作增量收益和成本预测。

本次核对的运行环境为当前 AutoDL 克隆实例：RTX 4090 24 GB；系统盘约 30 GB 可用；数据盘 50 GB 中约 11 GB 可用；Python 3.12.3、PyTorch 2.12.1、Transformers 4.57.6。当前 GPU 空闲。本阶段没有产生 GPU 推理费用。

## 2. 候选组件矩阵

| 组件 | 可复用角色 | 许可与公开状态 | 权重/环境与 4090 可行性 | 训练数据或任务边界 | 决定 |
|---|---|---|---|---|---|
| [FSD / Forensic Self-Descriptions](https://github.com/ductai199x/Forensic-Self-Descriptions-CVPR25) | 连续取证分数；低层法证微结构专家 | 代码和权重说明为 CC BY-NC-SA 4.0；检测代码与权重已公开 | Python ≥3.12、Torch ≥2.10，与当前环境直接兼容；检测权重约 55 MB；CPU/GPU 均可。单图算法含图像内优化，真实延迟仍需 smoke | 只用真实图训练；论文实验涉及 COCO2017、ImageNet 与 MIDB。发布权重没有清楚标明采用哪一组真实训练子集，因此 COCO 无重叠不能假定 | **首选专家**；连续 z-score 适合校准和能力卡。确认性评测避开 COCO/ImageNet/MIDB 真图 |
| [AIDE](https://github.com/shilinyan99/AIDE) | 与 FSD 互补的混合视觉/噪声专家 | 仓库 MIT；代码与检查点公开，Chameleon 数据仅限学术研究 | 官方测试 Python 3.10、Torch 2.0.1；`requirements.txt` 又固定 Torch 1.11，需隔离环境并以官方推理最小依赖为准。CNN 前向预计可在单张 4090 运行，仍需实测显存、延迟和 checkpoint 输出 | 训练集来自 CNNSpot 与 GenImage；不能用这两者作为无重叠确认性测试 | **第二首选专家**；进入 Stage 1 前核对具体 checkpoint、输出方向与权重条款 |
| [ForgeryVCR](https://github.com/youqiwong/ForgeryVCR) | Qwen 系工具协议、轨迹与恢复执行参考 | 仓库 Apache-2.0；推理/评测公开，训练部分尚未完全公开；NPP 组件另有限制 | 完整合并权重约 8.28 GiB；依赖 vLLM、FlashAttention 与 ms-swift。当前 Python/Transformers 接近，但整体引入过重 | 主要任务是图像篡改检测与定位，不是完整 AIGI 二分类 | **只复用协议思想和必要代码片段**；保留现有同前缀执行器，不整包接入，也不下载模型 |
| [AIGI-Holmes](https://github.com/wyczzy/AIGI-Holmes) | 专业 MLLM 强基线或备用 Actor | 代码和模型 Apache-2.0；数据 CC BY-NC-SA 4.0 | 8B BF16 权重约 14.10 GiB，超过当前数据盘余量；官方长上下文协作解码示例采用 4 卡；依赖 Python 3.10、Transformers <4.48 | 训练数据明确包含 DRCT、GenImage 与 CNNDetection；与现有 DRCT pilot 有训练重叠 | **条件性外部基线**；扩盘并改用无重叠测试后再考虑，不进入最小前端 |
| [FakeVLM](https://github.com/opendatalab/FakeVLM) | 专业取证 VLM 基线 | FakeClue 数据标为 Apache-2.0；代码仓库和模型页未见清晰许可证 | 权重约 13.16 GiB，超过当前数据盘余量；官方训练环境较重，依赖文件含不可移植的本地 NumPy 路径 | FakeClue 大量复用 GenImage、FaceForensics++、Chameleon；训练需多卡 | **暂缓**；先解决许可与安装可复现性 |
| [MIRROR](https://github.com/handsome-rich/MIRROR) | 冻结检测器候选 | 仓库未见明确许可证 | DINOv3-Huge 路线，单卡可能运行但存储与显存需 smoke | 第一阶段使用约 20 万 MS-COCO 真图，第二阶段使用 GenImage SD1.4；当前 COCO 真图存在训练重叠风险 | **不进入主栈**；许可和 COCO 重叠均不合适 |
| [Effort](https://github.com/YZY-stack/Effort-AIGI-Detection) | 轻量冻结检测器候选 | 仓库未见明确许可证 | 依赖 Torch 1.12/CUDA 11.3 等旧环境；公开 checkpoint 可单卡运行 | checkpoint 以 GenImage 或 Chameleon 的 SD1.4 数据训练 | **暂不采用**；许可与环境劣于 FSD/AIDE |
| [CLASP](https://github.com/yqli00000/CLASP) | 证据图与 MLLM 解释结构参考 | 代码公开但未见明确许可证，训练数据未完整分发 | DINOv3/DDL-X，训练默认多卡；解释还依赖外部 Qwen API | 任务含检测与定位，完整复现实验条件不足 | **只借鉴结构** |
| [AgentFoX](https://github.com/suncore946/AgentFoX) | Agent 报告骨架参考 | Apache-2.0 | 最小仓库可运行，但专家调用、校准和聚类核心在公开版中停用 | 无法直接提供论文中的专家融合能力 | **只作接口参考** |
| [AIGI Detector Calibration](https://github.com/muliyangm/AIGI-Det-Calib) | 后验校准方法参考 | 仓库未见明确许可证 | 只处理 logits，算力成本低 | 默认少样本目标域校准会消耗开发样本，必须与测试隔离 | **复用公开方法，不复制未授权代码**；用标准温度缩放/逻辑校准实现 |

## 3. 推荐的最小复用栈

### 3.1 组件

1. **Actor**：继续冻结现有 `Qwen3-VL-8B-Instruct`、中文输出和解码设置，避免同时更换 Actor 与证据层。
2. **候选专家对**：FSD + AIDE。两者都输出模型得分，但证据机制不同：FSD 建模低层法证微结构，AIDE 结合视觉语义与噪声模式，适合检验互补纠错。
3. **角色初始假设**：先把 FSD 作为 `E_base`、AIDE 作为 `E_extra`。Stage 1 同时测量真实延迟；若 FSD 的单图优化显著慢于 AIDE，则按预先写明的规则交换二者角色，再冻结动作，不按准确率临时挑角色。
4. **A1 审计**：实现确定性的结构化审计，包括输入范围、分数方向、校准状态、专家是否 OOD、证据是否冲突或缺失。A1 不调用新专家。
5. **校准**：保留原始分数，用独立开发集拟合简单的温度缩放或逻辑校准；同时记录未校准分数，防止校准掩盖模型失效。
6. **执行器**：保留本项目现有同前缀分支、checkpoint/resume 和数据契约；只吸收 ForgeryVCR 的工具消息/schema 设计，不引入其整套 vLLM/ms-swift 依赖。

该组合的直接好处是：不需要再训练取证检测器；新增检测权重规模很小；当前服务器无需扩盘即可先做 FSD；AIDE 使用独立环境，不污染现有 Qwen 环境。需要 Stage 1 实测的关键不确定项只有三类：AIDE checkpoint 的最小安装、两专家在独立数据上的有效性与互补性，以及实际延迟/显存。

## 4. 数据复用与泄漏边界

1. 旧 T0 与三动作 pilot 继续只作为方案诊断材料。COCO 真图可能与 FSD、MIRROR、B-Free 等公开方法的训练数据重叠；DRCT 假图与 AIGI-Holmes 训练数据重叠，不能作为这些组件的确认性比较。
2. Stage 1 不使用 CNNSpot、GenImage、COCO、ImageNet 或 MIDB 作为主要筛选数据，避免与 FSD/AIDE 的已知或未澄清训练来源重叠。
3. 首选新开发数据候选是 [B-Free 发布的扩展 Synthbuster](https://github.com/grip-unina/B-Free)：真实图来自 RAISE，假图来自 FLUX 与 Stable Diffusion 3.5，各 1,000 张。它与推荐专家的已知训练源不同，且同一真实内容有对应生成图，适合按 source group 划分。正式下载前还需核对数据链接条款与压缩/分辨率元数据。
4. Stage 1 只从该数据中抽取预先固定的小型筛选集；Stage 2/3/4 的开发、验证和测试按 source group 隔离，任何用于阈值或校准的样本都不进入测试。

## 5. 不推荐现在做的工作

- 不微调 Qwen3-VL，也不在旧 pilot 上继续调提示；
- 不下载 AIGI-Holmes、FakeVLM 或 ForgeryVCR 的 8–14 GiB 合并权重；
- 不重新实现新的 AIGI 检测器或自行生成大批假图；
- 不把作者论文报告的性能当成本项目实测结果；
- 不在 FSD/AIDE 有效性和动作选择空间尚未证明前训练 Monitor。

## 6. Stage 1 的确认后执行顺序

用户确认“FSD + AIDE + 现有 Qwen Actor”后，Stage 1 按以下顺序执行：

1. 在当前环境安装 FSD 的最小推理依赖，下载约 55 MB 检测权重；不启用 attribution 权重；
2. 用少量非实验图片做 API/CPU smoke，再用 4090 测单图延迟、显存和重复性；
3. 建立独立 Python 3.10 环境接入 AIDE，核对 checkpoint 输出方向和预处理；
4. 下载并登记新的无重叠开发样本清单；
5. 分别评估两专家的 balanced accuracy、fake recall、real specificity、分数方向、校准与失败样本；
6. 检查两专家错误集合是否互补，再冻结 `E_base`、`E_extra` 与能力卡。若任一专家接近随机、严重单边预测或无法稳定运行，停止在 Stage 1，回到候选矩阵讨论替换，不进入三动作 pilot。

## 7. 当前待用户确认的研究决定

建议确认以下整组方案：

> 冻结现有 Qwen3-VL-8B Actor；Stage 1 只筛选 FSD 与 AIDE；数据优先使用 RAISE/FLUX/SD3.5 的公开扩展 Synthbuster 小样本；ForgeryVCR 只作协议参考；大模型专家和许可不清组件暂不下载。

确认后才会下载权重、创建 AIDE 环境并占用 GPU 做 smoke。
