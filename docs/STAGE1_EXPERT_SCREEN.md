# Stage 1：冻结专家有效性筛选

**开始日期：2026-09-28**  
**状态：正确顺序 AIDE 重跑与失败分析完成；专家栈暂停冻结**

## 1. 已确认配置

- Actor：冻结现有 `Qwen3-VL-8B-Instruct`；
- 候选专家：FSD + AIDE；
- 候选开发数据：B-Free 扩展 Synthbuster 的 RAISE / FLUX / SD3.5；
- 本阶段只筛选冻结专家的可运行性、有效性、校准与错误互补性，不训练 Monitor。

## 2. FSD 接入记录

### 2.1 来源与完整性

- 官方仓库：`ductai199x/Forensic-Self-Descriptions-CVPR25`；
- `main` 快照提交：`50f2eae06efdac2e5a33f407ca9a27a2295133ac`；
- 源码 zip SHA-256：`ef0be83f1e1007cd927577d41e9384f094c833686be432663d63b68784a84943`；
- 权重发布：`v1.2.0`；只下载 detection 文件，没有下载 attribution 文件；
- 服务器源码：`/root/autodl-tmp/external/Forensic-Self-Descriptions-CVPR25-main`；
- 服务器权重：`/root/autodl-tmp/models/fsd/v1.2.0`。

权重摘要均与 GitHub Release API 的官方 digest 一致：

| 文件 | 大小（字节） | SHA-256 |
|---|---:|---|
| `config.json` | 634 | `7cc34433045adb998762e00de7de25c50f9c1e10dbac1c18899c6c63c4cfafe4` |
| `fre.pt` | 9,861 | `d95b9c50837dbf7b660bbefa20cdaa5db5e59601a9d6544573c10e78e04906bb` |
| `gmm.pt` | 14,786,229 | `0f9fa030a3d5816266d0329fd0fb614b65e322d4bda6d083613c713bfe9bc829` |
| `fsd_transforms.pt` | 42,177,409 | `1e87d792b413101e58d9de71551182a1fab8b879ca6f6ba9780b6adcb9a5a699` |

### 2.2 最小依赖

核心 detection 路径只缺 SciPy。没有安装 `ray`、`gradio`、`pillow-heif`，也没有为已发布 GMM 安装只在重新拟合时使用的 `scikit-learn`。

- 独立依赖目录：`/root/autodl-tmp/external/fsd-py312-deps`；
- 新增依赖：`scipy==1.17.0`；
- 沿用基础环境：Python 3.12.3、PyTorch 2.12.1、NumPy 2.4.6、Pillow 12.2.0；
- 没有修改 Qwen 基础环境中的已安装包。

### 2.3 Smoke 结果

使用 `scripts/smoke_fsd.py`。输入为 FSD 仓库自带 `assets/teaser.jpg`，只验证执行链，不计入实验结果。

| 项目 | 结果 |
|---|---:|
| CPU load | 0.802 s |
| GPU run 1 load / score | 0.495 s / 3.055 s |
| GPU run 2 load / score | 0.503 s / 3.032 s |
| 两次 peak allocated | 10,948.589 MiB |
| 两次 raw score | -156.05543031102212 |
| 两次 z-score | -0.1611801944018042 |
| 两次标签 | `real`（阈值 -2.0） |

两次分数完全一致。该标签只对应仓库展示图片，没有检测性能含义。

### 2.4 执行约束

FSD 权重很小，但单图计算峰值约 10.95 GiB。它可以在单张 4090 上运行，但不应与当前约 17 GB 的 Qwen Actor 同时常驻。正式采集采用顺序执行：先预计算并落盘 FSD 分数，释放 FSD/CUDA 内存，再启动 Actor 消费结构化证据。该约束需计入 `E_base` 的真实延迟和成本。

### 2.5 网络异常与处理

AutoDL 到 GitHub 的 `git clone` 未完成；`codeload` 只有约 15–25 KB/s，两轮 60 秒下载均超时。已改为本机从官方 URL 下载、核对官方 SHA-256、通过 SCP 上传，再在服务器复核摘要。没有保留不完整仓库；失败的 zip 被完整校验文件覆盖。

## 3. AIDE 接入记录

### 3.1 来源、权重与完整性

- 官方源码 `main` 提交：`6725b710d5c437ab2f59792908ce0377dfc907de`；源码 zip SHA-256：`ac10669273d8742b667cdacbd772a0d749d56851ecff00779fd0852bf492797e`；
- 仅选择官方 `progan_train.pth`；服务器最终路径：`/root/autodl-tmp/models/aide/progan_train.pth`；
- 文件大小：`3,592,077,976` 字节；本地、服务器重组文件、数据盘临时副本和最终文件的 SHA-256 均为 `ce3a9d66c124e4c24846a6e513d4c66a7e34a16c46bd46a8041f809c2a4a756e`；
- 2026-09-28 将本地完整权重切成 14 片并四路上传；服务器逐片核验后在系统盘重组，再通过数据盘同目录临时文件替换旧半成品。临时分片已清理。

### 3.2 依赖与无卡检查

- 源码：`/root/autodl-tmp/external/AIDE-main`；Python 3.12 最小独立依赖目录：`/root/autodl-tmp/external/aide-py312-deps`；导入 `torch`、`torchvision`、`open_clip`、`timm`、`kornia`、`clip` 和 `models.AIDE` 已通过，未改动 Qwen/FSD 依赖；
- 使用 `scripts/smoke_aide.py` 对完整权重执行 `load_state_dict(..., strict=True)`，CPU 加载成功，耗时 22.12 秒；
- 官方数据集代码以 `0_real` / `1_fake` 编码，smoke 脚本将第二类 softmax 概率记为 fake 概率。

### 3.3 4090 smoke 结果

使用源码自带 `docs/Chameleon.jpg`，以两个独立进程分别重新构建模型、严格加载权重并运行一次单图推理。展示图只验证执行链，不计入研究结果。

| 项目 | run 1 | run 2 |
|---|---:|---:|
| 严格加载 | 26.338 s | 23.609 s |
| 单图模型前向 | 1.676 s | 1.119 s |
| peak allocated | 3,630.059 MiB | 3,630.059 MiB |
| logits `[real, fake]` | `[-0.6571024, 0.6045268]` | `[-0.6571024, 0.6045268]` |
| fake probability | 0.7793064 | 0.7793064 |
| 标签 | `fake` | `fake` |

两次 logits、概率和标签完全一致，严格权重加载与 CUDA 前向均通过。脚本中的 `score_seconds` 只计模型前向；AIDE 的 DCT 与五路图像预处理在 CPU 上执行，本次未单独计时，正式成本评估需计入完整端到端延迟。两次进程退出后显存回到 1 MiB、GPU 利用率 0%，没有残留计算进程。

**2026-09-29 再核对**：官方源码 SHA-256 为 `ac10669273d8742b667cdacbd772a0d749d56851ecff00779fd0852bf492797e` 的 `TestDataset.__getitem__` 实际返回四路 DCT 在前、原图 `x_0` 在最后；`AIDE_Model.forward` 也按此顺序取输入。此前将原图改到首位是错误修正。因此本节两次原始 Chameleon smoke 的输入顺序正确；此后第 6 节的 RAISE/FLUX/SD3.5 smoke 与 600 张批量评分的输入顺序错误，其 logits、概率和标签全部无效。`scripts/smoke_aide.py` 已恢复官方顺序。

## 4. 开发数据准备

### 4.1 官方来源与使用边界

- 官方来源：[B-Free 扩展 Synthbuster](https://www.grip.unina.it/download/prog/B-Free/extended_synthbuster/)；B-Free 官方仓库在 2026-01-14 记录该数据发布；
- 数据组成：1,000 张 RAISE 真图、1,000 张以相同 RAISE 内容描述生成的 FLUX 图、1,000 张 SD3.5 图；
- 计划只下载 `real_RAISE_1k.zip`（官方目录约 1.5 GB）和 `sd3_flux.zip`（约 3.2 GB），不下载与本阶段无关的 `latent-diffusion.zip`；
- 官方 `checksum.txt` 提供的 MD5 分别为 `a6aad7728226218f22a28b9c9aacaa2c` 和 `5a255c18fa99eb3115c7ed39d2840796`。下载后同时记录 SHA-256；
- B-Free 仓库许可限定 informational / nonprofit 使用，公开结果需引用原作者并保留原始声明。解压后还需核对数据包内是否附有更具体的数据许可；
- Stage 0 已排除 CNNSpot、GenImage、COCO、ImageNet 和 MIDB 等已知或未澄清训练重叠源。RAISE / FLUX / SD3.5 与 FSD、AIDE 当前已知训练源不同，但只能表述为“未发现已知重叠”，不能证明不存在未公开训练数据重叠。

服务器目前没有发现这些数据的现有副本。数据盘剩余约 6.9 GB，不能稳妥保存完整压缩包与解压结果；系统盘约 30 GB 可用，适合作临时下载、校验和抽样区。

### 4.2 已冻结的小型筛选设计

- 独立单位是 source group；同一 RAISE 内容及其 FLUX、SD3.5 对应图必须整体分配，不能把三张关联图当成三个独立重复；
- 固定抽取 200 个 source groups，共 600 张原始图；使用固定随机种子 `20260928` 将 100 组分到 calibration、100 组分到 screening；
- calibration 只用于分数方向核验和简单后验校准，screening 只用于报告 balanced accuracy、real specificity、FLUX recall、SD3.5 recall、失败率和两专家错误互补性；
- screening 每个类别各 100 张。二项比例在最坏情形附近的 95% Wilson 区间半宽约 9.6%，适合淘汰接近随机、严重单边或执行不稳定的候选；不足以支持细微专家差异或正式论文效果结论；
- 本批 Stage 1 样本不进入 Stage 2/3/4。其余 800 个 source groups 继续保留，后续按 source group 划分，避免组件选择污染确认性集合；
- 保留原始文件字节，不重编码、不统一尺寸；清单记录 source group、split、标签、生成器、相对路径、字节数、尺寸、格式和 SHA-256；
- 下载流程拟为：系统盘临时下载完整官方压缩包 → 核对官方 MD5 并补充 SHA-256 → 检查包内许可、目录和一一对应关系 → 固定抽样清单 → 仅复制 600 张到数据盘 → 再核对摘要 → 清理系统盘临时副本。

按当前 smoke 估算，FSD 对 600 张图的模型前向约需 30 分钟；AIDE 的 CPU DCT 与五路图像预处理尚无端到端批量计时，预计总耗时为数小时。清单冻结和 CPU 完整性检查不需要 GPU；真正运行专家前另行通知用户开卡。

用户于 2026-09-28 确认采用上述 200 个 source groups 方案。

### 4.3 下载、许可与结构核验（2026-09-29）

服务器直连官方源只有约 12 KiB/s，预计首包约 37 小时，已终止并清理 835,584 字节半成品。本机使用官方 HTTPS 下载两个完整包，官方 MD5 与补充 SHA-256 如下：

| 文件 | 字节数 | 官方 MD5 | 本机 SHA-256 |
|---|---:|---|---|
| `real_RAISE_1k.zip` | 1,646,333,296 | `a6aad7728226218f22a28b9c9aacaa2c` | `bd25842eb4069937d6676a31538bb557dc78db9867fa6e463df5af11d86fa73e` |
| `sd3_flux.zip` | 3,436,462,649 | `5a255c18fa99eb3115c7ed39d2840796` | `92a1d7f4f33e9a34c4556c3677e190a6db63ff6821fff98425271926013116b6` |

ZIP 中三类有效图像各 1,000 张，同名 source group 完全一一对应。FLUX 目录另有 3 个 `.ipynb_checkpoints/*-checkpoint.png` 文件，实际编码为 WEBP，不属于 1,000 个有效组，已排除。有效图像均为 RGB PNG；RAISE 宽高约 1256–1258 × 833–835（含纵向），FLUX 与 SD3.5 均为 1024 × 1024。统一编码但尺寸与宽高比仍不同，专家结果可能包含尺寸敏感性。

包内 `RAISE_License.pdf` 与 `README.txt` 已检查：仅供科学、非商业使用；发表时须引用 RAISE；复制件保留版权、许可条款及原站链接。许可文件与 600 张图一同保存于本地和服务器数据目录。B-Free 仓库另限定 informational / nonprofit 使用并要求引用作者。

### 4.4 固定清单与双端复核（2026-09-29）

使用 `scripts/prepare_stage1_expert_data.py`、种子 `20260928` 按 source group 抽 200 组，其中 calibration 100 组、screening 100 组，共 600 张原始图；未重编码。`scripts/validate_stage1_expert_data.py` 在本地和服务器最终路径逐图核对字节数、SHA-256、格式与尺寸，确认每组三图齐全、两 split 无交叉，均通过。

- 本地：`runs/stage1-bfree-screen-20260928/`；服务器：`/root/autodl-tmp/datasets/stage1-bfree-screen-20260928/`；
- `manifest.jsonl` SHA-256：`f305e5ffd99f3ec9d908494f2dcbfdcb856d7e74dedb8a3dd1130fad0c99660b`；
- `dataset_summary.json` SHA-256：`e014c540bc2ba59ba416f6583d64ebd648a2f9fee2f62fd19eba408fbf1d8091`；
- 上传 tar 大小 `1,020,500,992` 字节、SHA-256 `d22bf566cc8511e31b2a301903968d5c738eb5692a9d76014c0ba6f5c6603fb2`；四个分片与远端重组摘要一致；
- 服务器数据盘最终剩余约 5.9 GB；上传分片、重组 tar 和服务器失败下载半成品已清理。本地保留两个经官方 MD5 校验的原始压缩包，清理了上传临时件。

## 5. 批量评分入口与执行（2026-09-29）

新增 `scripts/score_stage1_experts.py`，按固定 manifest 逐图追加 JSONL，并可按已完成 `sample_id` 续跑。新克隆实例的 Stage 1 数据、FSD/AIDE 权重与清单 SHA-256 均核对通过；两位专家各曾完成 600 张推理，结果目录 `/root/autodl-tmp/trajectories/stage1-bfree-screen-20260928/`。本地副本位于 `runs/stage1-bfree-screen-20260928/scores/`，两份 JSONL 与服务器 SHA-256 一致；各 600 行、样本 ID 唯一并相互对齐。**AIDE 这份 JSONL 使用错误输入顺序，只作为失效历史记录，不能用于性能或互补性结论；重跑时使用新文件，不覆盖旧结果。**

无卡模式下，AIDE 首张大图 CPU 预处理进程两次退出，未生成输出；当时 cgroup 上限 2 GiB，原因未确定。4090 挂载后原始 RAISE、FLUX、SD3.5 图预处理和前向均正常，因此无卡预处理失败未影响评分。

## 6. 原始评分与运行表现（FSD 有效，AIDE 失效）

AIDE RAISE 单图两次严格加载与 CUDA 前向均成功，输入顺序错误，`fake_probability=0.20868` 及 FLUX/SD3.5 的预测全部作废。加载耗时 15.81 / 15.29 秒、预处理 0.296 / 0.237 秒、前向 1.138 / 0.815 秒、峰值分配显存 3,630.1 MiB；这些只说明可运行性和大致资源开销。

FSD 600 张平均 2.600 秒/张、峰值分配 10,696.5 MiB；失效 AIDE 运行平均 0.295 秒/张（含预处理）、峰值分配 3,630.7 MiB。两轮之间显存回到 0 MiB。角色待 AIDE 正确顺序重跑后再决定。

默认阈值下的筛查结果如下；校准集用于拟合，screening 集仍保持独立：

| Split / 专家 | AUC（fake 方向） | balanced accuracy | RAISE 真图 specificity | FLUX recall | SD3.5 recall |
|---|---:|---:|---:|---:|---:|
| calibration / FSD | 0.742 | 0.530 | 0.060 | 1.000 | 1.000 |
| screening / FSD | 0.700 | 0.520 | 0.040 | 1.000 | 1.000 |

FSD 默认阈值对真图的 specificity 很低。原始汇总 JSON `runs/stage1-bfree-screen-20260928/scores/summary_uncalibrated.json` 含有失效 AIDE 指标和互补性数字，不得用于结论。

## 7. 类别均衡校准与独立筛查（2026-09-29）

用户确认对真/假采用各半总权重。此前用 calibration 的 100 个 source groups 对两位专家分别拟合一维岭逻辑校准器（每类总权重 0.5，系数惩罚 `1e-3`），screening 的另外 100 组只用于评估；其中 AIDE 输入错误，只有 FSD 校准与指标有效。原始分数未改写，历史派生文件位于 `runs/stage1-bfree-screen-20260928/scores/calibrated/`。原始评分 SHA-256：FSD `f2caf2eafa95225807f68812c62c68b4d776cff5191a1ae3574d731420be04dd`；失效 AIDE `683c0d60b3c9490345dbe81e199bf8b10264ef6dd381b61e9436226ec3ea1ea4`。校准入口现要求 AIDE 评分元数据明确记录官方输入顺序，避免再次使用旧文件。

| Split / 专家 | AUC（fake 方向） | balanced accuracy | RAISE 真图 specificity | FLUX recall | SD3.5 recall | Brier score |
|---|---:|---:|---:|---:|---:|---:|
| calibration / FSD | 0.742 | 0.605 | 0.810 | 0.360 | 0.440 | 0.250 |
| screening / FSD | 0.700 | 0.603 | 0.770 | 0.360 | 0.510 | 0.250 |

失效 AIDE 分数参与了原 `calibration_report.json` 和 `calibrated_scores.jsonl`，其中 AIDE 指标及两专家互补性均无效；FSD 的独立校准与指标仍可用。FSD 的阈值与竖幅图错误分析见 [失败分析](STAGE1_FAILURE_ANALYSIS.md)。专家角色与 `E_base` / `E_extra` 尚未冻结；Stage 2 暂不启动。

原始分数和失效派生文件保留供追溯；正确顺序的 AIDE 重评分及校准见第 8 节。

## 8. 正确顺序 AIDE 重评分与 Stage 1 判断（2026-09-29）

旧 AIDE 运行脚本在远端按原哈希留档；修正脚本上传后，两个独立 RAISE 单图 smoke 的 logits 完全一致。正确顺序的 600 条新评分位于服务器结果目录 `aide_official_order.jsonl`，本地同名副本 SHA-256 为 `fca61f5379060433aac62964ebf994786c23bf81de7162645363641a0220a0c1`；对应元数据含 `input_order=dct4_then_original`。样本 ID 唯一并与 FSD 清单对齐，`--check-only` 为完成 600、待评分 0，进程退出后显存 0 MiB。原 `aide.jsonl` 和旧校准文件仍是失效历史，不参与新结论。

| AIDE / split | AUC（fake 方向） | balanced accuracy | RAISE specificity | FLUX recall | SD3.5 recall |
|---|---:|---:|---:|---:|---:|
| 默认阈值 / calibration | 0.561 | 0.603 | 0.300 | 0.890 | 0.920 |
| 默认阈值 / screening | 0.558 | 0.595 | 0.280 | 0.910 | 0.910 |
| 类别均衡校准 / calibration | 0.561 | 0.550 | 0.320 | 0.750 | 0.810 |
| 类别均衡校准 / screening | 0.558 | 0.593 | 0.380 | 0.800 | 0.810 |

校准仍只拟合 calibration，screening 独立评估；新参数与逐样本概率在本地 `runs/stage1-bfree-screen-20260928/scores/calibrated_official_order/`，其中 `calibration_report.json` SHA-256 为 `1595787e7e40c556eb4440d9f8325231d1084cc0b32d39006acecbbbf630bcb7`。AIDE screening 总体 AUC 0.558，其中 FLUX vs RAISE AUC 0.486、SD3.5 vs RAISE AUC 0.630。它能补到一部分 FSD 漏掉的假图，但两位专家各有明显类别偏向，未达到预设的独立可靠性门槛。FSD 的诊断阈值与竖幅来源组失效、正确顺序两专家错误互补性见 [失败分析](STAGE1_FAILURE_ANALYSIS.md)。按 Stage 0 停止规则，`E_base` / `E_extra` 尚不冻结，Stage 2 暂不启动。
