# SAFE 768×768 Crop 单因素诊断实验 SOP

## 0. 实验目标

本实验唯一目标：

判断 SAFE 在 RAISE/FLUX/SD3.5 目标域上的性能下降，是否主要由：

- 图像尺寸差异
- 宽高比差异
- resize/interpolation 历史
- 输入 geometry shortcut

导致。

本实验不是优化实验。

不是寻找最佳 preprocessing。

不是调参。

唯一研究问题：

> 在不改变 SAFE 模型和推理流程的情况下，仅消除 real/fake 图像尺寸与比例差异后，SAFE 分数是否明显改善？

---

# 1. 严格禁止事项

## 禁止修改 SAFE

禁止：

- 修改模型代码
- 修改 checkpoint
- 修改网络结构
- 修改 threshold
- 修改 score direction
- 修改 input_size
- 修改 normalization
- 修改 inference 参数

SAFE 必须保持：

```
checkpoint:
checkpoint-best.pth

input_size:
256

transform:
SAFE 官方 crop

model:
SAFE
```

---

## 禁止修改实验数据组成

必须使用：

已有 Stage 1 screening 数据。

保持：

```
RAISE real:
100 images

FLUX fake:
100 images

SD3.5 fake:
100 images
```

必须与之前 SAFE baseline 使用完全相同的图片。

不要：

- 增加数据量
- 减少数据量
- 重新采样
- 更换 source group
- 使用 calibration 数据

---

## 禁止使用 resize

这是本实验最重要规则。

允许：

```
center crop
```

禁止：

```
resize
rescale
interpolation
padding
letterbox
```

正确：

```
1256×833
 ↓
center crop
 ↓
768×768
```

错误：

```
1256×833
 ↓
resize
 ↓
768×509
 ↓
crop
```

---

# 2. 实验假设

当前 baseline：

```
SAFE original preprocessing

结果:
AUC ≈ 0.655
```

本实验：

```
768 center crop
+
SAFE original preprocessing
```

比较差异。

---

# 3. 创建独立实验目录

创建：

```
SAFE_768_crop_diagnostic/
```

目录：

```
SAFE_768_crop_diagnostic/

├── input_original/
├── cropped_images/
├── metadata.csv
├── inference_output/
└── REPORT.md
```

不要修改原始数据。

---

# 4. 固定输入图片列表

复用 baseline 使用的 300 张图片。

保存：

```
baseline_file_list.txt
```

不要重新搜索图片。

---

# 5. Crop 操作要求

对于每张图片：

读取：

```
width
height
```

如果：

```
min(width,height) < 768
```

停止实验并报告。

禁止：

- resize
- 放大
- padding

---

## Center crop

计算：

```
left = (width - 768) / 2

top = (height - 768) / 2
```

执行：

```
crop(left, top, left+768, top+768)
```

输出：

```
768×768
```

---

# 6. Crop 脚本要求

生成：

```
metadata.csv
```

格式：

|new_file|original_file|width_before|height_before|width_after|height_after|
|-|-|-|-|-|-|

必须记录：

- 原文件路径
- 新文件路径
- 原尺寸
- 新尺寸

---

# 7. 数据完整性检查

数量必须一致：

```
real:
100

FLUX:
100

SD3.5:
100
```

如果数量不一致：

停止。

---

# 8. 人工抽查

随机检查至少：

```
10 images
```

确认：

- 没有黑边
- 没有 padding
- 没有拉伸
- 没有 resize

---

# 9. SAFE inference

使用和 baseline 完全相同的 SAFE inference。

唯一变化：

输入图片。

保持：

```
checkpoint:
checkpoint-best.pth

input_size:
256

transform:
crop

model:
SAFE
```

不要修改：

```
--input_size
--transform_mode
--batch_size
--threshold
```

---

# 10. 保存输出

输出：

```
inference_output/
```

至少包含：

```
run.log
scores.csv
metrics.txt
```

scores.csv：

|image|label|score|
|-|-|-|

---

# 11. 计算指标

必须计算：

- AUC
- Accuracy
- Precision
- Recall

特别记录：

- FLUX recall
- SD3.5 recall
- real false positive rate

---

# 12. REPORT.md 格式

包含：

## 1. Experiment Goal

Only change input geometry by applying 768×768 center crop before SAFE inference.

## 2. Baseline

记录原 SAFE 结果：

```
AUC:
Accuracy:
FLUX recall:
SD3.5 recall:
Real false positive:
```

## 3. Crop Protocol

```
operation:
center crop

size:
768×768

resize:
NO
```

## 4. Results

|Setting|AUC|Accuracy|FLUX Recall|SD3.5 Recall|Real FP|
|-|-:|-:|-:|-:|-:|
|Original SAFE||||||
|768 Crop||||||

---

# 13. 结果解释

## Case A

如果：

AUC 提升 >= 0.10

或 fake recall 明显提升：

说明：

```
768 crop substantially improves SAFE performance.
This suggests image geometry, resolution or resizing-related
statistics contribute significantly to the previous failure.
```

---

## Case B

如果：

AUC 提升：

```
0.03 - 0.10
```

说明：

```
768 crop provides partial improvement.
Image geometry contributes to the failure, but it is unlikely
to be the only factor.
```

---

## Case C

如果：

AUC变化：

```
<0.03
```

说明：

```
768 crop does not materially change SAFE performance.
The previous failure is unlikely to be primarily caused by
simple image geometry mismatch.
```

---

# 14. 最终交付

提交：

```
SAFE_768_crop_diagnostic/

├── metadata.csv
├── cropped_images/
├── inference_output/
│   ├── run.log
│   ├── scores.csv
│   └── metrics.txt
└── REPORT.md
```

---

# 15. 完成后停止

禁止继续：

- 调 SAFE preprocessing
- 调 threshold
- 修改 crop size
- 测其他 detector
- 测 B-Free
- 修改 Actor

完成 REPORT.md 后等待下一步决策。
