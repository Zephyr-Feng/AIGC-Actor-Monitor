# Actor-B0-D 冻结输入与运行记录

## 运行状态

**尚未开始 GPU 条件运行。** 本文件先记录本地可核验的冻结资产。启动前须连接用户当前开卡的 AutoDL 克隆，只读核验模型、B0-C tool cards、图像与缓存工具输出；缺失或 hash 不匹配时停止，不覆盖旧文件。当前已知旧入口 `connect.bjb1.seetacloud.com:33082` 在上一阶段之后拒绝连接，不能视作当前有效入口。此处不记录任何凭证。

## 冻结配置

| 输入 | 冻结值 |
|---|---|
| Actor | Qwen3-VL-8B-Instruct |
| Model revision | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` |
| Local model config SHA-256 | `5cd452860dc1e9c29dd71cc3cef7f39b338b7a40793f7a260655c2d3568f3661` |
| Canonical B0-C prompt + tool cards + schema + generation SHA-256 | `739abe138a0a40b1c21a77308565165bb309a0f45d28f1cf2d0da5354e8da1ea` |
| Actor schema file SHA-256 | `d0ea87912099ccc058045f266bc904517f8abc209eea54ac707c44e2fc55b9b5` |
| Generation config file SHA-256 | `fb8b26b4b5d44d1bddf55215b39c50ee80b19371a902f5f4bc20a49dfb72b523` |
| Generation config | seed `20261006`; max actor steps `6`; max tool calls `4`; max format repairs/step `1`; max new tokens `768`; greedy decoding; repetition penalty `1.05` |
| B0-C Python runtime | PyTorch `2.12.1+cu130`; Transformers `4.57.4` |
| Minimal STOP policy | Preserve legal raw `real/fake` STOP verdicts; same-model projection only for invalid verdicts. No all-STOP forced choice. |
| Evidence v1 checkpoint SHA-256 | `c8caa9bad54c029e4d22e1909c4673e46a239d8419a986e0ab461d423a450156` |
| Evidence v1 official repository commit | `b145f7130004c02725e9b3703954a3329ebf56de` |
| Evidence v1 config file SHA-256 | `4388677edb2f3e75e580777c2a8e8bd499fd9196a1e3730858acbc86138ff0fc` |

The original B0-C tool-card JSON is not in this local checkout. Before inference, retrieve it from the active cloned instance and record its file SHA-256. Recompute the canonical B0-C hash from the frozen system prompt, exact tool cards, schema, and generation config; it **must equal** the value above. Also verify the remote model config, 60 image hashes, Evidence v1 outputs/crops, cached tool-results SHA, and runtime versions. No prompt/schema/crop/detector/model patch is authorized in this stage.

## Data and order

- B0-C manifest SHA-256: `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`
- B0-C cached tool-results SHA-256: `94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`
- B0-C raw trajectories SHA-256: `276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`
- B0-C frozen minimal-policy replay SHA-256: `89fbe915fdf32505b20da820a50236c2a2238fc3fa72ab0e4bce06447464f130`
- B0-D diagnostic manifest SHA-256: `7730863c14b4781202b48c1fb95a38e52a54ec3c5966d1c307f819f16d52a807`
- Actor-facing manifest SHA-256: `b5a8fadd99a04b8c213a95640cc2537e5746a5bce1cb75fab0e099c5153c83c2`
- Derived FULL trajectory SHA-256: `24b08992bf3add37e0644f6c9fe1b397af374ddaee312f1d1fad82b24658af34`
- Cohort: 60 existing B0-C images, 20 source groups; this is a paired diagnostic subset, not a new independent held-out.
- Diagnostic quotas: EASY 12; PROBE proxy 12; TOOL_DISAGREEMENT 16; WEAK_EVIDENCE 10; DIFFICULT_SOLVABLE 10. Historical PROBE-error overlap is 0. PROBE cases are explicitly described as difficult proxies.
- Monitor-reserved source groups: 74, untouched.
- All conditions preserve the diagnostic manifest order. FULL reuses B0-C outputs; only PROBE-MASK, PROBE-DELAY, and TOOL-RENAME require inference.

## Code provenance

- B0-C tool-source bundle SHA-256: `b24bde84bf39b1c47d2f2a895b63e97585bebfac5b68a3c2a8165c8991466f75`
- B0-C component hashes are recorded in the pre-run history below and can be recomputed from the listed source files.
- B0-D runner SHA-256: **fill after code commit, before run**.
- B0-D evaluator SHA-256: **fill after code commit, before run**.
- Git commit used for the run: **fill after code commit, before run**.
- Active AutoDL instance, host and port: **fill after user opens a card and endpoint is verified**.
- Verified remote tool-card file SHA-256 and recomputed prompt SHA-256: **pending remote preflight**.
- Condition-specific prompt/schema/card hashes and run fingerprints are written to each condition's `runtime.json` before final evaluation.

## 2026-10-07 pre-run history

| Frozen component | SHA-256 |
|---|---|
| `experiments/actor_b/run_b0.py` | `4e4b4e5ecf169672d311229a94ebfa210ec1c6775a3ff04f3fc046cc9de9cfb5` |
| `experiments/actor_b/actor_b_protocol.py` | `e32c8d21654d3cbb5c6319c187a193bd9d8d852d296e79010aa88b186e25f93a` |
| `experiments/actor_b/contract_replay.py` | `a4a50858e3acac2b43181cdd71c699bec3df46c208f714bbbc2711480c650cdf` |
| `experiments/actor_b/apply_minimal_contract_repair.py` | `65179ddb87004cbf408f8232ef2dd07c61420795017aaf760c2689c106c33bc3` |
| `experiments/actor_b/merge_b0_evidence.py` | `1527f8110571e6c37aac13e5f7b508c6be609be4493a477d3172ab9e0547c6a6` |
| `experiments/actor_b/extract_b0_probe_evidence.py` | `6524e7a5d0fb615c57e22f9d82d0a765edec4c768fede309c2330a87dca45f35` |
| `experiments/actor_b/reuse_heldout_evidence.py` | `71339806720df487b8bb06815bbe9b6bc4422e1058cfcc16bef230306501cdad` |
| `experiments/probe_evidence_v1/build_evidence.py` | `5365b2a31fcaf5d6ee48e40dc5ec9852aa939071de7320b51439136ce24876c8` |
| `experiments/probe_evidence_v1/extract_features.py` | `ca306e3d3f2e0e09c371fdd6b4a7768928411087ddf2b77d68fe25044a789f67` |

Local code and evaluator tests passed before GPU readiness. The evaluator smoke test re-used the FULL fixture in all four slots only to validate file alignment and output generation; it is not a B0-D condition result and must not be reported as one.
