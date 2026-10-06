# SAFE 独立校准与筛查结果

**日期：2026-09-29**  
**结论：未通过预设 Stage 1 可行性门槛；专家角色继续暂停冻结。**

## 设计与完整性

按[评分前冻结的方案](STAGE1_SAFE_INDEPENDENT_SCREEN_PLAN.md)，从未使用的 800 个 B-Free source groups 中，以种子 `2026092910` 分层抽取 100 组 calibration 与 100 组 screening；每组横幅 70、竖幅 30。旧 Stage 1 的 200 组及 SAFE 探索性 30 组均被排除。calibration 仅评分 100 张 RAISE 真图；screening 评分 100 张 RAISE 真图与各 100 张 FLUX、SD3.5 假图，总计 400 张。仅从本地既有两份官方 ZIP 提取原始 PNG，没有新下载或生成。未来 Stage 2–4 仍有 600 个未用组。

两份源 ZIP 的官方 MD5 与既有 SHA-256 均匹配；1,000 个三类同名 source groups 配对一致。400 张原图合计 679,805,435 字节，本地和新 AutoDL 实例均逐图核对了清单 SHA-256；设计摘要为 `c85058042c7e3b9268e334bc71efdeab267d1e3954fde36af0265ca065d8335e`，清单摘要为 `ceb396cbf9a78d2aa04a4e77307e6062e4486de900b6c8bd12be13f7732fcc58`。SAFE 官方提交与权重同[探索记录](STAGE1_SAFE_TRIAGE.md)，权重 SHA-256 `b3f5ecfb46a154ed553aaaf4bf3ba59182310726ddb0cbb1fe42bd0e22d2f20e`。原图 RGB、中心裁剪 256×256、`ToTensor()` 和 `softmax(logits)[1]` 未变。

100 条 calibration 分数 SHA-256 为 `366081cf3e026cc09eafe46612f9246e37c43c92022a77a610596fcbd23c6ed3`。仅用这 100 张真图，按第 80 个升序 fake 分数的 `nextafter(+∞)` 冻结阈值 **0.9561132788658143**，校准集真图判对 80/100。阈值文件在筛查评分前写入并上传，SHA-256 `c8104c12a705041dff0594fc011823bad11f36ed6f60e9c35dcab905773413f2`。随后一次性评分 300 张 screening 图；分数文件本地/远端 SHA-256 同为 `5bb6b46bb8eab5862d43354716388fb24384a83be8a30160354474ac6d41f735`，300 条无缺失。报告由预设规则直接计算，没有在 screening 上搜索阈值。

## 独立筛查

| 指标（screening） | 官方阈值 0.5 | 冻结阈值 0.9561132788658143 | 预设门槛 |
| --- | ---: | ---: | ---: |
| RAISE 真图判对 / 100 | 17 | **82** | ≥80 |
| RAISE 真图误报 / 100 | 83 | **18** | ≤20 |
| FLUX 假图判对 / 100 | 100 | **25** | ≥70 |
| SD3.5 假图判对 / 100 | 96 | **27** | ≥70 |
| balanced accuracy | 0.575 | **0.540** | 描述性指标 |

连续分数总体 AUC **0.655**，分 FLUX **0.6923**、SD3.5 **0.6177**；阈值移动不改变 AUC。冻结阈值下，横幅真图 57/70 判对（81.4%），竖幅 25/30 判对（83.3%），均未触发低于 70% 的方向警讯。两类假图召回均远低于门槛，因此 **SAFE 未通过**；真图误报能压到目标以下，但在固定阈值下几乎丧失所需的假图识别能力。

这一判断仅适用于本 B-Free 的 RAISE 真图与 FLUX、SD3.5 整图生成配置。RAISE 与生成图尺寸和宽高比不同，AUC 也不能被解释为跨来源泛化。100 个真图组和各 100 张假图是粗筛，不是正式论文测试集。本轮不据此再调阈值，也不进入 Stage 2；下一步需讨论是否更换公开候选或重新审视 Stage 1 专家角色要求。

## 文件与服务器状态

本地清单、分数、阈值和机器可读报告位于 `runs/stage1-safe-independent-20260929/`；选择/提取、评分、汇总脚本分别是 `scripts/prepare_stage1_safe_independent.py`、`scripts/score_stage1_safe_independent.py`、`scripts/summarize_stage1_safe_independent.py`。远端数据盘目录为 `/root/autodl-tmp/trajectories/stage1-safe-independent-20260929/`。新实例通过现有 SSH 密钥只读交接核验了旧清单、探索结果、SAFE 官方包和权重；既有未提交工作未改动。推理完成后无 GPU 进程，显存 0 MiB、利用率 0%，可以关卡。
