# 两种理由监督SFT执行冻结

2026-10-11，用户“可以”批准[训练预算](../../../docs/research/MONITOR_RELATION_SFT_EXECUTION_DISCUSSION_20261011.md)，含上传14601实例和25–40分钟4090窗口。冻结v2材料，普通正确理由/显式关系理由两个新adapter，各216更新，共432更新和204新生成；旧48 base reason_first原始结果精确复用，合计252评估条件。不是独立测试或人审gold，不默认采用。

同一seed42、每遍完整72条洗牌，三个epoch，两组逐步曝光对应；仅最终评估。NF4 double/BF16、SDPA、语言q/v LoRA r8/alpha16/dropout0.05、AdamW 2e-4、batch1/累积1、裁剪1、assistant-only loss、4096上下文、greedy384。共同prompt/标签/引用，assistant文本固定reason、return_reference_ids、judgement。监督token每遍3404/4366，差28.26%，仅比较完整方法。

本地预检验证144训练序列mask、目标顺序、216更新覆盖、84评估长度；旧48提示全文及长度匹配，旧运行器hash与NF4/BF16/SDPA/disable_adapter/greedy384路径验证。保留异常输出，不修补或重采样。base预留36执行一次，两adapter各84；不额外生成训练题。

私有目录relation_sft_comparison_20261011，inputs SHA `f5a3551fb706cc8dc94c989dad1e5b6ee2a89c3cd9555c7294a7283f8f63d40c`。准备器独占创建，不重复运行。远端新trial/operation/cpu_preflight均前缀relation_sft_comparison_v1，根 `/root/autodl-tmp/monitor-sft-smoke-20261010`；已存在文件只能核hash，不能覆盖。保护25基座/Actor环境文件、旧adapter全部文件、50协议文件。Actor不执行，74预留真实组/GT/身份映射禁读。

raw后核标签、理由与充分引用，首审锁及同助手非盲复审，0独立人审。候选门槛：原48联合含引用至少比base多1题、整组多1；预留36联合含引用不下降，两集误支持/误拒绝不增加。另直接比较普通/关系adapter，持平/退化如实记录；预留base全对时保持全对只是保留能力。结果另存报告，不依据输出改条件。
