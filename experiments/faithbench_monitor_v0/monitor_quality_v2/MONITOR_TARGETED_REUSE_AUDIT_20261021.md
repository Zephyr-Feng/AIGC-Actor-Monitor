# Monitor定向阶段静态复用审查（2026-10-21）

训练授权仍待答。本轮只静态读源码和建立开发参考，没有模型/GPU/SSH/训练/数据划分/API/哈希。

## 可复用与不可直接执行

public_helpers.py的supervised_positions/loss_for/checkpoint及fava_trial.pack可复用；前者实现assistant token监督和适配器/优化器游标保存，后者核对模板前缀。已静态查看这些自有直接模块及旧训练/评估入口的相关代码，未见所查文件中哈希核验调用；不推断未读依赖或数据构建链均已审计，执行前仍须查实际路径。

launch_fava_mixed.py在模块顶层读取固定目录、写approved=true与历史八小时授权、从00952初始化并启动任务，不能导入或运行它来复用函数。旧授权不继承，历史文件不改。fava_mixed_trial写死500更新/8小时/334生成/167评估及旧数据文件；train_feedback写死7612条/14小时，不是改CLI参数即可小试。获明确阶段授权且材料审核完成后，才编写最小新入口，显式读取本阶段授权、不自行制造授权、不覆盖旧输出。

新运行根须不存在；旧权重/优化器/结果不覆盖。检查点清理即使沿用，只能处理本轮新根内自有路径；不为磁盘不足删旧盘。当前只需复用函数，不提前新建通用训练框架。

## 已有具体参考与检查边界

data/monitor_targeted_review_v1_20261021/review_fixtures.json含7条：008三错误、010两预算错误、009一真实冲突保留、一明确构造未知库规模。6段为原Actor自然片段，未知不是原Actor输出。全部只链接原始源文件和模型记录，不复制源卡；human_gold=false、approved_for_training=false、split=null。008/009/010已曝光，不能作独立验证gold。

interface_checks.json保存7项实际源锚、原文位置/范围、分流检查：5 ready、1 retained、1 unresolved，semantic_verified=false。初次检查把uncertain误期望为ready，断言失败未写文件；读真实prepare契约后按unresolved修正检查，不改业务。检查只证明助手参考接口可用，不证明语义gold或训练收益。

## 对下一阶段的修正

128更新是停止上限，不是目标。96合格样本若沿microbatch1/accum16，单遍只有6更新，不能为凑128隐式重复21轮。实际样本/token/单遍更新数与学习率在材料审完后冻结。错误检出、错误修改、未知和有据内容保护须一起检查，不以JSON通过晋级；Actor固定，失败即保留旧版。仍待已提交的训练阶段授权，不重复询问预算，不因自动续轮扩展训练或提示实验。
