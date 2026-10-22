# Monitor 8例文字试做

2026-10-09：研究者已确认文字输入、现有冻结Qwen3-VL-8B-Instruct和既有8个开发例。无卡准备已完成；实际模型审核尚未运行。

这一步审核原始Actor轨迹并生成**拟干预**，不会执行工具、重新生成Actor动作或训练。5个终态与3个CALL前缀含同图不同条件，不能作为8个独立测试样本。审核与建议分开保存；是否有效仍需逐例核验。

## 输入与输出

`prepare.py`核对既有manifest、输入、案例索引和四条件原始文件hash，按原选择顺序派生8例；不重新选择样本、不读取silver标注。输出位于Git忽略的`../private/pilot_v1/`，拒绝覆盖已有目录。

每例增加运行快照与原始证据记录：accepted CALL消耗额度，格式重试不消耗，DELAY受阻请求仍消耗；已成功工具不可重复。FULL旧记录没有call_status时，以实际非错误返回核对成功状态。terminal的预算按历史accepted CALL重建，并核对同图既存CALL前缀预算。工具别名保持原样。

证据记录只整理决策前已返回的observation。当前CALL结果和未来步骤不进入CALL输入；后出现的证据不能追认支持较早步骤。工具卡及原始返回的范围、局限完整保留。记录中的盲化sample_id沿用原输入，不读取身份映射。

`review`沿用原七类规范和状态，不改变旧标签；`proposal`可为：

| 动作 | 首版接口约束 |
|---|---|
| ALLOW_ACTION | CALL合理、有额度且工具可用；STOP原始结构合法、review为PASS、STOP及结论支持检查均pass |
| REVISE_REASONING | 有引用的违规，反馈要求先修正陈述；额度0也可提出 |
| REQUEST_EVIDENCE | STOP有可执行缺口、premature_stop失败、有额度、候选工具可用且各有能力引用 |
| BLOCK_CALL | 当前CALL合理性失败，反馈要求重选合法动作 |
| END_LIMITED | STOP额度耗尽或没有可用工具；保持审核失败/未决状态，不认定结论充分 |
| UNASSESSABLE | 至少一项适用审核缺少信息；不自动放行 |

每项建议含中文理由、原文引用；修正、补证据和阻止CALL另含中文feedback。只有补证据建议含gap。引用必须指向原输入叶子值，不能把派生证据记录当作独立证据。解析器验证格式、引用存在和基本可执行性；不自动证明引用语义、工具相关性或证据充分性。

## 无卡入口

在仓库根目录运行（准备包已存在，无需再次prepare）：

```powershell
python experiments/faithbench_monitor_v0/pilot_v1/run_text.py
python -m unittest discover -s tests -p test_monitor_pilot.py -v
```

默认只校验准备包，不导入torch/transformers、不加载模型。准备源码或请求变更将导致hash校验失败，需要记录新版本并使用新目录派生；不能覆盖旧包。

## 之后的GPU审核

先核验研究者提供的当前AutoDL实例、冻结模型snapshot和环境，再告知用卡任务/时段，由研究者开卡。入口必须显式加`--run-inference --input-dir <准备包> --model-dir <冻结snapshot> --output-dir <新结果目录>`。

模型revision固定为`0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`，模型config hash核验，local_files_only加载；每例独立文字上下文。贪心生成，seed=42，max_new_tokens=4096，repetition_penalty=1.05，不作格式重试；这组生成参数仅用于首轮接口诊断。记录原始响应、解析失败、token、耗时及runtime。结果目录拒绝覆盖，异常留下已完成响应；不自动续跑或挑选语义响应。

`check_responses.py --inputs <inputs.jsonl> --responses <responses.jsonl> --output <新检查文件>`可在无卡环境复核响应格式与引用。实际推理后需逐例检查问题定位、引用支持、反馈具体性、补证据相关性及不确定性；结构通过不等于语义正确。

尚未接入在线Actor，没有对照效能评价。74预留来源组、原始标签及冻结Actor保持不变，B0-D gate仍INCONCLUSIVE。
