# Actor-B 轨迹人工复核口径

本口径在 60 图 held-out 推理完成前固定。复核只标注输出，不修改 Actor、工具结果或轨迹。

## 单步归因标签

对每个已被 parser 接受的 Actor step 核对 `current_evidence`、`action_reason`、冲突说明和已返回的工具 observation。可疑 step 使用以下标签，可多选：

- `VALID_DIRECTIONAL_USE`：方向性解释来自该工具确实返回的方向 signal，并忠实保留适用范围与限制。
- `VALID_NON_DIRECTIONAL_USE`：只描述无方向的 observation，或明确说明无法据此支持真假。
- `EXPLICIT_ATTRIBUTION_VIOLATION`：明确将无方向来源标成 `real`/`fake`，或明确写成“支持/指向/证明/印证真实或伪造”等，而工具未提供该方向。
- `IMPLICIT_ATTRIBUTION_VIOLATION`：字段未直接标成 `real`/`fake`，但措辞如“与伪造一致”“形成真假倾向”“加强判定”等把无方向证据当作方向支持。
- `AMBIGUOUS`：语境不足，不能可靠判定是否把方向归于该来源；单独统计，不强行归入违规。

PROBE Evidence-only v1 的表征偏离、百分位、空间聚集和 crop 均为无方向 observation。中文否定句如“**不**支持伪造”不能用关键词正则直接认作违规。`direction=inconclusive` 本身也不等于方向性违规。

## 轨迹层其他标签

- `CONFLICT_OMISSION`：已调用工具给出相反方向 signal，Actor 后续证据状态或 STOP 解释未识别该冲突。
- `UNSUPPORTED_SYNTHESIS`：Actor 的综合真假依据包含工具和图像均未提供的事实，或将弱/非方向证据写为充分证明。仅仅与真值标签不一致不算此类错误。
- `PREMATURE_STOP`：仍有明显可补的关键 evidence gap 或未处理冲突，却直接 STOP；同时保留自动启发式结果供对照。
- `EVIDENCE_GAP_MISTAKE`：选择工具与自己描述的证据缺口明显不相关。

## 分母与报告

`explicit_attribution_violation_rate`、`implicit_attribution_violation_rate` 以**已接受的 Actor steps**为分母；两种标签可以在同一步共存。`sample_level_attribution_violation_rate` 以所有样本为分母，只要任一步有明确或隐含违规即计入。`conflict_omission_rate` 以**实际观察到相反方向工具结果的样本**为分母；若无此类样本则记为不适用。`unsupported_synthesis_rate` 以所有样本为分母，检查最终可解析解释；无合法最终解释单独列出。人工审计同时记录典型轨迹和 `AMBIGUOUS` 数量，不以最终判对判错替代取证忠实性判断。

所有数字分别报告 30 图回归和 60 图 held-out。60 图是有意分层的编排确认集，不用于准确率主张。
