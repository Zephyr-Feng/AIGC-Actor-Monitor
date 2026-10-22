# 27B Monitor 无卡准备完成记录

2026-10-09。状态：`prepared_no_inference`。同一实例 `connect.bjb1.seetacloud.com:36712`，hostname `autodl-container-c25d449539-d0f8b4f0`；最后GPU探测为 `No devices found`。未启动27B服务、模型生成、训练或Actor动作。

## 已验证产物

| 项目 | 验证结果 |
|---|---|
| Qwen3.5-27B Q4_K_M | 16,740,812,704字节，整份文件SHA-256与固定发布版本一致 |
| llama.cpp b11517 | 官方后端包与CUDA12.8配套包SHA均一致，源码HEAD与固定commit一致 |
| 私有运行库 | 三个Ubuntu官方包SHA一致，独立解包；私有loader运行`llama-server --version`返回0，build11517/commit8a1a9b512 |
| 8例CPU词表预检 | 全部可编码，3,738–11,402输入tokens，合计66,226 |
| 上下文预检 | 最长输入加4,096输出为15,498，8/8在计划24,576上下文内 |
| 本地备份 | 六份JSON凭据取回，SHA与远端逐一一致 |
| 部署辅助检查 | 新辅助脚本语法通过；后端帮助确认全部计划启动参数存在；本轮准备目录无残留进程 |
| 数据盘 | 完成时剩余7,264,858,112字节；无需清理旧Actor材料 |

预检只读取GGUF模板/词表与冻结开发请求，不读取权重张量作计算。模板先用Python Jinja2渲染，再由固定源码对应的原生`llama-tokenize`以`vocab_only`编码。原生服务的Minja渲染和实际token usage仍需GPU阶段核对，不能将CPU结果当成显存验证。

输入仍为同一8例、同顺序、单次独立上下文、文字输入；最终准备manifest为`a0cea96066cc0b20f25e5dd57e1b5489b6a302dd6ac720774760016f85b23a17`。原输入SHA仍为`a93ed4d266c9848e991c940463c0280b170086c14c8042f56809b613d343bbba`。v2协议、prompt与运行器未因部署问题改动；协议阶段全仓库69项测试已通过。

## 来源与锁定版本

- 原模型：[Qwen/Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B)，Apache-2.0。
- 量化模型：[unsloth/Qwen3.5-27B-GGUF](https://huggingface.co/unsloth/Qwen3.5-27B-GGUF)，Apache-2.0；revision `3221f178a6b842d04f1fb42f1c413534adcc0a6a`，文件`Qwen3.5-27B-Q4_K_M.gguf`，SHA `84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806`。
- [llama.cpp b11517](https://github.com/ggml-org/llama.cpp/releases/tag/b11517)，MIT；commit `8a1a9b5126126e5228b95fa909d4b08fac65e8b3`。
- `llama-b11517-bin-ubuntu-cuda-12.8-x64.tar.gz`：SHA `10565a6a0c231ea10625ff7de128c0c6ee65e8dab60f59b88f5d5a1f8e028e91`。
- `cudart-llama-b11517-bin-ubuntu-cuda-12.8-x64.tar.gz`：SHA `5be78009a9d636e50f2caefc1b18c613a58ab698fe5655f0b950ee9d2c6f8f6a`。
- 官方Ubuntu Noble [libc6下载页](https://packages.ubuntu.com/fr/noble/amd64/libc6/download)：`libc6_2.39-0ubuntu8.9_amd64.deb`，SHA `ff5557d99b51f761c4b7c92368b9cc45565eda17df9bf9eb4b134d09825008be`。
- 官方[libstdc++6下载页](https://packages.ubuntu.com/noble/amd64/libstdc%2B%2B6/download)：`libstdc++6_14.2.0-4ubuntu2~24.04.1_amd64.deb`，SHA `a51f8de7829211db961a31f02158058ad1a95f92ac6d0a5dff6350e2821c54c0`。
- 官方[libgcc-s1下载页](https://packages.ubuntu.com/noble/amd64/libgcc-s1/download)：`libgcc-s1_14.2.0-4ubuntu2~24.04.1_amd64.deb`，SHA `aa7fadbe33b78bcf99885318040601c550c208929565b179891d9a3cc2aa68cd`。

## 超时与失败如何处理

无卡重启中断下载后，从日志确认的实际字节断点恢复，没有将稀疏文件的逻辑大小当作下载完成。大分段低速时停止自己的下载进程组，原地改为64MB队列；HTTP 503有限重试后完成，最后验证整份权重。旧日志和半成品保留。HF直连、镜像及官方学术加速的不同传输尝试有记录；[AutoDL官方学术加速](https://www.autodl.com/docs/network_turbo/)只用于下载子进程，不改全局环境。ModelScope同发布者文件固定revision和SHA一致，但实测仅约0.6MB/s，未切换正式来源。

原后端启动失败原因是系统缺少GLIBC_2.38/GLIBCXX_3.4.32；源码归档超时后改为固定tag浅克隆并验证HEAD。编译器被Killed终止，实际容器限额为0.5CPU/2GiB，未反复编译，亦不据主机128核/约1TB内存输出判断可用资源。最终复用官方二进制，通过私有运行库解决兼容性，系统库与Actor venv保持原状。第一次词表预检因不适用的CLI选项终止，查固定版本源码后去掉该选项，完整8例重新预检成功；失败目录保留。

## 可追溯凭据

远端公开准备目录：`/root/autodl-tmp/monitor-v2-public-20261009/`。

本地被Git忽略的备份目录：`experiments/faithbench_monitor_v0/private/remote_preflight_v2_27b_20261009/`。逐例请求、渲染文本和待人审材料留在private，不进入本报告。以下六份记录本地/远端SHA一致：

| 文件 | SHA-256 |
|---|---|
| verified_model_download.json | `2c50cfe689364e3c0a9904e4dd93e6b902a113298503a88c6cdf1910284af21f` |
| verified_runtime_downloads.json | `f2edd0b032a8a5b4946b34de413c1e82ce119746ab4d91e5207fffdb103f62ee` |
| private_libraries_record.json | `d05cded2b61da06b2eb88b77400b92d54c4383850e233c6aebb4302d5417717c` |
| verified_downloads.json | `de89b1668197b82a6ef20277f312dc5fdc07e363be51f35cdb073bf8f7e4b480` |
| deployment_prepared_20261009.json | `0872e3486a948a3f169fb046cff29877cc52f831842089757c09bf43a740638f` |
| token_preflight.json | `3b7084fc10fffc5d5945ab20fe9e1f9766bddeef84e4c463d84109b91f99e9e1` |

## 下一步与解释边界

告知研究者后由研究者开RTX4090，预计15–30分钟完成加载核验、8例未训练Monitor各一次生成及备份；这是工作窗口估计，首例后按实测修正。先核验显存和模板；若加载失败，停在该步骤，记录日志/资源证据，不擅自改变量化或模型。服务只监听`127.0.0.1:8089`，计划24576上下文、单并发、关闭thinking。生成保持greedy、seed42、最多4096tokens、重复惩罚1.05、无格式重试；不执行Monitor提出的Actor干预。

8B完整接口已通过4/8，语义仍需人审；27B尚无结果。模型代际、量化、后端及重复惩罚窗口均构成比较限制，不能把后续差异仅归因于参数规模，亦不能从8例接口通过率推断独立测试准确率。8例待人审材料已准备，gold仍空、人审确认0、训练记录0；不启动SFT，74个预留来源组保持不动，B0-D gate仍为INCONCLUSIVE。
