# 现成反馈数据与低token路线（2026-10-18）

用户再次指出逐条全文审核成本过高，要求省token或寻找可直接复用数据。本轮停止追加手写审核，完整记录仍为143/1,020；既有成果保留。仅核对本地候选覆盖和公开元数据，未下载新语料、调用模型、划分数据或训练；无任何哈希操作。

## 已核对的可复用内容

- 本地1,020份回答包含2,386处全部作者标注，2,386处均有meta解释，平均112字符。1,271是此前选中候选跨度数，2,386是这些回答保留的全部作者标注，二者不同。可直接保留原文、跨度、类型、作者解释及原来源，程序整理；无需助手重新生成全部理由。但这些标注未必给出最小修正、证据ID或正确内容保护，作者判断也存在争议，不能当成已完成的全文反馈。
- FAVA：作者数据卡列35k合成训练错误/纠正对，以及460段识错与编辑人工标注。作者代码说明训练prompt含参考文本，completion用标签标示错误类型和删除/替换。适合优先考察错误定位与修正对的机械解析；不是自然错误分布或中文完整反馈的现成等价物。数据卡CC-BY-4.0，原始材料权利仍需按来源保留。460段被作者用于检测评估，不能无区分并入训练。
  - https://huggingface.co/datasets/fava-uw/fava-data
  - https://github.com/abhika-m/FAVA
- RAGBench：论文称约100k条，12领域。官方数据卡含response_sentences、sentence_support_information及其中explanation/supporting_sentence_keys、unsupported_response_sentence_keys、overall_supported_explanation。能辅助支持性判定与证据绑定，不提供等价的完整纠正答案。官方示例annotating_model_name为gpt-4o，不能称人审gold。数据卡CC-BY-4.0，子来源条件分别核对。
  - https://huggingface.co/datasets/galileo-ai/ragbench
  - https://arxiv.org/abs/2407.11005
- RAGTruth：已在用，官方说明约18k自然生成回答，人工词级标注，meta为标注者解释；全量有train/test。不是再下载一遍即可新增完整纠错监督。
  - https://github.com/ParticleMedia/RAGTruth

## 建议替代逐份手写的主线

优先评估FAVA现成训练纠错对，RAGBench补证据句关联与解释；本地作者meta程序保留为部分监督，现有143份助手全文记录保留为适配参考。程序承担标签解析、原句定位、证据键映射和格式验证；无法直接映射的字段留缺失，不为凑满契约调用助手补齐全量中文解释、修正或保留项。只对实际适配异常作针对性审阅，不预先继续手写剩余877份。

这是建议改变数据来源和覆盖策略，尚未执行接入或更改既定研究/分配条件。下载前须明确采用来源及用途范围；现有禁止新增下载的边界仍有效。不得将仅跨度监督改称全文反馈，不能把机器标签或作者错误标注包装为gold。没有实测节省比例，也未证明新增数据能提升Monitor。
