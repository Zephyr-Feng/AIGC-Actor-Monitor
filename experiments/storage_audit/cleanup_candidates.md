# AutoDL 清理候选与保留依据

盘点日期：2026-10-05（Asia/Shanghai）  
已核验主机：`autodl-container-sbhn4u78c0-c07a45ba`  
当前阶段：审计、窄范围清理和清理后核验已完成。

## 已确认的清理项

| 路径 | 盘点大小 | 类型 | 可删除依据 | 已完成报告/依赖 | 拟执行操作 |
|---|---:|---|---|---|---|
| `/root/autodl-tmp/actor0-bfree-20261002/model-cache/models--Qwen--Qwen3-VL-8B-Instruct/blobs/*.incomplete`（4 个文件） | 608,174,080 bytes | 不完整的 Hugging Face 下载缓存 | 文件修改时间为 2026-10-02；该缓存下没有完整 snapshot；Actor 推理使用的完整 pinned 模型位于独立 `model-cache-xet`（约 17 GB）。没有下载/推理进程运行。只删这 4 个 `.incomplete` 文件，保留缓存目录、锁文件、模型和相关日志。 | Actor-0 报告和模型哈希记录已保存；完整模型缓存保留。 | **已执行**：删除 4 个不完整 blob；清理后确认残留为 0。 |
| `/root/autodl-tmp/SAFE_patch_diagnostic/cropped_images/` | 657,821,604 bytes；1,500 张 | 可重建的实验中间 crop | SAFE patch 诊断已完成；原图清单、坐标元数据、crop SHA-256、模型 raw scores、运行日志和报告保留。工作区本地有完全相同的 1,500 个 crop 文件，且 1,500/1,500 个本地 crop SHA-256 均匹配；本地抽样原图也保留。远端没有实验进程依赖这些 crop。 | [SAFE patch 报告](../../SAFE_patch_diagnostic/REPORT.md)、`metadata.csv`、`crop_sha256.txt`、`patch_output/scores.csv` 等均保留；本地 crop 副本保留。 | **已执行**：删除远端 1,500 个 crop 文件及空目录；scores、metadata、logs、hash 文件保留。 |
| `/root/autodl-tmp/probe-dinov2-bfree-20261001/pip-cache/` | 93,485,218 bytes；126 个文件（目录总 apparent size 93,503,772 bytes） | 可重新下载的 pip 缓存 | 只存安装包缓存；已安装依赖留在独立环境目录；没有运行中的安装任务。 | 代码、权重、依赖环境和全部实验结果另处保留。 | **已执行**：删除 126 个缓存文件；清理后确认残留为 0，保留空目录结构。 |

## 明确保留

| 路径 | 大小 | 分类与理由 |
|---|---:|---|
| `/root/autodl-tmp/SAFE_official_data/DiTFake_repo/DiTFake/` | 约 23 GB | 原始实验数据集，唯一远端全量副本；保留。 |
| `/root/autodl-tmp/actor0-bfree-20261002/model-cache-xet/` | 约 17 GB | Actor-0 完整 pinned Qwen3-VL 权重缓存；可重新下载但成本高，后续可复用；保留。 |
| `/root/autodl-tmp/probe-dinov2-bfree-20261001/weights/` | 约 4.6 GB | PROBE 与旧专家权重；研究推理依赖，保留。 |
| `/root/autodl-tmp/toolbox_screening/` | 约 1.9 GB | RIGID/Provenance 工具环境、源码、逐图结果和失败日志；保留。 |
| `/root/autodl-tmp/actor0-bfree-20261002/data/` | 约 778 MB；480 张 | Actor-0 冻结 dev/eval 图像及实验副本；与 manifest/轨迹可审计关联，保留。 |
| `/root/autodl-tmp/probe-dinov2-bfree-20261001/data/` | 约 490 MB；300 张 | PROBE 冻结评测数据副本及 manifest；保留。 |
| `/root/.cache/pip/` | 约 3.3 GB | 仅在系统盘，不占数据盘；当前系统盘仍有约 20 GB 可用，暂不清理。 |

未基于文件名判断重复，也未删除任何原始数据、冻结清单、权重、最终报告、逐图分数或关键轨迹。Actor-0 与 PROBE 的图像清单分属不同冻结来源组；未做全量文件级去重，也不通过移动数据改变现有 manifest 路径。

## 执行边界

- 删除前重新核对主机名、目标绝对路径、文件数量和字节数。
- 只删除表格中列明的缓存文件与 crop 文件；不使用未限定路径的递归删除。
- 操作后重新核对数据盘可用空间及清理项是否仍有残留，并把实际释放量写入最终报告。
- 不移动大模型至系统盘，不更改缓存变量，不执行 AutoDL 扩容。

## 本次执行记录

- 第一次尝试使用默认 `python3`，远端命令因 `PATH` 中不存在该程序立即退出；没有执行删除。
- 第二次在精确目标检查阶段发现 pip cache 的目录总字节数比普通文件总和多 18,554 bytes（目录项开销）；全部目标均未删除。
- 第三次改用已记录的 `/root/miniconda3/bin/python`，按普通文件总和修正 pip cache 校验后执行。删除前主机、目标绝对路径、4 个 partial 的名称/年龄/大小、1,500 个 crop 的数量/大小、126 个 pip cache 文件的数量/大小全部匹配。
- 清理前数据盘可用 1,573,445,632 bytes；清理后可用 2,936,434,688 bytes，`df -B1` 空闲空间增加 **1,362,989,056 bytes**（约 1.27 GiB）。所有清理目标残留为 0。
- `toolbox_screening/bin/c2patool-v0.28.1.stalled.part`（16,384 bytes）保留：仅占少量空间，失败日志已归档，无需为此改动工具证据目录。
- 命令输出日志分别保存在 `2026-10-05_cleanup_execution.txt`、`2026-10-05_cleanup_execution_retry1.txt`、`2026-10-05_cleanup_abort_inspection.txt`、`2026-10-05_cleanup_execution_retry2.txt`。
