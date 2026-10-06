# Heterogeneous Forensic Toolbox Screening

**Status (2026-10-02): completed.** The PatchCraft, RIGID, and Provenance Inspector evaluations and the prespecified comparison with the frozen PROBE results are complete. See [REPORT.md](REPORT.md) for protocol, results, decisions, and limitations.

## Frozen evaluation data

- 300 original PNGs in 100 source groups: 100 RAISE real, 100 FLUX, and 100 SD3.5.
- Frozen manifest: [dataset_manifest.jsonl](dataset_manifest.jsonl), SHA-256 `61d9455417f5d388edd663ff8497c641db58e3ee3349fda94e64c01b77b2d465`.
- Existing PROBE scores reused from `experiments/probe_dinov2/results/probe_predictions.csv`.
- No threshold, model, preprocessing, or hyperparameter was selected using frozen test labels.
- RIGID threshold was fixed on the separate 30-source-group calibration set in [rigid/calibration](rigid/calibration); no source groups overlap the frozen test set.

## Results

- PatchCraft: 300/300 scores, 0 inference failures; 46.15 s, 3689 MiB peak allocated VRAM. Decision: **CONDITIONAL** as weak local texture evidence only.
- RIGID: 300/300 scores, 0 inference failures; 12.60 s, 4698 MiB peak allocated VRAM. Decision: **DROP** for this frozen domain.
- Provenance Inspector: 300/300 C2PA + metadata scans, 0 tool errors; no C2PA or origin-bearing metadata was found. Decision: **CONDITIONAL** when provenance evidence exists.
- PROBE: reused as **KEEP** baseline; its 6 errors were the basis for the prespecified complementarity analysis.

All mandatory per-image, analysis, and report files are listed in [REPORT.md](REPORT.md). Runtime logs, configuration snapshots, calibration scores, and per-image raw outputs are retained alongside each tool's result files.

## Sources and adapters

- PatchCraft source: [vendor/modelscope/PatchCraft](vendor/modelscope/PatchCraft)
- IBM/RIGID source: [vendor/RIGID](vendor/RIGID)
- DINOv2 source: [vendor/dinov2](vendor/dinov2)
- Scoring and analysis adapters: [scripts](scripts)
