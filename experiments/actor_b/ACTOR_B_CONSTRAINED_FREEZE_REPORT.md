# Actor-B Contract-Constrained Freeze Gate Report

**Date:** 2026-10-07
**Decision scope:** The tested forced-choice-on-every-STOP implementation only.
**Current disposition:** Freeze withheld; the evidence does not yet establish that SFT is required.

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

The fixed 15 controls reached 20/20 parse success together with the five failures, and the original tool sequence was preserved for all 20. The original legal verdict was preserved for 10/15 controls (66.7%): four `fake → real` and one `real → fake`. This is substantially below the plan's ideal of approximately 100%.

## D. Full 60 replay

| Measure | Result |
|---|---:|
| Legal terminal parse | 60/60 (100%) |
| Original invalid STOPs repaired | 5/5 |
| Original legal verdicts preserved | 37/55 (67.3%) |
| Original legal verdicts changed | 18/55 |
| Changed verdict direction | 17 `fake → real`; 1 `real → fake` |
| Tool sequences preserved | 60/60 (100%) |
| Pre-STOP history preserved | 60/60 |
| Non-verdict STOP fields preserved | 60/60 |
| Exact score tie | 1; original legal verdict retained |

The complete replay is `contract_constrained/outputs/full_retry2/replay.jsonl`, SHA-256 `ff410c84cb94c9a093b48e8edde06b6f0ab9d88428f184cba041654bd3261488`; runtime metadata is next to it. The pilot replay is under `contract_constrained/outputs/pilot/`. Per-sample outputs remain ignored by Git.

The first full attempt stopped at record 14 because scores were rounded before comparison. A second attempt exposed an exact tie at that same originally legal sample. Both partial outputs were preserved remotely; a third run used full-precision comparison and the documented tie rule and completed 60/60. The completed output records decoder SHA-256 `a4a50858e3acac2b43181cdd71c699bec3df46c208f714bbbc2711480c650cdf`.

## E. Decision

The tested method meets the structural contract and leaves tool orchestration and all pre-STOP history unchanged. It changes 18 of 55 already legal verdicts, so this implementation is **not approved for `ACTOR_B0_C_FREEZE`**. The full report evaluator therefore marks its preservation gate false.

These results do not by themselves establish `ACTOR_B1_SFT_REQUIRED`: the run produced a legal terminal state for all 60 samples, and it did not show an orchestration failure. The supplied plan's freeze gate does not specify a numerical verdict-preservation threshold, while its control check identifies approximately 100% as ideal and its binary decision section requires either freeze or SFT. A policy decision is needed before assigning either final label.

Recommended next check: retain an original `real`/`fake` verdict when it is already legal, and use the same-model forced choice only for the five invalid STOP outputs. This minimal projection would test the plan's intended behavior-preservation property without another GPU run, but it is a policy variant and has not been applied. No SFT or Actor freeze was started.
