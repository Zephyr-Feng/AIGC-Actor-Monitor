# Actor-B Contract-Constrained Freeze Gate Report

**Date:** 2026-10-07
**Decision scope:** The user-approved policy that preserves legal original STOP verdicts and repairs only invalid verdicts.
**Final decision:** `ACTOR_B0_C_FREEZE`

## A. Implementation and frozen inputs

The frozen Qwen3-VL-8B-Instruct model scored the two legal JSON values `real` and `fake` at the final STOP field. The higher conditional log-likelihood was selected. The model did not receive ground-truth labels, and no detector, crop generator, or tool was rerun. One exact tie on an already legal raw `fake` verdict retained that original legal value. Raw output, constrained output, candidate scores, and pre-STOP history hashes were saved separately.

The original STOP context was reconstructed from the held-out trajectories and cached observations. The tokenizer preflight found no token-boundary drift for the verdict field. Original generated token IDs were not saved, so the raw text prefix was re-encoded with the same tokenizer; see the method limitation in `contract_constrained/README.md`.

Frozen input hashes:

- Original 60 trajectories: `276715a5ebd42bc9a7c3b27d5d18f6c5550145d1be9f3ba2bf873f7b0767cec9`
- Held-out manifest: `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`
- Cached tool results: `94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`
- Model revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`
- Prompt SHA-256: `739abe138a0a40b1c21a77308565165bb309a0f45d28f1cf2d0da5354e8da1ea`
- Schema SHA-256: `d0ea87912099ccc058045f266bc904517f8abc209eea54ac707c44e2fc55b9b5`

## B. Five original failures

All five originally invalid STOP outputs became parseable legal terminal outputs: 5/5. Four `inconclusive` values were selected as `real`; one null value was selected as `fake`. These are model likelihood choices, not GT- or tool-score-based repairs.

## C. Success controls

In the initial forced-choice-on-every-STOP pilot, the fixed 15 controls reached 20/20 parse success together with the five failures, and the original tool sequence was preserved for all 20. That method preserved 10/15 legal control verdicts (66.7%): four `fake → real` and one `real → fake`. The user then selected a minimal policy: keep already legal original verdicts and apply the saved same-model choice only to invalid STOP outputs.

## D. Full 60 evaluation

| Measure | Forced choice on all STOPs | User-approved minimal policy |
|---|---:|---:|
| Legal terminal parse | 60/60 (100%) | 60/60 (100%) |
| Original invalid STOPs repaired | 5/5 | 5/5 |
| Original legal verdicts preserved | 37/55 (67.3%) | 55/55 (100%) |
| Original legal verdicts changed | 18/55 | 0/55 |
| Tool sequences preserved | 60/60 (100%) | 60/60 (100%) |
| Pre-STOP history preserved | 60/60 | 60/60 |
| Non-verdict STOP fields preserved | 60/60 | 60/60 |

Under the selected minimal policy, the five invalid outputs use the already computed same-model forced choices; the 55 legal outputs retain their exact original STOP JSON. No detector, crop pipeline, tool, or additional GPU inference was run for this derivation.

The all-STOP scoring diagnostic is `contract_constrained/outputs/full_retry2/replay.jsonl`, SHA-256 `ff410c84cb94c9a093b48e8edde06b6f0ab9d88428f184cba041654bd3261488`. The selected derived replay is `contract_constrained/outputs/minimal_policy/replay.jsonl`, SHA-256 `89fbe915fdf32505b20da820a50236c2a2238fc3fa72ab0e4bce06447464f130`; its metrics are in `contract_constrained/outputs/minimal_policy/evaluation/metrics.json`. Per-sample outputs remain ignored by Git.

The first full attempt stopped at record 14 because scores were rounded before comparison. A second attempt exposed an exact tie at that same originally legal sample. Both partial outputs were preserved remotely; a third run used full-precision comparison and the documented tie rule and completed 60/60. The completed output records decoder SHA-256 `a4a50858e3acac2b43181cdd71c699bec3df46c208f714bbbc2711480c650cdf`.

## E. Decision

The all-STOP forced-choice variant is rejected for changing 18 already legal verdicts. Under the user-approved minimal policy, the final metrics are 60/60 legal terminal outputs, 5/5 original failures repaired, 55/55 legal verdicts preserved, and 60/60 tool sequences and pre-STOP histories preserved. The evaluator marks the freeze gate passed. Final decision: **`ACTOR_B0_C_FREEZE`** under the minimal policy. No SFT was started.
