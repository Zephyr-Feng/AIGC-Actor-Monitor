# 条件式 schema 候选中止记录（2026-10-07）

本候选只在原 JSON schema 中增加 CALL_TOOL/STOP 的条件分支；system prompt、工具卡、生成参数与模型未改。schema SHA-256 `c219d162bf2e6414178768ff86096a038a9c10a36997aa5e4e68761425cb767e`；模型实际读取的 prompt material SHA-256 `e3983f3cd840c4fdbdf60b5b10494c07721084d0bb54e70b156787b110da418d`。

前 16/30 条已写入远端 `actor-b-schema-20261007/actor_b/baseline_b0_schema_fixed/outputs/records/`。其中 1 条在有限 retry 后仍输出非法 `final_verdict=inconclusive`，另 1 条重复请求已调用工具且 retry 后仍重复。两类均由 parser 正确拒绝。这已达不到本轮 30 图 `parse_success=100%` 的工程目标；继续占卡不会改变该结论，故核对进程 PID 后以 SIGINT 停止，保留部分记录，不将其纳入最终 30 图指标。

原始 schema 已恢复到 SHA-256 `d0ea87912099ccc058045f266bc904517f8abc209eea54ac707c44e2fc55b9b5`；后续完整回归在 `baseline_b0_schema_fixed_v2/` 单独运行，只保留 parser 对 `final_confidence=null` 的契约对齐修复。没有修改 evidence reasoning prompt、工具定义或任何取证结果。
