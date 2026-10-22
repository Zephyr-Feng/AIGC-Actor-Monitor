# 关系SFT实施兼容性核查

2026-10-11。提示对照已完成，新SFT材料方案仍待用户确认。本次只读取旧训练代码、冻结manifest和七条训练记录，保存核查结果；没有生成新训练题、修改旧协议、连接服务器、加载模型或训练。

## 实际监督顺序与提示服从

旧v3冻结`train.json`中的七条answer键顺序均为：

`audit_target → capability_reference_ids → reason → return_reference_ids → status`

七条均有非空reason。准备器的dump使用`sort_keys=True`，包括嵌套answer都按键排序。训练器[tokenize_record](../../experiments/faithbench_monitor_v0/sft_smoke_v1/train_smoke.py)第24行使用`json.dumps(row['answer'], ensure_ascii=False)`，不重新排序，因此送入tokenizer的助手文本保留上面的文件顺序。reason已经先于status。

冻结manifest SHA256 `f10cba3e259695555524652811963b3817490d0011db3de1c772989eeb8a4583`，其中train文件SHA256 `ddbb81eb66f7d17909d91c7f1e8c246568dc3e243a777a9a14a68385495d57a7`与当前读取文件一致；下表四份代码均与该manifest的协议hash一致。旧运行报告中的mask/无截断/20步完成是历史运行证据，本次没有重新训练。

这排除了“旧训练目标总先给status，所以新提示总先给judgement”这个直接解释。当前提示是三字段契约，新标签为judgement；旧五字段及数据/目标均不同，尚不能判断是接口迁移、提示服从、数据覆盖还是优化造成。输出顺序是可观测行为，不代表模型内部先思考什么。

**新材料序列化的实际风险：** 若复用同样的sort_keys准备器保存三字段answer，文件顺序会变成`judgement → reason → return_reference_ids`，静默破坏讨论稿要求的理由先输出。未来新训练路径需要在最终assistant序列化处显式固定两组共同的`reason → return_reference_ids → judgement`，并核查真正送入tokenizer的文本。仅看草稿目标字典的插入顺序，或验证loss mask，均不能证明训练序列顺序正确。此处记录必要实现条件，未改任何冻结代码。

## 可以复用与需要适配的部分

|部分|核实情况|新阶段要求|
|---|---|---|
|assistant-only loss|前缀为-100，全部助手目标token进入loss；理由和引用已经有监督|复用前缀与mask核验，不能将新方案称为首次加入reason监督|
|训练步数|旧run固定20步、batch1，每步取一个样例，shuffle后循环|72条若原样复用，最多20条参与；先冻结每条曝光与更新计划，不自行加步|
|目标序列化|准备保存时嵌套键排序，训练时保留读取顺序|两组共同显式固定最终助手文本的三字段顺序|
|评估解析|从“待审核数据”分隔符提取数据，解析旧契约，并比较status|适配现有抽象题payload与三字段解析，保留raw；旧status正确率不能代替新标签+理由指标|
|保护核验|完整基座/Actor环境快照和只训练语言LoRA的检查已有|复用已有核查；新文件与独立输出目录保存，不覆盖旧adapter|
|预算统计|CPU预检统计每条assistant token，训练日志只有整体loss|材料确认后按实际目标长度与曝光核预算；整体loss降低不是理由正确的证据|

旧训练前后评估各运行一次。未来若两组各自重复生成同样base前测，会增加请求数；应在执行冻结中明确是否复用同条件的base raw，满足同模型、同prompt、同配置才可复用。此处没有决定请求数或发起调用。

## 核查指纹与下一步

|冻结代码|SHA256|
|---|---|
|sft_smoke_v1/train_smoke.py|`123917b5024a0cbbabce49510f585022f696e481e3a1cce41e7b6ffd70ba0b5b`|
|sft_evidence_contract_v3/run.py|`221d26b9c87ab08f03add820f8dae789c6aca2e43bed0c4839693a87b88f49b0`|
|sft_evidence_contract_v3/prepare.py|`20c014c5392e5c7a497f13399eaccfa5ed696c59e4fbc73709621a75e6cfb955`|
|sft_evidence_contract_v3/contract.py|`01e61670f7eb4fa02ada91eb1345419caa88574648caa5940f5ed7bf75c37f70`|

当前可确认的是代码与冻结材料上的兼容性缺口，不是新三字段训练已经可运行。用户确认[材料讨论稿](MONITOR_RELATION_SFT_DISCUSSION_20261011.md)后，先准备并审阅材料，随后用真实tokenizer核查长度、mask和最终输出顺序，再确认训练预算及开卡窗口。待确认问题仍是同一个新增监督/整组划分问题；不把自动goal继续视为用户批准。
