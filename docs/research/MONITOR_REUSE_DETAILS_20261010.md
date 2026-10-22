# 本轮复用源码核查与不能照搬的汇总规则

本轮不安装或执行第三方仓库，只阅读固定版本的官方源码，以本项目现有证据编号、时点账本和原解析器实现小模块。私有轨迹不发送检索服务；不把本文方法来源当实验有效性的证明。

- AgentRx，MIT，commit `7a18c79708e7671be15124460f4f7296107c2a55`：[static_invariant_generator.py](https://github.com/microsoft/AgentRx/blob/7a18c79708e7671be15124460f4f7296107c2a55/agentrx/invariants/static_invariant_generator.py)，blob `926ce6355e3f5b4b4e3c1c26e6923f507040fdfb`。其语言模型评定rubric区分CLEAR_PASS/CLEAR_FAIL/UNCLEAR，但汇总丢弃所有UNCLEAR，剩余全通过或没有剩余时为PASS，并要求缺失证据时倾向PASS。本项目需要未知状态，不能复制这个汇总；只复用静态契约与逐项记录思想。已有checker.py也已核读。
- ECT，arXiv:2608.23623v1附代码，Apache-2.0；固定公开包已经缓存并记录hash。models.py采用EvidenceScope、来源arguments/response、SUCCESS/ERROR与VALID/INVALID/UNKNOWN；verifier.py要求scope字段和属性匹配，类型敏感、数值重放。本项目没有其财务运算需求，不复制完整framework；借用来源类型与时点约束、保留未知、证据与声明各自定位。来源与既有许可核查见MONITOR_SOURCE_AUDIT_20261009.json。
- RefChecker，Apache-2.0，commit `1df1b25cee792ba2b171302e31ca4f768bd67703`。此前读取claim级核验提示；ANY支持优先的汇总可能隐藏同声明冲突，不能复制为Monitor强允许规则。只借声明定位/关系核验思想。
- EaE，MIT，Aether-AIS/cotrh-blue-team，commit `7dd11d656756cb74215b4adf14b5d25b0f080576`。借引用抽取后回到上下文核验思想；缺失/空引用应记录失败或未知，不能从覆盖分母中删掉。
- llama.cpp实际后端commit `8a1a9b5126126e5228b95fa909d4b08fac65e8b3`：[JSON Schema转换源码](https://github.com/ggml-org/llama.cpp/blob/8a1a9b5126126e5228b95fa909d4b08fac65e8b3/common/json-schema-to-grammar.cpp)，blob `3349ae4fe0cccb20b9d0da6916ae6509ec77f684`。pattern必须首尾锚定，不支持的正则仅warning后接受任意string。因此不凭Schema有pattern就认定约束实际执行；本轮没有加入未经后端核验的中文正则。反馈合法动作改由新接口编译，理由截句仍单独记录。

R2整体关系核验误伤Actor视觉，R3原子片段定位更具体但显式方向及反馈仍失败，R4静态契约改善接口却丢掉局部来源语义。F是组合候选，需真实结果验证；不能将其中任一代码约束收益说成模型学会了新能力，也不能从相关开发轨迹统计独立准确率。
