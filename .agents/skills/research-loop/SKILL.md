---
name: research-loop
description: 基于 Actor/Monitor 项目的已有证据推进科研迭代，提出可证伪假设、选择有区分力的实验、修改必要代码并据结果决定下一步。适用于接续研究、实验复盘和范围已授权的自主科研；只查状态时不启动实验。
---

# research-loop

首要优化：在可信、可复现和授权边界内，减少每轮所需上下文，把推理用于选择下一步。使用中文解释证据与不确定性。一个核心 Skill 即可；只有反复观察到独立工作流才拆分。

## 先取小上下文

项目根目录为 `D:/Codex/AIGC`。下列命令从项目根目录执行；换目录时使用脚本绝对路径。

```powershell
python -B .agents/skills/research-loop/scripts/loop.py context
```

返回当前目标、默认/开发最好/独立验证状态、最近两轮和当前进度标记。若 `snapshot_current=false`，只读 `docs/PROJECT_PROGRESS.md` 顶部最新相关段落及所链结果，更新 `docs/research_loop/state.json` 的摘要与标记；不重读历史。续接目标不同，先更新目标与相关记录范围。

按需才读：[项目教训与代码入口](references/project-notes.md)（选新假设或遇到类似失败）、[运行与授权边界](references/execution.md)（执行、预算、服务器、晋级）。常规续轮无需加载其他 Skills、协议全文或全部日志。新研究问题/新机制才定向核对原论文、数据许可和已有实现，现有文献复盘只作索引。

## 推理驱动下一步

1. 从最近失败定位**阶段**：输入/监督 → Monitor识错 → 反馈定位与建议 → Actor采用 → 完整最终稿。区分观察、可能原因和已排除原因；没有区分原因的证据时保留多个解释。
2. 提出一个主要假设和一个最有力的竞争解释。优先选能让两者产生不同预测的最便宜检验：已有输出/监督对照、CPU单测、缓存回放，最后才是新生成或训练。写清支持结果、反证结果及各自下一步；“再试更多”不算理由。
3. 冻结本轮最小比较：变化项/保持项、输入与来源组、初始化和提示/长度/硬件、主要语义指标与损害指标、停止条件、授权范围和预算。通常一份短 JSON/已有方案足够；多因素共同改变只能评价整体配方，不能声称单因果。复用原输出先核对实际输入、参数和曝光历史。
4. 检查必要调用者、改动和现有测试；只改必要代码，不自动回滚整个工作区。普通原型完成针对性功能/输入/有限数值/样本完整性检查即可。核心算法、监督矛盾、训练内失败或异常时，深入到相关原始样本、loss/监督位置和实际加载路径，别机械重复全部检查。
5. 用脚本压缩日志、做配对统计、核预算；LLM只读汇总及足以判别原因的原始案例。机械结果不是语义正确证明。保留漏检、误报、未决与回退；不抽掉失败样本。
6. 根据反证选继续、换假设或停止。相同问题/配置已有结果就复用；没有新信息的同源换词、追加epoch和加长生成应停止。停止一条支线不等于研究目标完成。证据不足时记录“未决”，不要为维持循环而制造实验。

## 记录与复现

`docs/research_loop/experiments.jsonl` 是追加记录；每轮记录一个短条目，不生成长报告。使用：

```powershell
python -B .agents/skills/research-loop/scripts/loop.py record --record <本轮短记录.json>
python -B .agents/skills/research-loop/scripts/loop.py summarize --paired <配对审阅.json> --expected <冻结ID列表.json>
```

短记录字段为 `id,track=project,hypothesis,change,result,validation,evidence,decision,next`；decision 为 reject/continue/candidate/stop。evidence 指向仓库内实际文件，内含配置、命令、来源与曝光、原始输出和统计；记录器只验证结构及文件存在，不认证内容。补充竞争解释/预测可放本轮已有方案中，无需另建文件。更正用新ID追加，保留旧记录。

配对统计输入为 JSON 列表，每行含 `id,source_group,split`（development/independent）和六个布尔字段：`correct_before,self_review_correct,correct_after,format_valid,unknown_case,unknown_preserved`。这些必须来自逐例审阅，不能从JSON通过率猜测；未决案例先单列，不能强制转成错误/正确。冻结 expected 列表须对应声明的评分子集，同时在证据中报告未决和缺失总数。脚本输出修复/损害、来源级胜负和未知保护；它不会验证人审身份或语义。

状态文件仅保留下一轮需要的目标、最近证据指针、默认与最好状态。每个明确阶段结束更新 `docs/PROJECT_PROGRESS.md` 一条；不重复记录轮询或搬运全历史。状态和本地记录都是上下文，不是授权凭证。

## 执行、验证与晋级

首版工具只运行内建纯CPU合成模拟，无真实模型、shell或网络入口。模拟命令：`python -B .agents/skills/research-loop/scripts/loop.py mock --proposal <方案.json>`；方案样例见持久记录 `docs/research_loop/mock/*/proposal.json`。模拟的有限候选仅验证流程，研究假设仍由 Codex 判断。

真实训练/推理须有明确现行授权。用户已取消独立执行器前置要求，可沿用已授权的SSH和既有脚本执行；loop.py没有真实backend仅是该工具的功能范围，不代表禁止其他已授权入口。每批固定输入、比较条件、调用/更新数量和停止条件，设置适当超时，保留原始输出，结束后复盘；不限总预算不等于无限重复或自动扩展。JSON、提示词和看门狗是记录与运行保护，不是不可绕过的安全机制。细节按需读 execution.md。只查状态或修改规则不启动实验，本 Skill 不接管其他聊天任务。

普通实验：做上述必要自动检查。异常/核心改动：定向深查。**晋级**：读取原冻结评测协议，做完整来源配对、强Actor同条件对照、语义净收益与新增损害、未知保护及既有105/32不退化检查；未参与选型的来源/独立复核和预算/产物证据齐备才提交晋级决定。开发个案不能冒充独立验证，模拟永不晋级，不能修改冻结基线或协议来过关。

用户已允许科研原型跳过 Superpowers 的重复设计审批、计划文档、强制多Agent和重复检查。按此授权就地完成必要推理、实现与验证；只在范围、风险或结果需要时升级流程，不全局停用或改写其他技能。预算/安全/冻结门槛不在可跳过范围内。
