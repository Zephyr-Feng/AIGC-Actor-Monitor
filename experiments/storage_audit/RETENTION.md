# 项目实验数据保留策略

日期：2026-10-05  
适用范围：AutoDL `/root/autodl-tmp` 上的当前 SAFE、PROBE、PatchCraft/RIGID/Provenance 和 Actor-0 归档，以及后续 PROBE Evidence v1、Actor SFT、Monitor 阶段。

## KEEP：必须长期保留

- 原始数据集及来源/许可说明；当前 SAFE DiTFake 全量数据、冻结评测样本均保留。
- 冻结 manifest、source-group 映射、样本 ID、相对路径和图像 SHA-256。
- 每个实验的固定配置、prompt、checkpoint/revision 和权重摘要。
- 逐图 raw scores、工具输出、关键 trajectory、最终 metrics、日志、失败记录和 `REPORT.md`。
- 最终训练 checkpoint；在本项目使用的 pinned Qwen、PROBE、SAFE 等模型缓存暂时保留，因为网络重下成本高且后续研究还会复用。

## REGENERABLE：有重建信息时可在报告完成后清理

- 全量 patch/crop PNG、processed-image 副本、临时 feature 张量、debug dump 和中间可视化。
- 保留原图路径、bbox/坐标、预处理配置、代码版本与 SHA；只留少量明确用于人工审计的样本图。
- SAFE Patch Coverage 的 1,500 个远端 crop 已删除；本地工作区仍保存 1,500 个 crop，且全部 SHA-256 核验通过。远端 scores、metadata、hash 清单、日志和报告仍在。

## DELETE：确认不再运行且日志/最终结果已留存后清理

- 失败下载留下的 `.incomplete` 文件和 pip 下载缓存。
- 实验完成后的空临时目录、临时传输片段和重复生成的调试图。
- 本次已清理：4 个 Actor-0 模型 `.incomplete` 文件、126 个 PROBE pip cache 文件，以及 1,500 个远端 SAFE patch crop 副本。
- 不按文件名相同推断重复；若准备删除重复图像，先比较 SHA-256，再确认 manifest、脚本及运行配置不依赖独立路径。

## 目录与热/温/冷数据建议

在不改变现有路径依赖的前提下，后续逐实验采用：

```text
/root/autodl-tmp/
├── datasets/<source>/           # 唯一规范数据集副本
├── manifests/<experiment>/      # 冻结清单、source group、hash
├── checkpoints/<model>/         # pinned/final checkpoint
├── experiments/<run>/           # config、raw、metrics、logs、report
└── scratch/<run>/               # 可再生 crop/features/temp
```

- **Hot**：当前 subset、当前模型和临时 feature 放本地数据盘；实验完成后按本文件清理 `scratch`。
- **Warm**：多个实验复用的数据、清单、最终模型/指标放共享存储或有独立备份的位置；当前 AutoDL 数据盘保留一份工作副本。
- **Cold**：历史完整 run、过期模型缓存和原始备份转至本地 NAS/对象存储/大容量归档介质；目前未核验这些服务是否已配置，因此本报告不假设它们可用。

跨服务器传递 manifest、config/checkpoint SHA、git commit 和相对路径；避免每个实验再复制整份数据集。PROBE Evidence v1 保留 reference features、patch metadata、bbox、Evidence Card 和 Top-3 审计 crop，不长期保存全部 patch PNG。
