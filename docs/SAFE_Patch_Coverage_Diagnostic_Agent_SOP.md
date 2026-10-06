# SAFE Multi-scale / Patch Coverage Diagnostic SOP（Agent Execution Version）

## 0. 任务目标

你需要执行一次 SAFE forensic detector 的空间覆盖诊断实验。

唯一研究问题：

> SAFE 在 RAISE/FLUX/SD3.5 目标域表现下降，是否主要因为固定 center crop
> 丢失了有效 forensic evidence？

本任务不是模型优化。

不是寻找最佳参数。

不是提升指标。

不是调 detector。

只允许改变：

**输入图像裁剪区域。**

------------------------------------------------------------------------

# 1. 严格禁止事项（必须遵守）

## 禁止修改 SAFE

禁止：

-   修改 SAFE 源代码
-   修改模型结构
-   修改 checkpoint
-   微调模型
-   修改权重
-   修改 threshold
-   修改 score direction
-   修改 softmax 处理

必须使用：

    checkpoint:
    checkpoint-best.pth

------------------------------------------------------------------------

## 禁止修改 inference 参数

必须保持 baseline 一致：

    model:
    SAFE

    input_size:
    256

    transform:
    SAFE official preprocessing

禁止修改：

    --input_size
    --batch_size
    --transform_mode

------------------------------------------------------------------------

## 禁止修改数据集合

必须使用之前 Stage 1 screening manifest：

SHA256:

    ceb396cbf9a78d2aa04a4e77307e6062e4486de900b6c8bd12be13f7732fcc58

数量：

    RAISE real: 100
    FLUX fake: 100
    SD3.5 fake: 100

禁止：

-   重新随机抽样
-   添加图片
-   删除图片
-   使用 calibration 数据
-   使用剩余 source groups

如果 manifest 不匹配：

立即停止并报告。

------------------------------------------------------------------------

# 2. 实验原理

之前发现：

    original image
        ↓
    SAFE CenterCrop(256)

与：

    original image
        ↓
    CenterCrop(768)
        ↓
    SAFE CenterCrop(256)

完全等价。

因此不能使用 768 nested crop。

本实验改为：

测试不同空间区域是否包含 forensic evidence。

------------------------------------------------------------------------

# 3. 创建实验目录

创建：

    SAFE_patch_diagnostic/

目录：

    SAFE_patch_diagnostic/

    ├── cropped_images/
    ├── metadata.csv
    ├── patch_output/
    └── REPORT.md

不要修改原始数据。

------------------------------------------------------------------------

# 4. 固定图片列表

必须读取已有 baseline 使用的 manifest。

保存：

    baseline_file_list.txt

记录全部 300 张：

    real images: 100
    FLUX images: 100
    SD3.5 images: 100

不要重新选择图片。

------------------------------------------------------------------------

# 5. Crop生成规则

每张原图生成 5 个 crop。

crop size:

    512 × 512

位置固定：

    1. top_left

    2. top_right

    3. bottom_left

    4. bottom_right

    5. center

------------------------------------------------------------------------

# 6. Crop计算方式

先读取：

    width
    height

检查：

    min(width,height) >= 512

如果不满足：

停止实验并报告。

禁止：

-   resize
-   padding
-   interpolation
-   放大

------------------------------------------------------------------------

## 坐标规则

### top_left

    x = 0
    y = 0

### top_right

    x = width - 512
    y = 0

### bottom_left

    x = 0
    y = height - 512

### bottom_right

    x = width - 512
    y = height - 512

### center

    x = (width - 512) // 2
    y = (height - 512) // 2

------------------------------------------------------------------------

# 7. 保存 crop

文件名：

    {image_id}_{position}.png

例如：

    001_top_left.png
    001_center.png

------------------------------------------------------------------------

# 8. 生成 metadata.csv

必须生成：

    metadata.csv

格式：

  image_id   position   original_file   x   y   width   height
  ---------- ---------- --------------- --- --- ------- --------

示例：

    001,top_left,a.png,0,0,512,512

------------------------------------------------------------------------

# 9. 数据检查

运行检查：

必须得到：

    original images:
    300

    cropped images:
    1500

因为：

    300 × 5 = 1500

如果不是：

停止。

------------------------------------------------------------------------

# 10. 人工抽查

随机检查：

至少 10 张 crop。

确认：

-   没有黑边
-   没有拉伸
-   没有 resize
-   crop尺寸都是512×512

------------------------------------------------------------------------

# 11. SAFE 推理

对每个 crop：

使用 SAFE 官方 inference。

唯一变化：

输入图片。

保持：

    checkpoint:
    checkpoint-best.pth

    input_size:
    256

------------------------------------------------------------------------

# 12. 输出格式

创建：

    patch_output/

必须包含：

    run.log

    scores.csv

    metrics.txt

scores.csv:

  image   label   position   score
  ------- ------- ---------- -------

其中：

position:

    top_left
    top_right
    bottom_left
    bottom_right
    center

------------------------------------------------------------------------

# 13. 指标计算

计算：

## Position-level

每个位置分别计算：

-   AUC
-   Accuracy
-   fake recall
-   real false positive rate

位置：

    top_left

    top_right

    bottom_left

    bottom_right

    center

------------------------------------------------------------------------

## Image-level aggregation

对于每张图片：

计算：

### max score

五个patch取最大值。

### mean score

五个patch取平均。

比较：

    center only

    max patch

    mean patch

------------------------------------------------------------------------

# 14. REPORT.md

创建：

    REPORT.md

必须包含：

# SAFE Patch Coverage Diagnostic Report

## 1. Dataset

填写：

    manifest SHA256:
    ceb396cbf9a78d2aa04a4e77307e6062e4486de900b6c8bd12be13f7732fcc58

    RAISE:
    100

    FLUX:
    100

    SD3.5:
    100

------------------------------------------------------------------------

## 2. Baseline

填写之前 SAFE baseline：

    AUC:
    Accuracy:
    FLUX recall:
    SD3.5 recall:
    Real FP:

------------------------------------------------------------------------

## 3. Position Results

表格：

  Position         AUC   Accuracy   FLUX Recall   SD3.5 Recall   Real FP
  -------------- ----- ---------- ------------- -------------- ---------
  top_left                                                     
  top_right                                                    
  bottom_left                                                  
  bottom_right                                                 
  center                                                       

------------------------------------------------------------------------

## 4. Aggregation Results

  Method          AUC   Accuracy
  ------------- ----- ----------
  Center only         
  Max patch           
  Mean patch          

------------------------------------------------------------------------

# 15. 自动解释规则

只能选择以下之一。

## Case A

如果：

    max patch AUC - center AUC >= 0.10

写：

    Patch coverage substantially improves SAFE performance.
    This suggests forensic evidence is spatially localized and
    the original center crop loses useful evidence.

------------------------------------------------------------------------

## Case B

如果：

不同位置性能明显不同：

写：

    SAFE sensitivity depends on spatial location.
    Different image regions contain different amounts of forensic evidence.

------------------------------------------------------------------------

## Case C

如果：

    max patch improvement < 0.03

写：

    Patch coverage does not materially improve SAFE performance.
    The failure is unlikely to be caused only by missing local evidence.
    Target-domain shift or detector mismatch should be investigated.

------------------------------------------------------------------------

# 16. 最终交付

必须提交：

    SAFE_patch_diagnostic/

    ├── cropped_images/

    ├── metadata.csv

    ├── patch_output/

    │   ├── run.log
    │   ├── scores.csv
    │   └── metrics.txt

    └── REPORT.md

------------------------------------------------------------------------

# 17. 完成后停止

完成 REPORT.md 后立即停止。

禁止继续：

-   调 SAFE preprocessing
-   修改 crop size
-   调 threshold
-   测 B-Free
-   测其他 detector
-   修改 Actor

等待下一步实验决策。
