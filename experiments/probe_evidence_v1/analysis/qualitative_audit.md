# PROBE Evidence v1 定性审计

## 设计与观察方法

- 固定种子 `20261005`，逐组抽取 10 张 RAISE、10 张 FLUX、10 张 SD3.5，共 30 张。
- 查看 30 张原图与 top-3 crop 的 contact sheet；四张 PROBE 分类误例另以完整分辨率检查原图、top-3 crops 和 patch deviation map。
- 定性观察只用于发现坐标、裁剪、padding 和空间统计实现错误，不用于调整 k、距离、95 百分位门槛、预处理或其他参数。

## 审计结果

- 30/30 张的 crop 与对应 processed image 区域一致；另对随机 20 张图的 60 个 crop 用像素数组重建核对，60/60 完全一致。
- 未观察到 bbox 偏移、patch 顺序错位或 padding 不一致。边缘剩余区域未被 patch 覆盖，是官方 336 像素非重叠滑窗在不能整除的图像边界留下的余量；bbox 始终位于实际 processed image 坐标系。
- Top 区域能正确定位到具体场景，但部分高偏离 patch 覆盖天空、水面、草地、画作边框等背景或边缘。Deviation 描述与真实参考 patch 的距离，不是物理伪造痕迹检测。
- RAISE 样本整体多为 `none`，但罕见内容仍会产生一组孤立或聚集的高偏离 patch。四个错误例中，sepia 雕塑照片被 PROBE 误判为假，具有 3/6 个孤立高偏离 patch；这说明高偏离也可能由真实但不常见的内容带来。
- 三个 FLUX 错误例分别有 5/9、8/9、9/9 个高偏离 patch，且均为聚集模式；异常覆盖较广，并非只由一块极端 patch 触发。
- 部分 FLUX/SD3.5 图像的大量 percentile 达到 100，表示该 patch 高于全部校准 patch 距离；百分位上端因此有饱和。该观察作为描述性结果记录，不据此改变预设距离、参考集或阈值。

## 限制

审计支持实现层面的坐标与裁剪正确性，不证明偏离来自生成器，也不验证 Evidence Card 是否能提升 Actor 的后续判断。本实验没有运行 Actor。
