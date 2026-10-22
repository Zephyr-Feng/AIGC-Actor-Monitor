# Monitor文字试做：无卡准备报告

日期：2026-10-09。授权范围：文字输入＋现有冻结Qwen3-VL-8B-Instruct＋既有8开发例。

## 实际完成与验证

- 建立运行快照、证据记录、审核与拟干预分离协议、独立文字运行入口和响应复核入口。
- 成功派生5terminal＋3call_prefix，顺序沿用原案例索引；原输入重建逐例一致，四条件来源文件hash与原manifest一致，相关CALL前缀预算交叉核对通过。
- 新增12项测试通过；全仓库63项测试通过。覆盖受阻CALL计费、格式重试、缺失旧状态字段、同step时间边界、预算不一致、别名、不可用/重复工具、额度耗尽、非法STOP、引用和未决状态。
- 默认运行入口校验通过，`model_loaded=false`；最长请求25,867字符。此数值是字符数，尚未测实际token数及显存。
- 准备包与逐样本请求受`experiments/faithbench_monitor_v0/.gitignore`的`/private/`规则保护，未上传。

## 哈希

| 文件 | SHA-256 |
|---|---|
| 原private/manifest.json，保持原值 | `5359eb808e00f5d21447434720c3a0d5b8a74045470717d38811a76fbdd44e6e` |
| 新private/pilot_v1/manifest.json | `b7a0979e90622a01562cd90485f838c83aac8b60e8392c081c145fb49cd61e46` |
| 新private/pilot_v1/inputs.jsonl | `a93ed4d266c9848e991c940463c0280b170086c14c8042f56809b613d343bbba` |

新manifest另记录协议源码、请求文本、原来源文件与冻结模型信息。没有读入silver标注或身份映射；原始工具observation中的盲化sample_id保持原样。没有加入GT、预审标签、后处理verdict或当前CALL结果作为审核输入。

## 限制与下一步

没有模型推理、SFT、服务器访问或实际Actor干预。全部拟干预仍为未执行建议；测试只验证接口与控制约束，不验证科学判断。没有证明Monitor收益、证据充分性规则或工具独立性。人工金标签仍0，B0-D gate仍INCONCLUSIVE。

下一步：获取并无卡核验当前AutoDL入口与冻结模型，安排研究者开卡后对8例各做一次独立Monitor审核；随后逐例核对语义质量。Actor接入试验和扩大开发集需要单独确认。
