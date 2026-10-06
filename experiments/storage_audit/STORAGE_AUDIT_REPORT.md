# AutoDL 存储盘点、清理与扩容建议

盘点日期：2026-10-05（Asia/Shanghai）  
状态：只读审计、限定清理、清理后核验均完成；未执行数据盘扩容。  
最后核验主机：`autodl-container-sbhn4u78c0-c07a45ba`，AutoDL SSH 端口 `15279`。该地址是本次核验入口，不视作永久地址。

## 摘要

AutoDL 数据盘为独立 50 GiB XFS，清理前使用率 98%、只剩 1.5 GiB。按预先列出的清理清单删除了四个旧下载 partial、1,500 张已完成实验的远端 crop 副本和 126 个 pip 缓存文件。清理后剩余 2.8 GiB（约 5%，95% 已用），`df -B1` 可用空间增加 1,362,989,056 bytes（约 1.27 GiB）。原始数据、模型、权重、冻结清单、逐图结果和报告均保留。

**扩容结论：`EXPANSION RECOMMENDED`。** 按本方案的阈值，清理后仍低于 10 GB，且当前主要空间由要保留的数据与模型占用。建议在启动新的多工具或模型训练阶段前把数据盘从 50 GB 扩至约 100 GB（增加 50 GB）；本轮没有代为购买或扩容。

## A. 磁盘状态

| 文件系统 | 挂载点 | 清理前 | 清理后 | 说明 |
|---|---|---:|---:|---|
| 系统盘 overlay | `/` | 30G 总量，11G 已用，20G 可用，35% | 30G 总量，11G 已用，20G 可用，35% | 未迁移缓存；系统盘可用空间高于数据盘。 |
| 数据盘 XFS `/dev/md0` | `/root/autodl-tmp` | 50G 总量，49G 已用，1.5G 可用，98% | 50G 总量，48G 已用，2.8G 可用，95% | inode 使用率约 3%，瓶颈是容量而非 inode。 |

清理后 `df -B1`：总量 `53,687,091,200` bytes；已用 `50,750,656,512` bytes；可用 `2,936,434,688` bytes。清理前可用 `1,573,445,632` bytes。

系统盘虽有约 20G 可用，但 Qwen pinned 模型约 17G。把完整模型搬到系统盘会把系统盘剩余压至约 2–3G，故本轮没有迁移。`/root/.cache/huggingface` 不存在；`/root/.cache/pip` 约 3.3G 且位于系统盘，当前不影响数据盘空间，予以保留。

## B. 清理后最大的 20 个目录

以下为 `du -x -h --max-depth=3 /root/autodl-tmp` 的最大路径；父目录与子目录同时列出，数值有包含关系，**不能把各行相加**。

| 大小 | 路径 |
|---:|---|
| 400M | `/root/autodl-tmp/toolbox_screening/venv/lib` |
| 401M | `/root/autodl-tmp/probe-dinov2-bfree-20261001/deps/probe` |
| 416M | `/root/autodl-tmp/probe-dinov2-bfree-20261001/deps` |
| 482M | `/root/autodl-tmp/actor0-bfree-20261002/data/eval` |
| 490M | `/root/autodl-tmp/probe-dinov2-bfree-20261001/data` |
| 490M | `/root/autodl-tmp/probe-dinov2-bfree-20261001/data/probe_eval_data` |
| 778M | `/root/autodl-tmp/actor0-bfree-20261002/data` |
| 1.2G | `/root/autodl-tmp/toolbox_screening/torch_home` |
| 1.2G | `/root/autodl-tmp/toolbox_screening/torch_home/hub` |
| 1.9G | `/root/autodl-tmp/toolbox_screening` |
| 3.4G | `/root/autodl-tmp/probe-dinov2-bfree-20261001/weights/aide` |
| 4.6G | `/root/autodl-tmp/probe-dinov2-bfree-20261001/weights` |
| 6.0G | `/root/autodl-tmp/probe-dinov2-bfree-20261001` |
| 17G | `/root/autodl-tmp/actor0-bfree-20261002/model-cache-xet` |
| 17G | `/root/autodl-tmp/actor0-bfree-20261002/model-cache-xet/hub` |
| 18G | `/root/autodl-tmp/actor0-bfree-20261002` |
| 23G | `/root/autodl-tmp/SAFE_official_data/DiTFake_repo/DiTFake` |
| 23G | `/root/autodl-tmp/SAFE_official_data/DiTFake_repo` |
| 23G | `/root/autodl-tmp/SAFE_official_data` |
| 48G | `/root/autodl-tmp` |

清理前完整深度统计、cache 大文件列表和挂载信息见 [只读盘点原始输出](2026-10-05_readonly_inventory.txt) 及 [定向盘点](2026-10-05_targeted_inventory.txt)。

## C. 空间占用分类

### 必须保存

- SAFE 官方 DiTFake 数据：约 23G、30,000 张图；本轮作为原始数据保留。
- PROBE/B-Free 冻结数据与权重：约 490M 图像副本、4.6G 权重；保留数据清单、结果、环境和权重。
- Actor-0：480 张冻结 dev/eval 图像副本约 778M、逐图轨迹和评分，以及 pinned Qwen3-VL 完整缓存约 17G；保留模型和所有核心结果。
- toolbox screening：约 1.9G，含 RIGID 环境、Provenance 工具、输出和日志；保留结果、工具版本和失败记录。
- SAFE patch 诊断的 `patch_output/scores.csv`、metrics、运行日志、`metadata.csv`、`crop_sha256.txt` 和报告均保留。远端 patch 输出目录清理后约 928K。

### 可重新生成

- SAFE Patch Coverage 的 1,500 张 512×512 crop 是中间图。远端副本已清理；本地 [SAFE_patch_diagnostic](../../SAFE_patch_diagnostic/) 仍保存全部 1,500 张图、坐标和 SHA 清单、抽样原图、原图清单和脚本。逐张 SHA 校验为 1,500/1,500 通过。
- 未来 PROBE Evidence 的临时 crop、特征和可视化按实验完成后可再生，建议只长期保留 bbox/坐标、feature metadata、Evidence Card 和 Top-3 审计 crop。

### 缓存

- 已清除的 Qwen `.incomplete` 是失败下载片段，不是模型权重；完整 pinned 模型在独立 `model-cache-xet` 路径中。
- `/root/autodl-tmp` 的 PROBE pip cache 已清除；系统盘 `/root/.cache/pip` 约 3.3G，因数据盘是当前瓶颈且系统盘仍有约 20G 可用，暂时保留。
- 没有清除完整 Qwen、PROBE 或 SAFE 权重缓存；它们虽然能重新获取，但下载时间和网络失败重试成本较高。

### 重复文件

- 未因文件名相同删除任何数据。SAFE patch 的远端副本是本地 1,500 张 crop 的副本：远端 `crop_sha256.txt`、`metadata.csv`、`scores.csv` 的 SHA-256 与本地归档对应文件分别一致；本地 1,500 张 crop 逐张 SHA-256 全部通过，因此只删除远端副本。
- 当前 AutoDL 保留的图像集包括 PROBE 300 张、Actor-0 480 张、SAFE DiTFake 30,000 张；保留各自 manifest 和路径。没有对全部 30,000 张 SAFE 图像与 B-Free 图像做跨数据集全量 SHA 配对，因此不宣称全盘不存在内容重叠，也未执行原始数据集去重。

## D. 实际清理

| 路径 | 原大小 | 操作 | 结果 |
|---|---:|---|---|
| `/root/autodl-tmp/actor0-bfree-20261002/model-cache/.../blobs/*.incomplete` | 4 个文件，608,174,080 bytes | 删除已过期且未完成的下载片段；保留完整模型和目录结构。 | `.incomplete` 残留 0。 |
| `/root/autodl-tmp/SAFE_patch_diagnostic/cropped_images/` | 1,500 个文件，657,821,604 bytes | 删除已完成诊断的远端中间 crop 副本；本地同一组图像及逐图 SHA 保留。 | 目录移除；远端 scores/metadata/log/hash 保留。 |
| `/root/autodl-tmp/probe-dinov2-bfree-20261001/pip-cache/` | 126 个文件，93,485,218 bytes 文件内容 | 删除安装包缓存文件；已安装环境未改动。 | 缓存文件残留 0。 |

`df -B1` 的可用空间净增 `1,362,989,056` bytes（约 1.27 GiB）。完整候选依据在 [cleanup_candidates.md](cleanup_candidates.md)；执行与中止尝试日志见 [清理日志](2026-10-05_cleanup_execution_retry2.txt)、[第一次未执行日志](2026-10-05_cleanup_execution.txt)、[第二次未执行日志](2026-10-05_cleanup_execution_retry1.txt) 和 [校验原因检查](2026-10-05_cleanup_abort_inspection.txt)。前两次尝试分别因远端未提供 `python3`、pip cache 目录大小与普通文件字节和有 18,554 bytes 目录项差值而在删除前中止，未改动任何目标。修正后第三次通过全部前置校验并完成清理。

另有 16,384 bytes 的 `toolbox_screening/bin/c2patool-v0.28.1.stalled.part` 保留；它很小，相关下载失败日志仍在，清理它不会实质改善空间。

## E. 扩容判断

**`EXPANSION RECOMMENDED`**。

清理后只剩 2.8G，低于方案的 10 GB 阈值；占用主体是 SAFE 原始数据、完整模型缓存、PROBE 权重和实验文件，删除它们会损害复现或提高后续下载风险。建议把数据盘 **增加 50 GB，扩至约 100 GB**，在保留当前数据的同时为 Evidence features、少量审计图、SFT checkpoint 和 Monitor 轨迹留出工作空间。此数值是存储容量规划，不是购买操作；需要用户在 AutoDL 控制台确认。

## F. 下一阶段与长期结构

- **PROBE Evidence v1**：将源图路径、bbox、patch metadata、reference features 和 Evidence Card 作为主要持久产物；最多保留 Top-3 与最终审计 crop，全部中间 patch PNG 放入 scratch 并在哈希/指标核验后清理。
- **Actor SFT**：复用当前约 17G 的 pinned Qwen 缓存；优先按已确定的训练策略只保留最终 adapter/checkpoint、配置和日志。若采用全量 SFT，单份权重已是约 17G 量级，optimizer state 和多份 checkpoint 会显著增大空间需求，因此必须先估算保存点数量并保证扩容后有足够余量。
- **Monitor**：优先保存结构化轨迹表、干预账本、预测、metrics 和配置哈希；不要按每个实验再次复制完整图像集或基础模型。
- 后续目录建议为 `/root/autodl-tmp/{datasets,manifests,checkpoints,experiments,scratch}`，每个数据集只留一个规范副本，实验通过 manifest、相对路径和 SHA 引用。现有目录暂不重排，以免改变已冻结运行路径。
- Hot 数据留本地数据盘；Warm 数据（规范数据集、清单、最终模型和结果）在后续共享存储可用时集中管理；Cold 历史运行归档到 NAS/对象存储/大容量盘。当前没有核验可用的外部归档服务，因此本轮没有迁移或假设有备份。

## 验证与边界

- 清理前后主机身份均为 `autodl-container-sbhn4u78c0-c07a45ba`；`/root/autodl-tmp` 明确挂载在独立 `/dev/md0` XFS 数据盘。
- 清理后 SAFE 原始 30,000 张图、Actor-0 480 张数据、PROBE 300 张数据、完整 Qwen/PROBE 权重、Actor 轨迹和 SAFE patch raw scores 均存在；清理目标残留均为 0。
- 进程检查未见模型推理或实验任务，仅有 AutoDL 的 Jupyter、TensorBoard 和面板服务。`nvidia-smi -L` 此时未枚举 GPU；本存储任务没有运行任何 GPU 作业。
- 没有移动模型、改变环境变量、改写 manifest、删除原始图像或运行扩容操作。
