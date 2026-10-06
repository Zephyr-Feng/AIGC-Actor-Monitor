# Qualitative trajectory audit

The fixed 50-case sample was reviewed using its source-image contact sheets, the full Actor step bundle, and the aligned tool observations. Ground-truth labels were omitted from the review bundle and were not used to score these process judgments. The sample is stratified and intentionally oversamples mistakes, conflicts, single-tool stops, all-tool calls, and selected easy cases; its counts are descriptive of the audit set, not prevalence estimates.

## Rubric

- `tool_selection_reasonable`: pass when the selected tool addresses a remaining information need or stopping is supported by independent, coherent evidence; fail when a relevant unused tool could address an acknowledged conflict/gap, or the Actor stops with only one uncalibrated learned score and claims high confidence. The plan allows variable tool counts; the single-score concern is about confidence and sufficiency, not a mandatory call quota.
- `evidence_summary_faithful`: pass when the semantic tool, actual signal, and score are represented without reversing or inventing an observation.
- `evidence_gap_valid`: pass when the stated gap matches the observations and the remaining useful evidence; fail when a useful unused tool or lack of independent evidence is dismissed as “no gap.”
- `conflict_recognized`: pass when observed disagreement is identified before final STOP and retained in the final account; no conflict is required when only one signal was observed.
- `stop_reason_consistent`: pass when the stop rationale matches available observations and preserves unresolved uncertainty; fail when it claims a consensus or no remaining evidence despite a material known gap.

## Summary

All 50 evidence summaries faithfully represented their tool observations, and all observed conflicts were acknowledged before STOP. Twenty cases were flagged for process concerns: 16 single-global-tool high-confidence stops and 4 premature stops while a useful tool remained available to address a conflict. The remaining 30 cases passed all five review fields. These findings are post-hoc diagnostics only; no prompt, score, threshold, preprocessing, or model selection was changed after evaluation.
