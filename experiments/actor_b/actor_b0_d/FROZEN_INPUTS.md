# Actor-B0-D 冻结输入与运行记录

## 运行状态

**2026-10-07：PROBE-MASK、PROBE-DELAY、TOOL-RENAME 已各完成 60/60。** 用户开卡后核验 `connect.bjb1.seetacloud.com:33082` 可达；模型、B0-C canonical prompt、schema、generation、60/60 原图哈希、60 张 Evidence cards、180/180 crops、缓存工具输入与 B0-C 轨迹均通过核验。三组轨迹/runtime 均取回并与远端 SHA-256 一致，样本顺序对齐，运行器哈希一致。推理进程退出，GPU 最终为 0 MiB / 0%。正式评价已生成 240 条条件记录、20 图 × 4 条件的 80 行盲审包和 827 条工具选择审计行。人审尚未完成，当前 gate 为 ACTOR_B0_D_INCONCLUSIVE。此处不记录任何凭证。

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

The original B0-C tool-card JSON is not in this local checkout. During the 2026-10-07 run, its remote SHA-256 was verified as 4bea66b6aad42ff93ed7a4ff128b5094550e81fb72f1b8452fdfb464a98867fb; the recomputed canonical hash matched the frozen value above. Model/config, image hashes, cached Evidence/crops, tool results, runtime versions and input order were verified before inference.

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
- B0-D runner SHA-256: `9d9fd8a8d867433d7675d5bf64ddef58b8f702c1ef5a1f1c87fb5509eefbae62`
- B0-D pre-run evaluator SHA-256: `d913bf1b33c023ceb7381e80e39c51d0c971d9f0a1c36efdd41b5adc29d15b10`; reporting correction below records the current evaluator.
- B0-D preparation/control bundle SHA-256 (four Python controls, canonical path/hash map): `0666b74f4dd375b2ad35f9b905c02da409449a75860eefe039daa8fe45264b7b`
- Git source commit for the run: `1c26bca4bae2bde5f94f409e4cf430fdaabd98ec`. Any later commit before execution is documentation-only; verify these script hashes again before running.
- Active AutoDL instance, host and port: `connect.bjb1.seetacloud.com:33082`, verified on 2026-10-07.
- Verified remote tool-card file SHA-256: `4bea66b6aad42ff93ed7a4ff128b5094550e81fb72f1b8452fdfb464a98867fb`; recomputed canonical prompt SHA-256: `739abe138a0a40b1c21a77308565165bb309a0f45d28f1cf2d0da5354e8da1ea`.
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

Local code and evaluator tests passed before GPU readiness. The evaluator smoke test re-used the FULL fixture in all four slots only to validate file alignment and output generation; it is not a B0-D condition result and must not be reported as one. The source commit above contains the B0-D scripts; this freeze record may be committed afterward without changing those scripts.

## 2026-10-07 GPU run checkpoint

The exact cards were verified at `/root/autodl-tmp/actor-b0-20261007/actor_b/config/tool_cards.json`. Image root: `/root/autodl-tmp/actor0-bfree-20261002/data` (manifest paths begin with `eval/`). Crop root: `/root/autodl-tmp/probe-evidence-v1/output/evidence`. Model snapshot: `/root/autodl-tmp/mini-faithbench-v0/model-cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`. Interpreter: `/root/autodl-tmp/mini-faithbench-v0/actor-venv/bin/python`. Cached Evidence outputs are reused; no detector or crop generation is run.

Remote run directory: `/root/autodl-tmp/actor-b-schema-20261007/actor_b/actor_b0_d/`. The clone lacked `contract_replay.py` at its Actor root; the exact frozen helper (`a4a50858e3acac2b43181cdd71c699bec3df46c208f714bbbc2711480c650cdf`) was placed in the new B0-D directory. The runner, helper and GT-free Actor manifest were transferred; existing code and results were preserved. TOOL-RENAME uses a detached process with `tool_rename.log` and `tool_rename.pid` so a chat interruption does not stop the run.

| Condition | Records | Raw / effective parse | STOP projections | Inference seconds sum | Trajectory SHA-256 | Runtime SHA-256 |
|---|---:|---|---:|---:|---|---|
| PROBE-MASK | 60 | 57/60 / 60/60 | 3 | 2037.68 | `d8a832646a3806decd668c5503022587c60bcf57392018fd46e0f81ab7f7c6ea` | `693039dd31e2ff8ff2f3f29f76ffc45eda03c991d0814bcd7228eaecd2e856a7` |
| PROBE-DELAY | 60 | 52/60 / 60/60 | 8 | 2607.43 | `38f8acbf4597df494e88501be962695135f204089fe410afe1fa172df54226cb` | `b886d0f23ec9aa5a1172e39189833f9579c83cd4481dd4a966c4b0a3058f90e3` |
| TOOL-RENAME | 60 | 59/60 / 59/60 | 0 | 2276.64 | `83fba0e96c644a6a1107ec327581060b566c2a7572634b004357140e0e39c51d` | `af08cf140b58e46a38fc8885709c3a511763c297781cbbb50f194071a263b90c` |

PROBE-MASK material hash: `b2a71a84b0238162c239bece146dec11a819c8d20b4ca67685f91dafd455d12b`. PROBE-DELAY material hash equals B0-C. PROBE-DELAY recorded 28 blocked first-PROBE attempts and 0 unavailable-tool attempts. These are runtime counts; tool-selection quality, premature STOP and faithfulness require the human audit.

## Offline reporting correction (2026-10-07)

Before the four-condition evaluation, inspection found that the original `probe_first_immediate_stop` numerator counted every PROBE-first trajectory with a final STOP, even when other tools followed. It now requires one successful PROBE call followed by STOP with no subsequent CALL_TOOL request (including rejected requests); the frozen STOP projection and STOP format repair remain allowed. Four targeted regression cases distinguish immediate STOP, later successful calls, rejected later calls and projected STOP. The corrected evaluator SHA-256 is `bb9a12fbcaa1205f835b6f865ee6dd05a26fcb6d4b9775f25ce831de8303beeb`. The pre-run bundle hash above remains a historical source record; inference runner, inputs and policy hashes are unchanged.




Final evaluation (2026-10-07): corrected evaluator SHA-256 bb9a12fbcaa1205f835b6f865ee6dd05a26fcb6d4b9775f25ce831de8303beeb; aggregate metrics at evaluation/metrics.json; report at report/ACTOR_B0_D_REPORT.md. Current gate: ACTOR_B0_D_INCONCLUSIVE because the required human review remains pending. The audit packet and per-sample/call-level tables stay local and are excluded from GitHub.
