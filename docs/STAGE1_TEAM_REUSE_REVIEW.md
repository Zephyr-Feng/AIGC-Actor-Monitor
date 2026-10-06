# 组员 Training-Free 成果与 Stage 1 专家筛选的适用性

**日期：2026-09-29**  
**状态：资料与仓库只读核对完成；未引入模型、数据或 GPU 实验**

## 两项任务的边界

本项目 Stage 1 的 [B-Free 清单](STAGE1_EXPERT_SCREEN.md)是 200 个来源组，每组 1 张 RAISE 真图、1 张 FLUX 整图生成图、1 张 SD3.5 整图生成图；100 组 calibration、100 组 screening。假图只有**两种生成器家族**，不是混合了大量局部篡改方式。AIDE 正确顺序 screening 的 FLUX/RAISE AUC 0.486、SD3.5/RAISE AUC 0.630，说明即使单独看生成器也有问题。FSD 的竖幅 RAISE 来源组表现较差，方向、内容、分辨率及裁剪效应尚未分离。由现有结果不能把低性能单独归因为“伪造方式多样”。

组员的 [Training-Free 总结](https://github.com/harleyhhl666/mllm-forensics-training-free/blob/main/reports/TRAINING_FREE_FINAL_SUMMARY.md)和[数据划分](https://github.com/harleyhhl666/mllm-forensics-training-free/blob/main/docs/DATASET_AND_SPLITS.md)只研究 TGIF `sd2-sp`：Stable Diffusion 2 局部重绘后拼接，假图与配对真图只在掩码内不同；篡改区域中位数不到 4%。其独立 TruFor 可行性筛选为 200 对图，整图 AUROC 0.9845、TPR@5% FPR 0.955，另有像素定位指标。仓库 [`CROSSCHECK.txt`](https://github.com/harleyhhl666/mllm-forensics-training-free/blob/main/reports/CROSSCHECK.txt)显示报告数字由结果文件重算一致。这是**该局部拼接任务**的成绩，不能推断 TruFor 对 FLUX/SD3.5 整图生成有效。

[TruFor 官方仓库](https://github.com/grip-unina/TruFor)将模型定位于图像篡改检测与定位；组员的[冻结协议](https://github.com/harleyhhl666/mllm-forensics-training-free/blob/main/protocols/TRUFOR_FEASIBILITY_PROTOCOL.md)记录其整图分数 `sigmoid(det)`、无官方阈值、RGB→CHW float÷256 且不缩放裁剪，并记录公开权重 MD5。该协议提到 TruFor 训练来源含 tampCOCO、compRAISE 等；如果未来用其评估本项目 RAISE/COCO，须先核对图像来源是否与训练样本重叠。组员检查的“TGIF 训练划分与评估来源不重叠”不能代替这一步。

## 可复用内容及决定

1. **直接复用筛选方法**：组员先冻结配对来源组、检查具体检查点和分数方向，再单独评估取证模型，报告 AUROC、低误报召回、来源组 bootstrap，最后才交给 MLLM。这与本项目 Stage 1 需要的流程一致，可用于改进候选准入审计。
2. **复用负结果的边界**：组员发现整图分数可支持真假判断，热力图/结构化区域描述更适合定位解释；错误空间证据还可能被 MLLM 忠实复述。当前项目应先保证专家分数可靠，再谈 Actor 使用证据，但不把其 Qwen2.5-VL 7B/32B 行为外推到本项目 Qwen3-VL-8B。
3. **TruFor 只列条件性候选**：它已在局部篡改上验证，尚无对本项目完整生成图的有效性证据。组员仓库的适配器依赖其服务器绝对路径，模型权重与图像均不在 Git 仓库中；仓库未见 LICENSE。当前不下载或运行 TruFor，不把 0.9845 写作本项目预期性能。

下一步维持原先低成本策略：若需新专家，优先核对**完整生成图**上的具体权重和无泄漏成绩；研究设计、候选与数据用途明确后，才以小规模独立样本上限验证。没有修改已冻结的 Stage 1 结果或剩余 800 组用途。
