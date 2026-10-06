# PROBE Evidence-Only v1：从分类器输出改造为非结论性取证证据

## 0. 任务目标

当前 PROBE-DINOv2 在 Actor 系统中直接提供 `real/fake + score`，容易导致 Actor 形成单工具 shortcut。

本实验的目标不是重新训练 PROBE，也不是提升 PROBE 分类准确率，而是构建一个新的：

**PROBE Evidence Extraction Branch**

使 PROBE 对 Actor 输出：

- 可复算的 representation deviation；
- 异常 patch 的位置；
- 异常在空间上的分布；
- 对应的视觉 crop；

而不再向 Actor 暴露：

- real/fake verdict；
- fake probability；
- signed classifier score；
- patch-level real/fake vote。

最终希望把 PROBE 从：

`classifier / judge`

改造成：

`forensic evidence locator`

本阶段不训练 Actor，不修改 Actor prompt，不开展 Monitor 实验。

---

# 1. 核心实验假设

验证以下假设：

> PROBE-DINOv2 的中间 patch representation 可以提供可验证的“异常表征证据”，而不必直接暴露真假分类结果。

目标数据流：

```text
Image
  ↓
Frozen PROBE-DINOv2 backbone
  ↓
Patch CLS features
  ↓
Compare with authentic-reference feature bank
  ↓
Representation deviation + spatial localization
  ↓
Evidence Card
```

Actor 后续只能看到 Evidence Card 和相应异常 crop。

禁止形成：

```text
PROBE → fake 0.98 → Actor → fake
```

---

# 2. 实验原则

必须遵守以下约束。

## 2.1 官方 PROBE baseline 完全冻结

禁止：

- 修改 checkpoint；
- 重新训练；
- 微调；
- 改分类阈值；
- 改官方图像预处理；
- 改 crop size；
- 改 patch stride；
- 根据 eval 标签调 evidence 参数。

现有 PROBE 分类结果必须完整保留，作为后续 baseline。

Evidence branch 必须与原 classifier branch 并存：

```text
                    ┌─ Official PROBE classifier
Image → PROBE ──────┤  仅用于实验评估
                    │
                    └─ Evidence extraction branch
                       Actor未来只能访问这里
```

---

## 2.2 分类信息与证据信息严格隔离

允许内部保存 classifier 输出用于 parity check 和研究分析。

但 Actor-facing evidence 文件中禁止出现：

```text
real
fake
fake_probability
real_probability
verdict
prediction
class
classifier_score
```

也禁止出现：

```text
7/10 patches vote fake
strongly supports fake
likely AI-generated
```

PROBE 工具只能描述“观察到了什么”。

---

# 3. 冻结实验数据

优先复用当前 Actor-0 实验中已经冻结的数据划分。

建议：

- reference/calibration：现有 dev 中的 real images；
- evaluation：当前独立 300-image eval；
- eval 仍为：
  - 100 RAISE real
  - 100 FLUX
  - 100 SD3.5

如果项目中已经存在更早冻结、且与 eval 来源组完全不重叠的真实图 calibration set，则优先使用该集合。

如果没有，则使用：

**Actor dev 中的 60 张 RAISE real**

作为 Evidence v1 authentic-reference set。

必须记录：

- image manifest；
- source-group IDs；
- SHA-256；
- PROBE checkpoint SHA-256；
- repo commit；
- Python/PyTorch/Transformers/CUDA；
- Evidence extractor 参数。

绝对禁止使用 eval fake/real 标签建立 reference bank。

---

# 4. Stage A：建立 baseline parity

在添加 evidence extractor 前，先验证新的代码路径没有改变 PROBE。

对 eval 中至少全部 300 张图重新走一次 evidence-compatible inference。

内部同时记录：

```text
patch_logits
image_logit
image_probability
CLS features
```

其中分类结果只进入：

```text
audit/
```

不得进入：

```text
evidence/
```

检查：

```text
new_image_probability
vs
existing_frozen_PROBE_probability
```

要求：

- 所有样本顺序一致；
- patch 数一致；
- 图像概率误差原则上 `< 1e-5`；
- 分类结果 300/300 一致。

如果 parity 不通过：

**立即停止实验。**

不要继续构建 reference bank。

输出：

```text
analysis/parity_report.json
analysis/parity_report.md
```

---

# 5. Stage B：提取 patch-level CLS features

使用当前冻结的 DINOv2 backbone。

对每个 patch 获取线性分类头之前的：

```text
CLS feature h_i
```

对于每个 feature 做 L2 normalization：

\[
z_i=\frac{h_i}{||h_i||_2}
\]

同时记录：

```text
sample_id
source_group
patch_id
grid_row
grid_col
processed_bbox
feature
```

注意：

`processed_bbox` 必须对应实际送入 PROBE patch generator 的 processed image。

不要把 processed image 上的坐标错误映射回原始图片。

建议同时保存 processed image，用于后续 crop 可视化和审计。

---

# 6. Stage C：建立 Authentic Reference Bank

只使用 calibration/dev 中的真实图片。

对所有真实图 patch 提取：

```text
L2-normalized CLS features
```

构成：

\[
R=\{z_1^{real},z_2^{real},...,z_N^{real}\}
\]

保存：

```text
reference_bank/
    features.npy
    metadata.csv
    manifest.json
```

metadata 至少包含：

```text
sample_id
source_group
patch_id
grid_row
grid_col
```

---

# 7. Stage D：定义非结论性的 Representation Deviation

第一版只使用一种距离，避免多变量调参。

使用：

**cosine distance**

\[
d(a,b)=1-a^Tb
\]

对每个 query patch：

\[
z_i
\]

在 reference bank 中寻找 k 个最近邻。

固定：

```text
k = 20
```

定义：

\[
D_i =
\frac{1}{k}
\sum_{j \in kNN(z_i,R)}
(1-z_i^Tz_j)
\]

它表示：

> 当前 patch 在 PROBE representation space 中距离真实参考 patch 有多远。

注意：

这不是 fake probability。

---

# 8. Stage E：建立 calibration percentile

不能直接把 `D_i` 的绝对数值解释给 Actor。

需要使用真实 calibration distribution 建立 percentile。

对于 reference real patch 本身计算 deviation 时：

**禁止使用来自同一个 source group 的 patch 作为 nearest neighbors。**

即采用 source-group-excluded reference。

这样避免：

```text
patch → 找到自己或同源高度相似 patch → 距离人为过小
```

得到真实 patch deviation distribution：

\[
D^{real}_{cal}
\]

以后对于任何 query patch 的 deviation：

\[
D_i
\]

转换成：

```text
reference_deviation_percentile
```

例如：

```text
98.7
```

它只表示：

> 该 patch 的 representation deviation 高于 calibration real patches 中约 98.7% 的样本。

严禁解释为：

> 98.7% fake probability

---

# 9. Stage F：生成 patch evidence

第一版固定：

```text
atypical patch:
reference_deviation_percentile >= 95
```

这里的 95 只来自真实 calibration distribution。

不能在 eval 上重新选择。

每张图输出以下统计：

```text
num_patches
num_atypical_patches
atypical_fraction

max_deviation_percentile
median_deviation_percentile

top_3_atypical_regions
```

其中每个 top region 包括：

```text
patch_id
grid_row
grid_col
bbox
deviation_percentile
crop_path
```

---

# 10. Stage G：空间模式分析

只做确定性统计，不做真假解释。

对于超过 95 percentile 的 patch，在 patch grid 上使用：

**4-neighbor adjacency**

计算 connected components。

输出：

```text
atypical_patch_count
connected_component_count
largest_component_size
largest_component_fraction
```

定义一个简单 deterministic descriptor：

### none

```text
atypical_patch_count == 0
```

### isolated

没有任何两个异常 patch 相邻。

### clustered

```text
largest_component_size >= 2
AND
largest_component_size / atypical_patch_count >= 0.5
```

### dispersed

其余情况。

注意：

输出：

```text
spatial_pattern = clustered
```

可以。

禁止输出：

```text
clustered synthetic artifacts
```

---

# 11. Stage H：保存异常区域视觉证据

每张图保存 deviation percentile 最高的：

```text
Top 3 patches
```

建议目录：

```text
evidence/crops/<sample_id>/
    region_01.png
    region_02.png
    region_03.png
```

crop 必须来自实际 processed image。

每个 crop 必须能够通过：

```text
processed image + bbox
```

完全重建。

做至少 20 张随机样本的像素一致性检查。

---

# 12. Actor-facing Evidence Card

最终为每张图生成一个：

```text
evidence_card.json
```

推荐 schema：

```json
{
  "tool": "global_representation_analyzer",
  "evidence_type": "representation_deviation",
  "scope": {
    "num_regions_examined": 12
  },
  "reference": {
    "type": "authentic_image_reference_bank",
    "distance_metric": "cosine_knn",
    "k": 20
  },
  "observations": {
    "num_atypical_regions": 3,
    "atypical_fraction": 0.25,
    "max_deviation_percentile": 99.1,
    "median_deviation_percentile": 63.4,
    "spatial_pattern": "clustered"
  },
  "most_atypical_regions": [
    {
      "region_id": "R1",
      "bbox": [0, 0, 336, 336],
      "deviation_percentile": 99.1,
      "crop_path": "..."
    }
  ],
  "limitations": [
    "Representation deviation is not proof of synthetic origin.",
    "Unusual authentic imagery or post-processing may also produce outlying representations.",
    "The representation does not by itself identify a physical image-generation artifact."
  ]
}
```

注意：

上面所有数值只是结构示例。

实际值必须来自程序。

---

# 13. 同时生成 human-readable Evidence Card

再生成对应的：

```text
evidence_card.txt
```

格式类似：

```text
PROBE Representation Evidence

Regions examined:
12

Reference deviation:
3 / 12 regions exceed the 95th percentile of the
authentic-reference calibration distribution.

Spatial pattern:
clustered

Most atypical regions:

R1
Location: [...]
Deviation percentile: 99.1
Visual crop: [...]

R2
...

Limitations:
Representation deviation is not proof of synthetic origin.
Unusual authentic imagery or post-processing may also
produce outlying representations.
```

禁止增加任何真假判断。

---

# 14. Stage I：Evidence Pipeline 评估

本阶段暂时不跑 Actor。

首先单独回答：

> 这个 evidence extractor 是否工作正常？

至少做以下分析。

## 14.1 Pipeline validity

报告：

```text
300/300 successfully processed?
feature finite?
distance finite?
crop reconstruction correct?
baseline parity?
```

---

## 14.2 Label-conditioned descriptive analysis

Evidence extractor 全部冻结之后，才允许打开 eval label 做描述性统计。

分别统计：

```text
RAISE
FLUX
SD3.5
```

的：

```text
mean/median max_deviation_percentile
mean atypical_fraction
spatial_pattern distribution
```

目的不是重新找最佳 threshold。

禁止根据这一步重新修改：

```text
k
95 percentile threshold
distance metric
reference bank
```

---

# 15. Stage J：重点检查 PROBE 原有错例

当前 eval 中 PROBE 共错 4 张。

Evidence extractor 冻结后，单独制作：

```text
PROBE_FAILURE_EVIDENCE_ANALYSIS.md
```

对 4 个错误样本逐张展示：

```text
原图
Top-3 atypical crops
patch deviation map
atypical fraction
spatial pattern
原 PROBE classifier 是否判断错误
```

然后回答：

1. PROBE classifier 错误时，Evidence Card 是否表现出明显不稳定或异常结构？
2. 错例是否由少数极端 patch 拉动？
3. 错例是否呈现 dispersed / isolated，而不是一致性的异常？
4. 异常 crop 中是否存在明显可能导致 detector confusion 的内容？
5. Evidence Card 是否提供了未来 Actor 进一步调用其他工具的合理理由？

只做分析。

**禁止根据这 4 张重新设计 threshold。**

---

# 16. Stage K：定性审计

固定随机种子：

```text
20261005
```

从 eval 中分层抽：

```text
10 RAISE
10 FLUX
10 SD3.5
```

共 30 张。

生成 contact sheet：

```text
original
+
top1 crop
+
top2 crop
+
top3 crop
+
deviation percentile
```

人工检查：

- bbox 是否正确；
- crop 是否对应原区域；
- 是否存在 padding/错位；
- top patch 是否只是图像边缘错误；
- spatial statistics 是否与图像一致。

人工审计只能用于判断 pipeline 是否有 bug。

不能根据审计结果调 detector/evidence 参数。

---

# 17. 第一阶段明确不做的内容

本轮不要做：

- Actor SFT；
- Actor prompt tuning；
- Monitor；
- GRPO；
- preference optimization；
- Mahalanobis distance；
- PCA；
- learned anomaly detector；
- Grad-CAM；
- attention rollout；
- training-manifold support；
- perturbation stability；
- 多距离 ensemble；
- threshold search；
- 使用 fake reference bank；
- 使用 eval 数据重新校准。

这些留到 Evidence v2。

第一版目标只有：

> 证明 PROBE 可以稳定输出非结论性、空间可定位、可复算的 representation evidence。

---

# 18. 成功标准

本实验判为 PASS 至少需要满足：

### Engineering

```text
300/300 eval successfully processed
baseline prediction parity = 300/300
no NaN/Inf features or distances
top-region crops reconstruct correctly
```

### Evidence integrity

Actor-facing output 中：

```text
0 fake/real verdict
0 fake probability
0 signed classifier logits
0 patch fake vote
```

### Reproducibility

重新运行得到：

```text
same manifests
same features within numerical tolerance
same region ranking
same Evidence Card statistics
```

### Research usefulness

能够对每张图片回答：

```text
哪些区域偏离真实参考分布？
偏离程度如何？
异常覆盖多大？
异常是孤立、聚集还是分散？
具体应该检查哪些 crop？
```

而无需告诉 Actor：

```text
这张图是真是假。
```

---

# 19. Stop conditions

出现以下任一情况立即停止并报告，不得擅自绕过：

1. 新 pipeline 无法复现官方 PROBE 分类结果。
2. 实际代码无法可靠取得 patch CLS feature。
3. processed-image bbox 无法与 patch 一一对应。
4. reference bank 与 eval 存在 source-group overlap。
5. evidence extractor 意外使用了 eval labels。
6. Actor-facing 文件泄露 classifier verdict / probability。
7. reference percentile 计算存在 self-neighbor 或同来源泄漏。
8. 修改原 checkpoint、官方 baseline 输出或历史实验文件。

---

# 20. 目录建议

```text
experiments/
└── probe_evidence_v1/
    ├── README.md
    ├── config/
    │   ├── evidence_config.json
    │   ├── environment.txt
    │   └── manifests/
    │
    ├── reference_bank/
    │   ├── features.npy
    │   ├── metadata.csv
    │   └── calibration_distribution.npy
    │
    ├── evidence/
    │   ├── cards/
    │   ├── crops/
    │   ├── processed_images/
    │   └── patch_records.jsonl
    │
    ├── audit/
    │   └── classifier_internal_outputs.jsonl
    │
    ├── analysis/
    │   ├── parity_report.md
    │   ├── evidence_statistics.json
    │   ├── evidence_statistics.md
    │   ├── qualitative_audit.md
    │   └── PROBE_FAILURE_EVIDENCE_ANALYSIS.md
    │
    └── REPORT.md
```

---

# 21. 最终 REPORT.md 必须回答的问题

最终报告不要只给运行成功信息，必须明确回答：

### A. Evidence branch 是否完全保持原 PROBE baseline？

给出数值和 parity。

### B. Authentic-reference deviation 是否能够稳定计算？

报告 reference bank 大小、patch 数、距离分布。

### C. Eval 中 representation deviation 呈现什么结构？

分别报告 RAISE / FLUX / SD3.5。

### D. 异常是否具有空间结构？

报告 none / isolated / clustered / dispersed。

### E. Top atypical regions 是否能被稳定定位并正确裁剪？

给人工审计结果。

### F. PROBE 的 4 个原始错误样本表现如何？

逐例分析，但禁止调参。

### G. Evidence Card 是否完全移除了 conclusion leakage？

明确搜索并验证：

```text
real
fake
probability
verdict
prediction
```

Actor-facing 文件中不得存在具有真假结论意义的字段。

### H. 是否值得进入 Evidence v2？

最终只允许：

```text
PASS
CONDITIONAL PASS
FAIL
```

并说明原因。

---

# 22. Evidence v2 暂定方向

只有 Evidence v1 PASS 后再考虑：

1. perturbation stability；
2. detector training-support / OOD；
3. 多尺度 patch evidence；
4. PROBE 与 PatchCraft region alignment；
5. Evidence-only Actor SFT。

本轮不要提前执行。

---

## 最终任务定义

本实验不是为了证明：

> PROBE 还能保持 98% 分类准确率。

这个事实已经有 baseline。

本实验要证明的是：

> 在不向 Actor 暴露 PROBE 最终分类答案的前提下，是否能够从冻结的 PROBE-DINOv2 中提取可复算、空间可定位、非结论性的 representation evidence，为后续真正的 evidence-grounded Actor reasoning 提供输入。

完成 REPORT.md 后停止，不开展 Actor 微调。