# 下一阶段入口：FaithBench与离线Monitor准备

日期：2026-10-08。状态：研究者已授权并完成下述无卡准备，产出见[开发协议与入口](../experiments/faithbench_monitor_v0/README.md)及[阶段报告](../experiments/faithbench_monitor_v0/PREPARATION_REPORT.md)；真实Monitor推理及正式实验尚未启动。依据主方案Phase II/III及B0-D模型审计判断，暂不追加Actor SFT。正式B0-D gate仍为`ACTOR_B0_D_INCONCLUSIVE`，未冒充人工确认或证据忠实度冻结通过。

## 推荐顺序

研究者最新要求：先讨论并确认Monitor设计（监督目标、信息范围、判断标准、结构和评价），再定模型与技术小样。现有开发代码/规范作为讨论草案；8例同模型文字检查尚未确认执行。

1. 整理FaithBench标注规范与开发案例。
2. 实现离线Monitor输入输出协议及可复现的小样检查入口。
3. 确认小样范围、模型、标签依据和评价规则后，运行离线Monitor baseline。
4. 离线识别能力得到验证后，再讨论在线干预；目前不启动Monitor训练。

## 复用边界

- 复用Mini FaithBench已有6图技术小样、既有工具卡/Evidence Cards、Actor-0与Actor-B已有轨迹及审计工具，不重复生成图像或执行detector。
- B0-D的60图与已被审计的轨迹可以作为已查看的开发/诊断材料，不能再称为新的独立测试集。
- 本轮Agent标签用于候选案例和模型生成的开发标签，不能直接称为经独立验证的Monitor ground truth，也不能用同一批提议证明Monitor有效。
- 74个Monitor预留来源组继续保留；不自行抽取、不重新划分。正式train/dev/test按来源组的边界先确认，同图所有条件和同源图不能跨划分。
- 当前Actor-B版本只作为开发候选，正式benchmark的数据生成版本和冻结范围仍需明确记录；不因当前建议自动改变gate。

## 无卡准备的具体产出

### 标注规范

沿用主方案七类：证据归因错误、无支持综合、冲突遗漏、证据不足、提前停止、无意义继续、verdict与解释不一致。每项判断附具体step和原始observation引用，允许unassessable。分别记录工具原文、Actor自己的推断和审核判断；真假GT不作为推理忠实性的替代答案。

先筛选能由原始工具输出和接口语义核验的自然案例，并保留正常轨迹。置信强度、冲突权重等可争议案例单列待裁决，不自动把初审疑点变成硬标签。若采用controlled perturbation，应另确认干预规则和可核验的标签来源。

### 离线Monitor协议

输入：工具说明、截至当前步骤的Evidence Cards和Actor轨迹；原图/crops仅在已允许的信息范围内加入。输出：中文问题说明、问题类型、证据引用、是否足以支持当前结论/STOP，以及不确定事项。终态审核可以读取完整已完成轨迹；过程中的CALL/STOP决策审核仅使用当时可见信息，避免未来证据泄漏。

复用现有parser、轨迹格式和本地审计材料，先用结构性检查及可核验的小样验证流程。具体baseline方法、模型、评价分母、样本数量和成功标准在真实实验前讨论，不临时加入SFT阈值或准确率门槛。

## 算力与进入条件

上述整理和代码准备不需要GPU。需要本地RTX 4090执行Monitor推理时，先说明具体模型、任务与预计时段，由研究者开卡。正式Monitor benchmark需要确认标签可信度和独立评估边界；模型生成标签的探索结果只能按该范围报告。当前不进行在线Actor干预，也不修改冻结Actor prompt或预算策略。
