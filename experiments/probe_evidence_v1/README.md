# PROBE Evidence-Only v1

This experiment adds a non-conclusive patch representation branch to frozen PROBE-DINOv2. It preserves the official classifier for audit and parity while keeping classifier verdicts and scores in the internal `audit/` directory. Actor-facing cards contain only representation distances, patch locations, crops, and limitations.

## Frozen design

- Evaluation: the existing Actor-0 eval, 300 images (100 RAISE, 100 FLUX, 100 SD3.5).
- Authentic reference: the earlier frozen 100-image RAISE calibration split from `stage1-safe-independent-20260929`. Its source groups were verified disjoint from Actor-0 dev and eval, as the plan requires.
- Backbone and checkpoint: official PROBE checkout `b145f7130004c02725e9b3703954a3329ebf56de`; DINOv2 checkpoint SHA-256 is recorded in `config/evidence_config.json`.
- Official classifier preprocessing remains RGB, fixed `data_augment`, 336-pixel non-overlapping sliding patches, ImageNet normalization, average patch logit, then sigmoid.
- Evidence settings are fixed: L2-normalized patch CLS features, cosine distance, `k=20`, source-group-excluded real calibration distribution, 95th percentile threshold, four-neighbor components, top three crops.

## Execution gates

1. Run `extract_features.py --split eval` and `check_parity.py`. Stop if the order, all 300 predictions, or the `<1e-5` probability parity criterion fails.
2. Only after parity passes, run `extract_features.py --split reference`.
3. Run `build_evidence.py`, then `analyze_evidence.py`.
4. Review the 30 seeded contact sheets for pipeline bugs only. Do not adjust parameters from their labels or appearance.
5. Preserve raw per-image audit outputs, patch features, reference bank, crops, cards, statistics, and reports.

The current remote runtime paths and verified transfer hashes are in [MIGRATION.md](MIGRATION.md). The saved plan is the user-provided PROBE Evidence-Only v1 protocol. No Actor, Monitor, or Evidence v2 work is part of this experiment.
