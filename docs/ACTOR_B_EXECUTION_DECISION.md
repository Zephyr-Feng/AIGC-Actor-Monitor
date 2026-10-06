# Actor-B 当前执行决策

日期：2026-10-06

本阶段按用户提供的“最小化适配、轻量 SFT、尽快冻结”方案执行。Actor-A、现有工具、Evidence v1、crop pipeline、数据 manifest 和历史实验全部保留，不重新训练或改造。

当前先实现 Structured Actor-B0，并在 30 张独立 Actor dev 图上做一次 sanity check。已有完整 Evidence-only v1 只覆盖旧 300 张 eval；Actor dev 只有旧 PROBE 分类输出。为避免复用已多次查看的 eval，也避免把旧分类结论泄露给 Actor-B，本阶段固定选择 30 张 Actor dev 图，使用冻结 PROBE checkpoint、同一预处理、同一 100 图参考库、`k=20`、95 百分位阈值和 top-3 crop 规则生成 Evidence-only 卡片。该操作是把冻结 Evidence v1 应用于新 dev 子集，不改变 Evidence 定义。

30 图 B0 的用途仅限工程和 orchestration 决策，不用于确认性性能主张。完成后只做一次判断：B0 稳定则冻结；B0 明显不稳定才构造最小 SFT 数据。任何 SFT、正式轨迹采集或 Monitor 工作都需等 B0 结果。

