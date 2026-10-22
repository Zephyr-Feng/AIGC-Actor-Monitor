# Windows 本地沙箱恢复记录

2026-10-19，用户授权检查并修复 `helper_unknown_error: setup refresh had errors`。

## 原因与证据

`.codex/.sandbox/sandbox.2026-10-19.log` 明确记录：刷新运行时读/执行权限时，打开 `cua_node/.../node_repl.exe`、`node.exe` 及 Swift 桥接 DLL 失败，Windows 错误 32（文件正被使用）。这是本地沙箱初始化失败的直接证据；此前自动审批容量不足/超时是另一条执行通道的故障，不能混为训练报错。

## 本次恢复

- 保留 6 个正在使用的原始模块，在原路径放回逐字节比较相同的副本，并保持原 ACL。备份移出运行时扫描目录，位于 `C:/Users/zhangzifeng/.codex/runtime-repair-backups/20261019-131501/`。
- 没有停止其他任务进程，没有改变 `windows.sandbox = "elevated"`、审批规则或网络隔离设置。
- 测试发现：启动 Node 工具内核后，普通沙箱会再次遇到文件占用；调用本对话 Node 工具的 `js_reset` 释放内核后，普通命令恢复。因此当前应优先用普通命令；若使用 Node 工具，结束后先重置其内核再执行普通命令。不能把这次恢复称为上游程序缺陷已永久修复。
- MXC 兼容性单命令探测返回本机不可用，未修改保存配置；未降级为 unelevated。

## 实际验证与限制

普通沙箱 `Get-Location` 和本地 Python 文件读取均退出 0。Python 读取已回收的阶段 1 审计记录，并断言 1,072 条、1,072 个唯一样本、67 更新，输出 `CPU_READ_OK`。Node 本地读取也曾成功，随后按上述方式复现并恢复。

这只证明本地命令执行已恢复，不证明模型权重或最终效果合格。未执行 SSH、GPU、训练、推理或任何直接/替代/间接哈希核验。Git 仍提示用户级 ignore 文件读取权限不足，未扩大该目录权限。

官方排障依据：[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)。
