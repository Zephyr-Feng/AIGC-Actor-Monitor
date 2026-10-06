# Mini FaithBench v0

Status: **third fixed 18-trajectory technical sample completed; evidence attribution and raw STOP contract still failed; formal 900-trajectory run not started** (2026-10-06). See [latest report](technical_sample_v3/REPORT.md), [second sample](technical_sample_v2/REPORT.md), and [first sample](technical_sample/REPORT.md).

This is a development diagnostic on the frozen Actor-0 evaluation manifest (100 source groups, 300 images), not a final paper holdout. It compares FULL, SUMMARY-MASK, and OUTPUT-RENAME using the pinned Qwen3-VL-8B-Instruct revision. Actor policy was preserved; only the PROBE tool schema was minimally adapted from classifier output to evidence-only output, including the two evidence-summary format instructions authorized after the first sample. No Actor training or decision-policy tuning is in scope.

## Frozen sources

- Actor-0 manifest: `experiments/actor0/data/actor0_eval_manifest.jsonl`, SHA-256 `fffd5736418a4cfd36b85f95b571a4347608851d607db9a5b86010f6ce1a857c`.
- Other tool observations: `runs/actor0-bfree-20261002/scores/eval_tool_observations.jsonl`.
- PROBE evidence cards and crops: `experiments/probe_evidence_v1/results/output/evidence/`.
- Original Actor-0 prompt-material hash: `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`.
- First Tool-Card-only candidate hash: `78ea83dfcf59a75fb7b9909ffe4492551a3c44635f50566329c5c759fd8f4359`; it failed because Actor fabricated global `signal/score` summaries.
- Interface-fix `actor0-evidence-v1` candidate hash: `cc128afa3e4f6ec0f0cc68509386c2668f6375f551fdc45803369746b6c8882f`. It has **not** been frozen because the rerun failed semantic and final-output parsing gates.
- Attribution/STOP-contract candidate hash: `5cc7a1cd8ffda55b7d2b94b7546619944073c933ed1a064c0a2d07c0c94604f2`. It also remains **unfrozen** after the final 18-trajectory sample exposed PROBE directional attribution and one raw `final_verdict=uncertain` STOP.

## Prepared inputs

`prepare_inputs.py` replaces only the global tool's returned payload. FULL uses the complete v1 JSON card with its original display identity `global_representation_analyzer`. SUMMARY-MASK removes exactly `num_atypical_regions`, `atypical_fraction`, `max_deviation_percentile`, and `median_deviation_percentile`. OUTPUT-RENAME changes the returned payload identity to `representation_inspector` and renames `observations`, `most_atypical_regions`, and `deviation_percentile` fields. The callable dispatcher name remains `global_forensic_analyzer` in all three conditions. The other three tool observations are equivalent after JSON parsing across conditions.

The 300 paired cards passed static checks for sample/image alignment, the four masked fields, renamed values, bbox, crop paths, and unchanged other-tool observations. The runner supplies the top-3 crop pixels in region order after a global tool call, with the same four-image context in every condition. Three fixed 18-trajectory technical samples have been produced; no formal trajectories or metrics exist.

The first sample found 7 fabricated global `signal/score` summaries per condition. The second found no direct global `signal/score` fabrication, but found PROBE-attributed implicit real/fake interpretations and only 17/18 parseable final outputs. The third restored 18/18 parseable final files yet still produced PROBE directional attribution and one rejected raw STOP with `final_verdict=uncertain`. Under the prespecified gate, the prompt remains unfrozen and the formal run is stopped. No surrogate values were inserted by the runner, and no Evidence parameter or Actor decision rule was changed.

## Rebuild

```text
python experiments/mini_faithbench_v0/prepare_inputs.py \
  --manifest experiments/actor0/data/actor0_eval_manifest.jsonl \
  --old-tools runs/actor0-bfree-20261002/scores/eval_tool_observations.jsonl \
  --evidence-dir experiments/probe_evidence_v1/results/output/evidence \
  --output-dir experiments/mini_faithbench_v0/inputs
```

The script refuses to overwrite existing inputs. Remove only a specifically verified generated file when an intentional rebuild is needed.
