# Astra 指令与技能调整记录

日期：2026-10-16。用户授权读取两份材料并直接修改适合 Astra 的实际指令。本次为指令维护，不是研究实验或模型迁移执行。

## 依据与阅读范围

搜索并完整读取两份第一方正文，使用 Markdown 原文避免导航内容与工具视窗截断：

1. [OpenAI GPT-6 / Astra 模型指南](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra)，完整读取 Astra 专用 Markdown，包括行为、提示、验证和迁移章节。
2. Eric Provencher，2026-09-11，[Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)。作者在 X 使用 @pvncher；本次采用 OpenAI Developers 原文，不依赖转述。

两文的适用建议是：缩短且区分技能描述、按需加载流程、按任务读取项目背景、明确完成条件和授权边界、避免过度验证。它们没有授权删除项目的数据/用卡限制，也不证明修改后效果已经改善。

已读取本仓库 AGENTS、全局 AGENTS 状态、项目技能描述清单，重点完整审阅并调整相关研究技能入口/参考，以及用户级 self-improving-agent。已读取 OpenAI Docs、skill-creator 和当前 Ponytail 的指导。没有宣称完整审查全部安装技能的所有深层参考。

## 实际生效入口与持久来源

| 来源 | 发现与处理 |
|---|---|
| `D:/Codex/AIGC/AGENTS.md` | 当前仓库规则，已按原有未提交内容改写；保留全部关键研究/服务器边界 |
| 父目录 AGENTS / override | 在所检查的 `D:/`、`D:/Codex/` 与当前仓库未发现额外上级/嵌套规则 |
| `C:/Users/zhangzifeng/.codex/AGENTS.md` | 空文件，保持空白，避免重复加入客户端已有通用指令 |
| `.agents/skills/` | 仓库本地技能；检查描述清单，修改8个相关技能，保留其他工具/专门任务技能 |
| `C:/Users/zhangzifeng/.agents/skills/self-improving-agent/SKILL.md` | 用户级自动维护指导，已收敛到具体复盘/指令修复；影响其他项目的该技能使用 |
| `C:/Users/zhangzifeng/.codex/config.toml` | 只检查相关配置键；文件默认为 `gpt-6.1-sol`、`high`。未改模型/预算/权限，不把配置等同于当前实际服务模型 |
| Codex memories | 所检查的文件目录没有可读持久记忆条目；未读会话日志或内部数据库 |
| 客户端/运行时注入指令、托管插件 | 当前可见指导已纳入冲突检查；未改客户端内部状态、系统指令、插件缓存或认证文件 |

当前会话已注入的技能描述/运行时消息不会因为磁盘文件改变而被撤回。后续任务需要客户端重新发现/加载相应文件；本次不能证明新会话行为或界面刷新已经发生。

## 已完成修改

共15个指令/资源文件，涉及9个技能。

- **项目 AGENTS**：明确在已有授权内完成实现、检查和交付，不重复确认；小修改按相关性读文档。研究新阶段仍读进度与主方案。新增明确的 FULL20 禁止重跑和方案不等于执行授权；保留 GPU、本轮开卡、来源/许可、SSH、凭据保护、原始记录和60秒反馈要求。
- **academic-research-suite**：入口从36,839字节降到3,709字节，保留5个工作流。取消泛研究问题自动进入全套管线，以及强制先进行苏格拉底问答的前置阻塞。命令、Schema、Material Passport、交接/跨模型等细节移到 `codex/adapter-contracts.md` 按需读取，保留真实的作者决定、外发和机构权限约束。
- **ARS model-runtime-policy**：取消“当前仓库配置已选择 Astra”的不实假定；模型由实际运行时及用户设置决定。委派仍须服从当前运行时限制。
- **experimental-design / statistical-power**：入口改成关键设计判断和参考路由；保留实验单位、伪重复、配对/分组、效应假设、敏感性等要求。概念讨论不会自动生成分配表、跑模拟或安装整套依赖。
- **literature-review**：收敛到系统/范围综述；移除每份综述必须生成 AI 配图、至少3数据库、指定 CLI 与固定 PDF 交付的通用要求。系统综述的可复现检索、筛选记录、引用与论据核验仍保留。同步修改其实际加载的 `references/core_workflow.md`。
- **nature-academic-search**：保留6个工作流，工具清单/环境操作改为按需读取；同步更新 manifest 的 `always_load` 和多源检索参考，避免没有专用 MCP 就提前停止。
- **nature-literature-pipeline**：缩短描述，明确普通检索不意味着创建定时任务、外发或重构归档；旧 cron/评分参数作为平台示例。
- **scientific-critical-thinking / scikit-learn**：仅缩短触发描述；保留专业正文。
- **用户级 self-improving-agent**：从17,469字节降到2,572字节，去掉每次技能结束/命令失败都应开启“进化周期”的指令；保留具体失败复盘和有证据的修正。用户明确要求改指令时直接完成授权修改。原 hooks 元数据保留，但不声称其已经安装成全局 Codex hooks。
- 四个技能原有顶层 `compatibility` 声明无信息损失地移到 `metadata.compatibility`，符合当前官方结构校验器；未按依赖说明安装软件。

9个修改技能的描述总长：4,720 → 1,092字符。主入口合计：127,061 → 44,416字节。部分专用协议移为按需参考，因此这些数字表示入口读取负担减少，不是性能、费用或任务效果实测。

## 验证、备份与限制

- 9个技能通过现有官方 `skill-creator/scripts/quick_validate.py` 结构校验；保留名称、许可、工具边界及其他元数据，兼容声明仅调整位置。
- 检查38个本地 Markdown 链接、6个检索路由、5个ARS路由存在；入口版本与 manifest 的 `3.22.0` 一致。
- 15个修改资源均有最终SHA256；14个原有文件保存修改前原文与SHA256，一个新增参考文件记录为新建。
- Windows换行与默认GBK导致的写后/校验失败已处理：文件使用UTF-8，校验器以 `-X utf8` 运行。没有据此修改官方校验器。
- ARS 安装包原有根目录 `VERSION` 缺失，未补造。未运行包级全套CI、真实模型行为评估、跨模型/API或研究实验。

备份与清单位于本地忽略目录：`.cache/astra_instruction_audit_20261016/before/`、`changes.json` 和 `validation.json`。恢复时按清单将相应备份复制回原位置，并仅在确认没有后续编辑时移除本次新建的参考文件；不要用Git重置覆盖其他未提交工作。应用脚本是本次维护的单次工具，不是新的常驻钩子。

`.agents/` 和 `.cache/` 被当前仓库忽略；本地技能修改不会随普通 Git 提交自动分发。未来重装技能可能覆盖本地调整，可凭备份和本记录复核，不能假定已同步到其他机器。

本次没有启动任何模型推理、训练、教师API、研究数据分配或服务器任务；FULL20未重跑。研究仍停在本地Monitor重训练方案已完成、具体执行批次未冻结的位置。
