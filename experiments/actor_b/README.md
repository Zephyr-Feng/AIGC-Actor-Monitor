# Actor-B

本目录实现现行方案 Phase I 的最小 Structured Actor-B0。它复用冻结的 Qwen3-VL-8B-Instruct、取证工具、PROBE Evidence-only v1 语义、原始图像和既有工具结果，不修改 Actor-A、Mini FaithBench 或任何 detector。

执行顺序：

1. `prepare_b0_subset.py` 从既有 Actor dev 中固定选择 30 张、30 个互不重复来源组，RAISE/FLUX/SD3.5 各 10 张，并移除旧 PROBE 分类输出。
2. `extract_b0_probe_evidence.py` 在 RTX 4090 上复用冻结 checkpoint、预处理和参考库，为这 30 张生成 Evidence-only 卡片与 crops。
3. `merge_b0_evidence.py` 合并 Evidence-only 卡片与既有 PatchCraft、SAFE、Provenance 输出。
4. `run_b0.py` 在同一 RTX 4090 上运行 prompt-only Structured Actor-B0。
5. `evaluate_b0.py` 生成固定指标和 `ACTOR_B0_BASELINE_REPORT.md`，只做一次是否需要 SFT 的判断。

本阶段不运行 900 条正式实验，不训练 Actor，不开发 Monitor。若 B0 达到稳定门槛，直接冻结；否则只进入一次最小 LoRA/QLoRA SFT。

