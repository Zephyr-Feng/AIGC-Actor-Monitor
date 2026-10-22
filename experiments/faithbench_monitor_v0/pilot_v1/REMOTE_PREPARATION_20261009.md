# Monitor 无卡交接核验

日期：2026-10-09。范围为现有实例的无卡准备；不运行模型推理、SFT或Actor接入。本文接续本地[准备报告](PREPARATION_REPORT.md)，其中“尚未访问服务器”是此前阶段的历史状态。

## 当前克隆与后续推理状态

随后研究者提供新克隆 `connect.bjb1.seetacloud.com:36712`，hostname `autodl-container-c25d449539-d0f8b4f0`。现有密钥交接成功，17个关键hash、准备包协议/制品全部hash、默认CPU入口及4个模型分片核验通过；旧部署/长度记录与目录完整保留。交接记录在Git忽略的 `../private/clone_handoff_20261009_36712.json`。这台RTX4090已开启且交接时0 MiB/0%，与下文旧实例的无GPU状态不同。

研究者进一步明确授权推理后，已从同一运行根目录启动8例各一次文字Monitor审核，PID2431，新输出 `outputs/text_review_v1_20261009/`，日志 `text_review_v1_20261009.log`。未训练或执行Actor动作。下文无卡准备和“尚未推理”描述保留为启动前的阶段记录；当前运行状态以项目进度页为准。

现已完成8/8，原始响应与运行记录取回本地且两端hash一致。PID2431退出，完成时GPU0 MiB/0%，已提示可以关卡。8/8JSON可解码但0/8完整接口通过，后续CPU引用及控制诊断见[运行报告](RUN_REPORT_20261009.md)。没有修复原输出或追加推理，下步停在方案讨论。

## 已完成

- 通过现有SSH密钥连接研究者指定的 `connect.bjb1.seetacloud.com:33082`，未使用或记录密码。实例hostname为 `autodl-container-7b1243b449-c3d2c28c`；地址仅代表本次核验，不是永久入口。
- `nvidia-smi` 返回 `No devices were found`。数据盘50G、已用21G、可用约30G；未改变开关机或GPU状态。
- 检查旧工作目录、冻结配置、B0-D来源轨迹/runtime、两份60行输入清单；下面列出的SHA-256均与本地一致。检查位置没有Git元数据，因此只声称这些文件的字节一致，不声称远端整个工作区干净。
- 复用现有Actor虚拟环境：`/root/autodl-tmp/mini-faithbench-v0/actor-venv/bin/python`。Python 3.12.3、torch 2.12.1+cu130、transformers 4.57.4、accelerate 1.10.1、Pillow 12.2.0。基础Python环境缺少transformers，未安装任何依赖。
- 冻结模型snapshot：`/root/autodl-tmp/mini-faithbench-v0/model-cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`。config hash一致，索引所需4个safetensors分片均存在，大小分别为4,902,275,944、4,915,962,496、4,999,831,048、2,716,270,024字节。未计算整个权重hash，也未加载权重。
- CPU上以公开虚构短句完成 `AutoProcessor.from_pretrained(local_files_only=True)`、chat template和文字编码；输入13 tokens，得到 `input_ids`、`attention_mask`，没有像素输入。模型类可导入，但没有实例化模型。这不是8例真实请求长度检查。

## 已比对文件

远端Actor根目录：`/root/autodl-tmp/actor-b-schema-20261007/actor_b/`。

| 相对路径／对象 | SHA-256 |
|---|---|
| `config/model_config.json` | `5665075c0c81d2dc87d55e833e348eba440c453d65e53e653b98dd6e3d06ceca` |
| `actor_b_protocol.py` | `e32c8d21654d3cbb5c6319c187a193bd9d8d852d296e79010aa88b186e25f93a` |
| `actor_b0_d/run_b0_d_condition.py` | `9d9fd8a8d867433d7675d5bf64ddef58b8f702c1ef5a1f1c87fb5509eefbae62` |
| MASK trajectories／runtime | `d8a832646a3806decd668c5503022587c60bcf57392018fd46e0f81ab7f7c6ea` ／ `693039dd31e2ff8ff2f3f29f76ffc45eda03c991d0814bcd7228eaecd2e856a7` |
| DELAY trajectories／runtime | `38f8acbf4597df494e88501be962695135f204089fe410afe1fa172df54226cb` ／ `b886d0f23ec9aa5a1172e39189833f9579c83cd4481dd4a966c4b0a3058f90e3` |
| RENAME trajectories／runtime | `83fba0e96c644a6a1107ec327581060b566c2a7572634b004357140e0e39c51d` ／ `af08cf140b58e46a38fc8885709c3a511763c297781cbbb50f194071a263b90c` |
| `heldout_confirmation/input/heldout_manifest.jsonl`，60行 | `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531` |
| `actor_b0_d/data/actor_input_manifest.jsonl`，60行 | `b5a8fadd99a04b8c213a95640cc2537e5746a5bce1cb75fab0e099c5153c83c2` |
| 模型snapshot `config.json` | `5cd452860dc1e9c29dd71cc3cef7f39b338b7a40793f7a260655c2d3568f3661` |

## 已完成：8例部署与长度预检

本地已打包23个文件，67,734字节，包括必要源码、冻结配置及已确认的8例文字输入/请求，不含GT、silver标签、图像或74个预留组。文件：`../private/monitor-pilot-20261009-b7a0979e.tar.gz`，SHA-256为 `b3042105abfa116e81413a32621675a00f501a47c7830acb9d52ce11a1a39731`。原输入及manifest未改。

首次SCP在进程启动前被自动审批拒绝，认为现有授权未明确涵盖内部输入传输。没有绕过。随后研究者明确回复“授权”；再次核对hostname、无GPU状态及目的地尚不存在后，完成该次已授权上传。

归档hash一致，23个普通文件按原仓库相对布局解包到新隔离目录 `/root/autodl-tmp/monitor-pilot-20261009/`。不覆盖旧工作区。默认 `run_text.py` 返回 `preparation_valid=true, cases=8, model_loaded=false`，协议源码与输入制品hash检查通过。

用已有venv和冻结snapshot的processor，仅在CPU测量原请求经过实际chat template后的长度，编码方式与runner一致。未加载权重、未调用generate、未添加像素、未安装依赖。

| 既定顺序 | 输入tokens | 输入＋最多4,096输出tokens |
|---|---:|---:|
| terminal_0002 | 8,779 | 12,875 |
| terminal_0005 | 8,362 | 12,458 |
| terminal_0001 | 7,738 | 11,834 |
| terminal_0061 | 10,137 | 14,233 |
| terminal_0041 | 9,646 | 13,742 |
| call_0001 | 4,324 | 8,420 |
| call_0190 | 4,143 | 8,239 |
| call_0385 | 8,776 | 12,872 |

总输入61,905 tokens，单例范围4,143–10,137；全部满足冻结model config的 `max_position_embeddings=262144`。这仅说明配置上下文检查通过，不代表实际显存足够、生成质量可靠或满长度生成已经测试。

远端原始记录为新根目录下的 `deployment_check.json`、`token_preflight.json`；本地副本保存于Git忽略的 `../private/remote_preflight_20261009/`。两端SHA-256一致：部署记录 `5f4b2d54f202343d1771749f5db22f47047122b571150cfb21fcc4cc8b0aad1f`，长度记录 `7be33c92a5c5d6252483fec87b03be1fd31184c9ef44d67edc2e8997483afa42`。新manifest保持 `b7a0979e90622a01562cd90485f838c83aac8b60e8392c081c145fb49cd61e46`。最后核验GPU仍 `No devices were found`，CPU预检进程已退出。

## 续跑位置与下一步

无卡准备完成。实际推理、语义质量、生成耗时和显存仍未验证。下一项用卡任务仅为已确认8例各一次独立文字Monitor审核，不执行Actor动作或训练。预计先预留30–60分钟，属于安排估计而非测量；首例完成后根据实际耗时修正。由研究者开卡后才启动，结束后提示可以关卡。在线Actor接入和调研候选机制另行讨论。

运行位置是上述新根目录；Python使用已核验的Actor venv；模型使用本页snapshot。准备包位于新根目录内 `experiments/faithbench_monitor_v0/private/pilot_v1/`，runner位于 `experiments/faithbench_monitor_v0/pilot_v1/run_text.py`。后续推理必须显式传入 `--run-inference` 和新的输出目录；当前未运行该命令，也没有Monitor推理结果。
