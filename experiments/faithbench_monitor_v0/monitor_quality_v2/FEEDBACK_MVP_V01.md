# Monitor–Actor研究MVP v0.1

首版用途是继续研究反馈机制：闭环可运行、改动可追溯、已有正反开发实例、失败明确保留。允许难例未决，不要求通用或零错误；不声称模型已全面理解反馈或已完成独立验证。用户已提出降低首版目标，具体是否将更充分的独立验证放下一阶段仍以其验收回复为准。

交付目录`data/feedback_mvp_v01/`包括10个运行依赖文件、使用说明、9份CPU回放和检查结果；服务器代码位于`/root/feedback-mvp-v01-20261020`，入口帮助已验证，不含权重，也未自动启动模型任务。

## 保留的最小实现

复用`selection_unseen_pipeline.py`：Monitor原生反馈→程序核对原文/来源/范围并分流未决→固定Actor提出局部候选→只看原始证据的正文选择→两序一致才执行；空/相同候选或顺序不一致保持未决，完整旧字段不得塞入局部位置。`feedback_control.py`保护补丁范围，终态/置信度/动作保持不变。来源内容由程序绑定，不要求Actor重新抄写证明。

此处保留现有流程，不加入新的裁判、训练或架构。后续可用删减对照决定哪些步骤值得保留；反序仅检查顺序敏感，不是语义证明。基座与当前适配器两份候选对照也未达到完整字段门槛，不并入首版替代原Actor提议器。

## 目前已有的证据

- 正确采纳：004明示注入的“偏离证明AI”得到带局限的修订；006的global解释、007的调用预算也有局部纠错。
- 错误抵抗：004错误反馈引发的信号倒置候选被选回原文；另两份错误反馈原样保持，不能将这些都解释为完成了独立证据反驳。
- 未决：Monitor明确未决可零Actor分流；未知数字候选的三对反序结果不一致，程序可以保持未决，但模型自身0/6主动弃答。
- 内容保护：9份冻结记录的来源/获准范围/不可改字段检查通过。仍有语义残留、概念混淆和对新来源可靠性不足，不报告整体准确率或零风险。

以上是助手开发审阅、含注入控制与同来源变体，非人审gold。详见`SELECTION_VALIDATION_RESULT_20261020.md`，既有分数不修改。MVP用于收集问题与改进，不自动进入生产或将程序接受标成语义通过。

## 零模型演示与复核

在仓库根目录运行下面的缓存回放；它不加载或调用模型、不启动GPU/训练、不做哈希，不改变原结果。输出目录须不存在。

```powershell
python experiments/faithbench_monitor_v0/monitor_quality_v2/feedback_mvp_replay.py --source data/feedback_selection_validation_v1_20261020 --output data/feedback_mvp_v01/native
python experiments/faithbench_monitor_v0/monitor_quality_v2/feedback_mvp_replay.py --source data/feedback_selection_validation_v1_20261020_control --output data/feedback_mvp_v01/control
```

`results.jsonl`逐项保存执行决定、原因、补丁及动作；`summary.json`明确`new_model_calls=0`、`semantic_certified=false`。回放缺少反序轨迹时保持未决，不能补想模型会怎样答；也不是修复后新模型评估。

## 后续真实运行

沿用既有服务器环境、模型与`selection_unseen_pipeline.py --root <新实验目录> --phase monitor|actor`；不加`--run`仅作CPU预检，加`--run`才推理。Monitor仍需已记录的本地Transformers/PEFT vendor环境。每个新目录须具备`inputs.json`、`authorization.json`和实际缓存图像；frozen_ids、原始source cards、answer/regions、original_action、图像prefix及selection_order_seed均随输入冻结，盲化用selection_identity_blind=true。可复用`prepare_selection_unseen.make`和既有配置方式准备，而不覆盖旧根。

这段说明不是新的执行指令；真实运行继续遵守已授权范围、GPU实查、无训练/API、FULL20/GT44禁用及无哈希要求。当前交付只回放现存输出，不追加推理。
