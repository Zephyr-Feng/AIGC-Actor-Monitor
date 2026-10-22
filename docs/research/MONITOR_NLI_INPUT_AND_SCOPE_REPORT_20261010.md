# 候选NLI输入准备与完整Monitor范围核查

2026-10-10，20:38。续接失败复盘，公开模型运行确认仍待用户回答。本阶段只投影旧材料、核原值和任务范围，未下载或加载权重、forward、优化、修改环境或启动GPU。

## 输入已经具体化

[prepare_nli_candidate_v1.py](../../experiments/faithbench_monitor_v0/pilot_v3/prepare_nli_candidate_v1.py)从已复核casebook生成20个去重输入，关联十三旧例/26选择条件。代码SHA `7a71edc9d5534be4744a994fe24bfe5cb0d5dd87f857450119220f52a6722668`。

每个premise按原pointer排序，以“字段位置：原pointer\n返回原文：原quote”逐字段投影；hypothesis为原主张，未补主语、合并属性或造新返回。只有premise/hypothesis作为候选推理字段，来源关联及适配说明另存。模型理由、既有状态、预审理由/判读没有进入推理输入。原casebook仍保存完整来源，候选摘录不取代它。

私有`sft_evidence_contract_v3_nli_candidate_inputs.json` SHA `e5ff843eabcbd3f35f4eb3ca8bba7aadeaad253361ef4e135e549be8e7666508`。逐条重建核20个输入、26来源条件、字段原值/指针和无目标字段投影通过，0修改。最长premise253字符，**尚未进行该公开模型tokenizer预检**，字符数不是上下文通过证据。仅原值投影通过，不代表该序列化适合NLI。

新增[run_nli_candidate_v1.py](../../experiments/faithbench_monitor_v0/pilot_v3/run_nli_candidate_v1.py)，SHA `98d9b8235b6e2e7d2e624dc13222f070841f406607082025b941cea0aee9fe51`。复用[作者NLI示例](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli#nli-use-case)和[实际config](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli/blob/main/config.json)的三类顺序；本候选固定local-only safetensors、FP32 CPU、四线程、无静默截断、逐条保存原始概率，不转换Monitor状态或训练标签。两代码静态compile通过；本机无torch，**runner尚未做运行验证**。无权重下载、forward或性能结论。

## 不能用局部材料替代完整监察

从原G冻结批准包重新核25材料hash，仅读八原包/对应focused输入和现行applicable_checks/allowed_actions定义。得到8例、65观察片段、5冲突槽。当前十三组件案例只有tool_return12、tool_capability1；没有完整check_records/proposal/relation_dispositions/conflict_slots目标。候选公开NLI也只测选择依据，不覆盖完整来源缺失口径或全轨迹综合。

| 完整目标 | 旧批准材料中的可见范围 | 本阶段能证明的内容 |
|---|---|---|
| 来源归因与依据覆盖 | 原65片段；当前13子例与20选择摘录 | 输入原值/无答案字段投影通过，尚无组件效果 |
| 冲突遗漏与方向区分 | terminal_0005一槽、terminal_0041一槽、call_0385三槽 | 原5槽仍存在；未执行新抽取或完整判读 |
| 证据综合/解释与结论一致性 | 五terminal原轨迹、最终解释和原始verdict | 本候选不覆盖；旧G有状态/理由不一致，不能按来源局部改善宣布修复 |
| STOP与资源停止 | terminal_0002/0005/0001余预算1/1/2，terminal_0061/0041余0 | 代码预算边界不等于模型正确判断充分性；仍须完整模型理由复核 |
| CALL必要性与预算 | call_0001/0190余4、call_0385余0 | BLOCK等代码契约和反馈编译不计模型监察收益；Actor反馈继续不执行 |

这些是范围事实，不是新gold或预测。原G/H非独立开发回归，当前也不构成独立提升证据。后续若组件有用，必须回到上述完整任务检查状态—理由—引用覆盖—处置一致性，保留所有原失败，不能仅报告NLI三分类匹配。

私有`sft_evidence_contract_v3_nli_candidate_scope_review.json` SHA `b22b2d0490fbf84d76722232fc35796ad4654ef7e90f7d244150d705490948d5`，同助手非盲、非独立、非gold；另核v3五十冻结协议。新标签/训练记录/模型请求均0，Actor/74组GT身份映射边界不变。

20:31:36目标工具已恢复active，取代上一阶段paused快照。等待已有公开基线确认期间完成这些CPU准备，未把等待当作授权。下一依赖步骤为确认后的资源/依赖检查、固定公开checkpoint及真实tokenizer预检，之后才有最多20次CPU推理与细审复审；当前没有实例上的自有运行任务。
