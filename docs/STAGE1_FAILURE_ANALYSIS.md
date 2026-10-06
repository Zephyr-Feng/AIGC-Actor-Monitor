# Stage 1 失败分析（2026-09-29）

**范围**：固定清单 200 个 source groups，每组 1 张 RAISE 真图、1 张 FLUX 假图、1 张 SD3.5 假图；100 组 calibration、100 组 screening。FSD、旧失效 AIDE、新 AIDE 评分文件的 SHA-256 分别为 `f2caf2eafa95225807f68812c62c68b4d776cff5191a1ae3574d731420be04dd`、`683c0d60b3c9490345dbe81e199bf8b10264ef6dd381b61e9436226ec3ea1ea4`、`fca61f5379060433aac62964ebf994786c23bf81de7162645363641a0220a0c1`。分析不改变已冻结清单或 Stage 1 准入规则。

## 1. AIDE 推理输入顺序错误

官方 AIDE 源码 zip SHA-256 `ac10669273d8742b667cdacbd772a0d749d56851ecff00779fd0852bf492797e`。其中 `data/datasets.py` 的 `TrainDataset`、`TestDataset` 均返回 `[x_minmin, x_maxmax, x_minmin1, x_maxmax1, x_0]`，`models/AIDE.py` 的 `AIDE_Model.forward` 按前四路 DCT、第五路原图读取。此前误判官方顺序，将本项目 `prepare_image` 改为原图第一路。因此后续 600 张 AIDE 原始分数、校准概率和错误互补性均**无效**；不能据此说 AIDE 接近随机或应被淘汰。2026-09-28 最早两次 Chameleon smoke 使用的是官方顺序，只验证可运行性。

`scripts/smoke_aide.py` 已恢复官方顺序；批量入口复用该函数，并在 AIDE 运行元数据记录 `dct4_then_original`。校准入口拒绝没有该标记的旧评分；已验证旧 `aide.jsonl` 被拒。远端旧脚本以原 SHA-256 保存于结果目录 `invalid_run_scripts/`，新脚本哈希核对通过。正确顺序结果写入新文件 `aide_official_order.jsonl`，旧结果原样保留。

## 2. FSD 原始评分与校准

FSD 官方 `FSDDetector.score` 使用 `z_score < -2` 作为 fake 默认判定；本项目取 `-z_score` 为分数方向，方向正确。600 行分数、标签和图像 SHA-256 与清单逐项一致，样本 ID 唯一、分数有限、默认标签与阈值公式一致。官方 `compute_fsd` 将输入转灰度，对残差把短边缩放至 1024，再中心裁到 1024×1024。

| 规则 | calibration balanced accuracy | screening balanced accuracy | screening 真图 specificity | screening 假图 recall |
|---|---:|---:|---:|---:|
| 官方默认 `-z_score > 2` | 0.530 | 0.520 | 0.040 | 1.000 |
| 已记录的类别均衡逻辑校准，概率 ≥ 0.5（等价 `-z_score ≥ 7.567`） | 0.605 | 0.603 | 0.770 | 0.435 |
| **诊断用** calibration 最佳 balanced accuracy 阈值 `-z_score ≥ 5.389` | 0.743 | 0.680 | 0.560 | 0.800 |

最后一行只在 calibration 搜索所有相邻分数中点并选取最优值，随后在 screening 读取结果；这是看过原筛查表现后做的探索性敏感性分析，**不是新的预注册准入结果**。其 screening FLUX / SD3.5 recall 为 0.740 / 0.860；按 source group 重抽样 2,000 次、随机种子 `20260929` 的 balanced accuracy 描述性 95% 区间约 0.620–0.740。FSD screening AUC 为 0.700；按 source group 重抽样 1,500 次、同一随机种子的描述性 95% 区间约 0.627–0.771。校准概率模型的分数中心为 7.579，真实 RAISE 分数有长右尾：calibration 最大 81.329、screening 最大 112.789；长尾可能使线性逻辑校准的 0.5 判定阈值偏高，损失假图召回。阈值分析显示 FSD 确有可用排序信号，但仍有大量真假重叠。

## 3. 竖幅 RAISE 真图上的失效集中

按每组 RAISE 原图的方向分层；生成图均为 1024×1024 正方形。screening 中横幅源 70 组、竖幅源 30 组。以仅从 calibration 选出的诊断阈值 5.389 评价：

| 来源组 | screening AUC | balanced accuracy | RAISE specificity | 两类假图合并 recall |
|---|---:|---:|---:|---:|
| 横幅 RAISE，70 组 | 0.819 | 0.757 | 0.714 | 0.800 |
| 竖幅 RAISE，30 组 | 0.439 | 0.500 | 0.200 | 0.800 |

screening RAISE 的 `-z_score` 中位数在横幅为 4.29、竖幅为 7.72；较大的值更容易被判成假图。相应 FLUX 中位数为 6.47 / 7.18，SD3.5 为 7.56 / 7.89。calibration 同样显示竖幅真图分数明显偏高。竖幅真图误报是总体低分的重要来源；但原图方向与场景内容、真实/生成图尺寸一起变化，现有观察**不能证明**具体是方向、内容还是缩放裁剪导致。由于假图本身为正方形，不能把隐藏的来源 RAISE 方向直接作为部署时的分流规则。

## 4. AIDE 正确顺序重跑与独立筛查

同一 RAISE 图的两次独立 smoke 均严格加载权重，logits 完全一致；随后 600 张评分全部完成，样本 ID 唯一、图像 SHA-256 与清单一致、本地与服务器评分文件摘要相同。4090 峰值分配约 3,630.7 MiB，结束后显存归零。初始 76 张因默认 CPU 线程设置约 2 秒/张；暂停后用 1、4 线程单图核验，logits 均不变，4 线程预处理降至约 0.37 秒；从断点续跑，screening 中位端到端耗时 0.444 秒/张。上传时 SCP 卡住，已检查进程和远端哈希，改用 SSH 标准输入上传并逐文件核验；没有在未核实脚本时启动推理。

| AIDE 规则 | calibration balanced accuracy | screening balanced accuracy | screening RAISE specificity | screening FLUX recall | screening SD3.5 recall | screening AUC |
|---|---:|---:|---:|---:|---:|---:|
| 官方 logits 默认阈值 | 0.603 | 0.595 | 0.280 | 0.910 | 0.910 | 0.558 |
| 类别均衡一维逻辑校准，概率 ≥ 0.5 | 0.550 | 0.593 | 0.380 | 0.800 | 0.810 | 0.558 |

正确顺序的 AIDE 在 screening 上对 FLUX vs RAISE 的 AUC 为 0.486，对 SD3.5 vs RAISE 为 0.630；总体 AUC 0.558，仍接近随机排序。仅在 calibration 搜索最佳 balanced accuracy 阈值，screening 也只有 0.605，且 RAISE specificity 仅 0.280。AIDE 官方 README 将 `progan_train.pth` 列为 ProGAN 训练模型；训练域与本次 FLUX/SD3.5 不同，可能是弱泛化的原因之一，但本次数据不能单独证明该机制。

校准概率阈值 0.5 下，screening 的互补性为：RAISE 上 FSD 单独正确 47 张、AIDE 单独正确 8 张、两者均错 15 张；FLUX 上分别为 7、51、13 张；SD3.5 上分别为 10、40、9 张。这主要表现为 FSD 更常识别真图、AIDE 更常报假图；互补错误不能代替每位专家的独立可靠性。新汇总和校准文件位于本地 `runs/stage1-bfree-screen-20260928/scores/summary_official_order.json` 与 `calibrated_official_order/`。

## 5. 结论与后续边界

旧 AIDE 结论因输入错误作废；正确重跑独立得出 AIDE 排序接近随机、真图误报高的结论。FSD 有一定排序信号，但现有校准阈值 balanced accuracy 为 0.603，竖幅来源组失效；事后诊断阈值的 0.680 不能作为新的预注册准入成绩。依据 Stage 0 已定的“任一专家近随机或严重单边则回候选矩阵讨论”门槛，暂不冻结 `E_base` / `E_extra`，不进入 Stage 2。下一步与用户讨论替代专家或调整实验配置；若要验证 FSD 的尺寸/方向机制，需另行设计受控预处理对照，并使用未参与本次诊断的新数据评价。
