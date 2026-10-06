# Stage 1 失败后的低成本候选复核

**日期：2026-09-29**  
**状态：SAFE 官方权重与单卡执行链核验完成；30 组探索和后续独立筛查已完成，独立筛查未通过；见 [结果](STAGE1_SAFE_INDEPENDENT_SCREEN_RESULT.md)**

## 结论

当前 FSD + AIDE 未通过 Stage 1。新候选不能凭论文总体成绩直接替换 AIDE；先核对**具体发布检查点**在相近生成器和真图来源上的证据，再限定下载、适配与单图运行成本。最初的无卡资料审计中，两条 SAFE 权重下载路由仅得到 32 KiB，半成品已清理；后续经用户确认，改用官方 GitHub API 取得完整权重并完成独立目录中的单卡 smoke，详见文末续核记录。最初审计时剩余 800 个 source groups 未使用；之后 SAFE 独立校准/筛查用了 200 组，目前剩余 600 组。

| 候选 | 与目标任务相关的公开证据 | 发布、许可和成本 | 决定与缺口 |
|---|---|---|---|
| [SAFE](https://github.com/Ouxiang-Li/SAFE) | [论文](https://arxiv.org/html/2408.06741v2) 的 DiTFake Table 6 报告 FLUX.1-schnell 99.3% ACC / 99.9% AP、SD3-medium 99.4% ACC / 99.9% AP；**99.9% 是 AP，不是 AUC**。训练集为 CNNDetection/ProGAN，和当前 RAISE/FLUX/SD3.5 已知来源不同。 | 官方仓库 Apache-2.0，提供 `checkpoint/checkpoint-best.pth`，GitHub 显示 5.57 MB；官方评估脚本默认 4 GPU、批量 256，需在不改变预处理和分数定义的条件下做单卡最小推理适配。 | **仅列为低成本优先核验候选**。论文 DiTFake 真图来自 COCO，约 640×480，假图为 1024×1024；分辨率/来源混杂可能抬高结果。SD3-medium 也不是 SD3.5。必须在匹配处理的新 RAISE 来源组上独立验证，不能把论文数字视为本项目效果。 |
| [SPAI](https://github.com/mever-team/spai) | [论文](https://arxiv.org/html/2411.19417) 在 5 种真图来源上报告 FLUX AUC 83.0%、SD3 AUC 75.9%；训练用单一 LDM 假图和真实图。真图来源含 RAISE，但该论文结果不是当前 B-Free 配对样本结果。 | 官方代码和权重声明 Apache-2.0；公开推理入口，作者称推理显存低于 8 GB。权重由 Google Drive 提供，实际文件大小与可达性尚未核验。 | **备选，暂不下载**。其 FLUX/SD3 与本项目 FLUX/SD3.5 版本不同，发布权重的传输成本未知；SAFE 的便宜核验失败或证据不够时再讨论。 |
| [FGTS](https://github.com/hzlsaber/FGTS) / [GenShield](https://github.com/zhipeixu/GenShield) | FGTS 公布跨生成器结果，但已发布线性探针都依赖 DINOv3-7B；GenShield 基于 BAGEL-7B-MoT，仓库推理说明要求另备训练后的检测检查点。 | 两者代码许可分别为 MIT / Apache-2.0；完整主干与存储、部署成本明显高于小型候选。 | **不进入本轮低成本尝试**。 |
| [CLIP-Cues](https://github.com/marco-willi/clip-cues) | 仓库明确有以 SynthBuster+ 训练的检查点，数据由 RAISE 及较新生成器构成。 | 权重/代码 MIT；CLIP 主干另需下载。 | **不用于当前 B-Free 独立筛选**：训练来源可能和本项目的 RAISE/FLUX/SD3.5 数据重叠，逐图排除前无法宣称独立。 |

## SAFE 静态推理路径核对（2026-09-29）

- 官方 [`main_finetune.py`](https://github.com/Ouxiang-Li/SAFE/blob/main/main_finetune.py) 的 `SAFE` 分支构建其自定义 `models.resnet.resnet50(num_classes=2)`；该模型实际上只实例化前两组残差层，前向先执行一级 DWT 高频变换。因此 5.57 MB 发布文件的规模与源码结构并不矛盾；当时尚未拿到完整文件做严格权重键核对。
- 官方 [`data/datasets.py`](https://github.com/Ouxiang-Li/SAFE/blob/main/data/datasets.py) 在 `transform_mode=crop`、`input_size=256` 的评估路径上用 RGB、中心裁剪 256×256、`ToTensor()`；标签目录为 `0_real` / `1_fake`。单图核验必须沿用这一路径，不能为了适应当前图像尺寸而另行缩放。
- 官方 [`scripts/eval.sh`](https://github.com/Ouxiang-Li/SAFE/blob/main/scripts/eval.sh) 默认 4 进程、每进程批量 256，但主程序只在 `args.distributed` 时包装 DDP；单卡推理路径在源码层面存在，仍需完整检查点验证。
- 再试 GitHub 的官方另一路由，20 秒仍只得到 32 KiB；已停止并删除半成品。两个官方 URL 均表现为首块后停滞，当时无法核验完整权重 SHA-256 和严格加载。搜索到第三方镜像，但文件名/大小不同，未把它视为官方检查点。

## 建议的成本上限与停止点

1. 先解决官方 SAFE 5.57 MB 检查点的可核验获取；不迁移大量数据，不安装整套旧训练环境。2026-09-29 两条官方 GitHub 路由分别在 30 秒和 20 秒仅取得 32 KiB，半成品均已清理；不继续在慢连接上耗时，也不用未核对来源的第三方权重。取得完整官方文件后再核对摘要、权重键和单卡载入。
2. 需要 GPU 时，先向用户报告具体估计时段。先运行**最多 3 张非评分图**确认严格加载、预处理、分数方向、耗时和峰值显存；超过预定单图时限或出现异常就停止，不直接运行 600 张。
3. 只有执行链可靠，再与用户确定新 source groups 的数量和用途、真/假统一处理、预先固定的准入指标及停止门槛。已分析的 600 张仅可作探索诊断，不能重复用作独立性能证明；其余 800 组原定留给 Stage 2/3/4，未经讨论不挪用。

目前没有合格的新专家，也没有冻结 `E_base` / `E_extra`。若低成本核验不能找到有说服力的第二专家，应讨论调整最小证据栈与研究设计，而不是继续轮换模型。

## SAFE 官方检查点与单卡续核（2026-09-29）

- 固定官方提交 `4e998724651b227def64f5be0cd60c0aa1552c35`。检查点为 5,840,638 字节，Git blob SHA-1 `21e7aceb520a44ffcdf09234aae8f02b5986f80a`，SHA-256 `b3f5ecfb46a154ed553aaaf4bf3ba59182310726ddb0cbb1fe42bd0e22d2f20e`；官方源码包两端 SHA-256 均为 `5ae8f3da27333d6dbd1065a81adbab095db9cf9d38e87c21c4aaaf59fded7f2a`，包内检查点 Git blob 哈希一致。未使用第三方镜像。
- 本地 `scripts/smoke_safe.py` 只调用官方 `models.resnet.resnet50(num_classes=2)`，读取检查点 `model` 字段并以 `strict=True` 载入。依照官方评估路径执行 RGB、256×256 中心裁剪、`ToTensor()`；第二类由官方 `0_real` / `1_fake` 目录及 `engine_finetune.py` 的 `softmax(..., axis=1)[:, 1]` 核对为 fake 分数。CPU 严格加载通过。
- 远端仅在新目录安装 `pytorch-wavelets==1.3.0` 和 `PyWavelets==1.9.0`，复用已有隔离目录的 `kornia==0.7.2`。两张非评分展示图单卡前向成功：AIDE 的 `Chameleon.jpg` fake 概率 0.47322，预处理/前向约 0.262/0.312 秒；FSD 的 `teaser.jpg` fake 概率 0.01432，约 0.101/0.004 秒。后者为热启动；推理期 PyTorch 峰值分配约 27.4 MiB，不代表完整显存峰值或批量成本。进程退出后显存与利用率均为 0。
- 两张展示图的真实标签、任务适用范围及独立性均不用于性能判断。截至单图 smoke 结束时，未在 B-Free 的 600 张上评分，剩余 800 个来源组也未动用。随后用户确认在既有 200 组中做 30 组探索性早停，见 [SAFE 30 组记录](STAGE1_SAFE_TRIAGE.md)；当前 SAFE 仍**未通过 Stage 1 准入**。
