# PROBE 原始误例的 Evidence v1 分析

本分析只描述四张冻结 Actor-0 eval 中的 PROBE 分类误例。证据提取参数在打开 eval 标签前已经冻结；本节没有进行阈值或参数选择。

| sample_id | category | frozen PROBE output | atypical patches | spatial pattern | max percentile |
| --- | --- | ---: | ---: | --- | ---: |
| `r0d0ff43at:raise` | RAISE | fake (incorrect) | 3/6 (0.500) | isolated | 100.0 |
| `r000da54ft:flux` | FLUX | real (incorrect) | 5/9 (0.556) | clustered | 100.0 |
| `r0cea5432t:flux` | FLUX | real (incorrect) | 8/9 (0.889) | clustered | 100.0 |
| `r1882b6e6t:flux` | FLUX | real (incorrect) | 9/9 (1.000) | clustered | 100.0 |

每例原图、top-3 crops 和 deviation map 见本目录下对应的 `probe_failures/` 图片。

## 逐例观察

- **RAISE `r0d0ff43at`**：真实的 sepia 雕塑场景中，三个 patch 越过固定第 95 百分位；三个 patch 互不相邻，分布在身体、手臂和头发附近。高偏离并非只由单个 patch 造成，也没有形成大块聚集。视觉上内容和色调较特别，说明真实图也可出现有空间位置的高偏离。
- **FLUX `r000da54f`**：五个 patch 越过门槛并构成聚集；高值覆盖樱花近景和草地/球场区域。表现为较广的空间变化，不能归结为单个极端 patch。
- **FLUX `r0cea5432`**：八个 patch 越过门槛并形成聚集，水面、天鹅和倒影区域均有较高偏离。
- **FLUX `r1882b6e6`**：九个 patch 全部超过门槛并形成聚集；图中包含画框、绘画天空、山体和建筑。偏离覆盖范围很广。

## 对方案问题的回答

1. **Evidence Card 稳定性**：四例都能形成有效特征、有限距离、空间统计和可重建 crop；完整重复运行的 patch 特征最大绝对差为 0，top-3 排序相同。因此没有发现提取不稳定。信号大小因样本而异。
2. **少数极端 patch 的影响**：三张 FLUX 误例不是单一极端 patch 造成；分别有 5、8、9 个 patch 越过门槛。RAISE 误例有三个分离的高偏离 patch。
3. **孤立或聚集**：真实 RAISE 误例呈 isolated；三张 FLUX 误例均 clustered。这个 4 例模式是描述性观察，样本量不能支持普遍规律。
4. **可能导致混淆的内容**：RAISE 雕塑照片的色调和非日常主体较突出；FLUX 樱花、水面与天鹅、画中画场景在纹理和内容上都与真实参考集不同。此处只记录可见差异，不推断生成来源或机制。
5. **是否提供进一步调用工具的理由**：大范围 clustered deviation 可作为“需要补充检查”的中性线索；RAISE 误例也有三个异常 patch，所以它本身无法区分真假，也不能单独决定工具路由。需要与其他独立证据结合。

## 结论

Evidence v1 能为原 PROBE 错例提供可定位的 representation deviation，但没有证明它可以纠错或提升 Actor。此处不改变冻结阈值和参数。
