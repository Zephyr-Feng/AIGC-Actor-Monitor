# Monitor pilot v2：分离机械约束与语义审核

2026-10-09。研究者已授权简化接口、更强模型未训练基线及微调数据准备。当前仅8例开发诊断；不执行Actor动作，不将开发结果当独立效能评价。Actor保持冻结。

**最新结果：27B同8例已完成。** 8/8生成与JSON解码，110处显式引用编号均存在，6/8完整接口通过；另外两例为finding/check不一致和非法检查状态。8/8原生模板核验成功，19份运行产物备份hash一致，GPU服务已退出、显存0 MiB，可关卡。详见[运行报告](RUN_REPORT_27B_20261009.md)与[聚合结果](RESULT_27B_20261009.json)；下文无卡准备为历史阶段，不能据此重跑。语义待独立人审，不SFT。

研究者后续授权的细审与复审已完成，见[双轮Agent审核摘要](REVIEW_SUMMARY_27B_20261009.md)。覆盖8例、63项适用检查、16条指控及8项建议；由同一助手复审，原响应/接口指标不变，人工gold仍0。

## 对照与信息边界

保留原v1失败结果，先运行冻结Qwen3-VL-8B-Instruct的v2，再运行Qwen3.5-27B Q4_K_M的同接口。v1→v2改变了提示、渲染和机械分工；8B→27B同时改变模型代际、量化和运行后端，不能把差异仅归于参数规模。固定原8例顺序、单次独立上下文、文字输入、greedy、seed42、max_new_tokens4096、repetition_penalty1.05；不格式重试。27B显式关闭thinking。

`inputs.jsonl`与冻结v1字节一致，SHA-256为`a93ed4d266c9848e991c940463c0280b170086c14c8042f56809b613d343bbba`。引用编号覆盖原始允许根的非空叶子，保留所有原始重试、Actor自述和工具返回；不引入GT、silver、后处理投影、当前CALL结果或未来步骤。派生ledger不重复提供，也不能作为独立证据引用。包装保留原始JSON类型和数值。补充的审核范围、预算、可用候选是确定性运行条件。

代码固定不适用项、case_id和总体decision；模型只选择适用checks、问题定位、证据编号、具体缺口和反馈。代码还原原始pointer/quote，再经原v1语义状态一致性、中文、引用和动作可执行性校验。非法编号/字段/动作直接拒绝，不修改原响应。编号可定位并不证明它支持所述判断；机械生成的合法quote或decision不能计为模型学会了引用或总体一致性。

## 入口

| 文件 | 用途 / 当前状态 |
|---|---|
| `protocol.py`、`prompt.md`、`prepare.py`、`run.py` | 已冻结的8例协议、提示、准备及运行；对照期间不修改 |
| `RESULT_8B_20261009.json` | 已完成8B v2的公开聚合结果 |
| `RESULT_27B_20261009.json`、`RUN_REPORT_27B_20261009.md` | 已完成27B v2的聚合结果、运行与诊断报告 |
| `PREPARATION_27B_20261009.md` | 已完成27B无卡准备、来源、hash、验证与下一步 |
| `download_public.py`、`download_parallel.py`、`download_segments.py` | 下载实现及过程路线；正式权重已完整校验，不需重新下载 |
| `build_backend.py` | 保留源码构建尝试，实际部署使用官方预编译包与私有loader |
| `prepare_private_libraries.py`、`preflight_27b.py`、`finalize_preparation.py` | 已执行的私有运行库、CPU词表预检及部署凭据汇总；不会启动推理 |

私有输入、原响应、人审队列和部署凭据位置见[当前交接](../../../docs/SESSION_HANDOFF_20261009.md)，不将它们移动到公开代码目录。

`prepare.py`只读取已锁定v1的8例包，不读取标注。最终包目录使用`private/pilot_v2_locked`。初次跨平台准备发现换行和文件遍历顺序影响manifest字节，已统一UTF-8/LF和排序，旧未运行准备包保留。最终manifest SHA-256：`a0cea96066cc0b20f25e5dd57e1b5489b6a302dd6ac720774760016f85b23a17`。

```powershell
python experiments/faithbench_monitor_v0/pilot_v2/run.py --input-dir experiments/faithbench_monitor_v0/private/pilot_v2_locked
python -m unittest discover -s tests
```

默认入口仅校验，不加载模型。实际执行需要`--run-inference`、backend、model-dir和不存在的output-dir。

## 更强模型部署登记

- 原底座：[Qwen/Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B)，Apache-2.0。
- 量化发布者：[unsloth/Qwen3.5-27B-GGUF](https://huggingface.co/unsloth/Qwen3.5-27B-GGUF)，Apache-2.0；固定revision `3221f178a6b842d04f1fb42f1c413534adcc0a6a`。
- 文件`Qwen3.5-27B-Q4_K_M.gguf`，16,740,812,704字节；原发布仓库LFS SHA-256 `84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806`。镜像传输后核验同hash，不据镜像名称信任权重。
- 运行后端：[llama.cpp b11517](https://github.com/ggml-org/llama.cpp/releases/tag/b11517)，MIT，commit `8a1a9b5126126e5228b95fa909d4b08fac65e8b3`；官方Ubuntu CUDA12.8预编译包及配套运行库，安装在新隔离目录，不修改原Actor venv。
- 本轮文本服务仅监听远端`127.0.0.1:8089`，数据不发往公共模型API；context24576/单槽与8例原生模板核验通过，加载时观察显存17,517 MiB，服务已停止。

无卡准备现已完成，见[27B准备报告](PREPARATION_27B_20261009.md)。模型整份SHA-256与锁定值一致，两个官方后端/CUDA包亦通过校验。Ubuntu22系统库无法直接启动该预编译程序；源码编译在实际0.5CPU/2GiB限额下被终止，未重复尝试。最终在独立目录解包经官方SHA核对的Ubuntu Noble运行库，由私有ELF loader启动后端；`llama-server --version`成功，不升级系统库或修改Actor环境。

无卡准备时仅用GGUF模板和词表预检，最长11,402输入tokens，加最多4,096输出为15,498。本轮原生服务8/8渲染SHA与token数均匹配、GPU加载与实际生成完成；准备脚本本身不启动服务，实际启动参数及cwd记录在私有凭据中。

公开下载脚本设置连接超时、低速终止、总时限、hash与过程日志。重启后按实际断点恢复；大分段低速时主动改用64MB队列，完成整份校验，旧日志和半成品保留。ModelScope同发布者文件hash一致，但实测低速，未作为最终权重来源。

27B原生后端与8B Transformers的重复惩罚窗口可能不同（原生默认最近64 tokens，Transformers按已有序列）；即使数值均为1.05，也不能声称完整生成机制一致。这是模型代际、量化和后端之外的比较限制。

## 评价与微调边界

分别记录：原JSON/适用checks/证据ID选择/完整校验、语义审查问题、耗时和token。语义判断需独立人审，不从接口通过率推断准确率。8例包括同图不同条件和前缀，不能算8个独立来源组。

人审确认仍0。这8例只用于开发与诊断，不作为独立测试再兼作训练。准备待人审材料不等于产生gold，也不启动SFT。正式训练量、来源组划分与未见测试须另外明确，74个Monitor预留组不触碰。

实验设计参考了本仓库experimental-design技能对配对比较、混杂和伪重复的规范；方法来源：[Kassis等，ScientificAgentSkills（2026）](https://arxiv.org/abs/2609.00065)，DOI:10.48550/arXiv.2609.00065。
