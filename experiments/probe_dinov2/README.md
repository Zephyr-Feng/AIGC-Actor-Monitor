# PROBE-DINOv2 on B-Free

**Status:** scoring and four-expert comparison complete.  
**Date:** 2026-10-01

## Objective and boundary

Evaluate the published PROBE-DINOv2 checkpoint on a new, frozen sample from B-Free extended Synthbuster, and compare it with FSD, AIDE, and SAFE rescored on the same images. No training or fine-tuning was performed. Test-set scores were not used to tune the primary threshold or preprocessing.

The result is a descriptive evaluation on 100 source groups, not sufficient by itself to freeze the project's expert stack, change `E_base`/`E_extra`, or start Stage 2. See [REPORT.md](REPORT.md) for results and limitations.

## Frozen dataset

- Source: B-Free extended Synthbuster `real_RAISE_1k.zip` and `sd3_flux.zip`.
- Selection unit: RAISE source group, keeping its real image and corresponding FLUX and SD3.5 images together.
- Previously used source groups excluded: Stage 1 (200) and SAFE independent calibration/screening (200); the manifests have no overlap.
- Selection: seed `20261001`; sample 70 landscape and 30 portrait groups without replacement from the 600 unused groups. The other 500 groups remain reserved.
- Images: 100 RAISE real, 100 FLUX fake, 100 SD3.5 fake; 300 PNGs total. Original archive bytes were extracted without resizing, re-encoding, or other image changes.
- Frozen manifest: [dataset_manifest.jsonl](dataset_manifest.jsonl), SHA-256 `61d9455417f5d388edd663ff8497c641db58e3ee3349fda94e64c01b77b2d465`.
- Image files for execution: ignored local run directory `runs/probe-dinov2-bfree-20261001/`; remote copy at `/root/autodl-tmp/probe-dinov2-bfree-20261001/`.
- Archive SHA-256: RAISE `bd25842eb4069937d6676a31538bb557dc78db9867fa6e463df5af11d86fa73e`; generated images `92a1d7f4f33e9a34c4556c3677e190a6db63ff6821fff98425271926013116b6`.
- Dataset use is limited to informational/nonprofit research under B-Free terms; retain notices and cite B-Free and RAISE.

## Model and source

- Model: PROBE-DINOv2, DINOv2-with-registers-large backbone.
- Official source: [PROBE-AIGI-Detection](https://github.com/Amamiya-C/PROBE-AIGI-Detection), commit `b145f7130004c02725e9b3703954a3329ebf56de`; source ZIP SHA-256 `5f748901f69fcc7153977f743e27c981899865bbf38fd29a7aeef8f360169093`.
- Official checkpoint: ModelScope revision `423e5877bc5ac51248508de56f3ac22f7dd1128f`, `DINOv2_best_model_step_34999.pth`, 1,217,679,947 bytes, SHA-256 `c8caa9bad54c029e4d22e1909c4673e46a239d8419a986e0ab461d423a450156`.
- All detector tensors were loaded with `strict=True` (442 keys).
- The official model class refers to an author-local absolute backbone path. The same architecture was instantiated from the official `facebook/dinov2-with-registers-large` config and the published detector checkpoint was strictly loaded. No detector weights were initialized from the config.
- Config: Hugging Face model revision `e4c89a4e05589de9b3e188688a303d0f3c04d0f3`, local [dinov2_config.json](dinov2_config.json), SHA-256 `902dad80eeb93434dc19bb0099d3dd45a8a40f9333ef0084ea2b55d3e39fea77`.

## Evaluation protocol

The official evaluator's native preprocessing was retained: 336-pixel fixed non-overlapping sliding patches, ImageNet normalization, patch-logit averaging per image, then sigmoid. No resize, center crop, augmentation, JPEG conversion, or test-time augmentation was added. The official fake score is `sigmoid(mean_patch_logit)`; fake is class 1 and the default decision is score `> 0.5`.

The official script only writes aggregate accuracy/AP, so [evaluate_dino_with_predictions.py](evaluate_dino_with_predictions.py) adds per-image export (`path`, `sample_id`, label, generator, raw mean logit, probability, prediction, correctness). It also accepts a local config file to resolve the original author-local backbone path. The forward path, checkpoint contents, patch creation, normalization, and score aggregation are unchanged. The all-generator run passed all 300 images. `--fake_equal_real` disables the official script's default random class downsampling because this frozen set intentionally contains 100 real and 200 fake images.

### Fixed operating points

| Expert | Primary decision | Source |
|---|---|---|
| PROBE-DINOv2 | score `> 0.5` | Official evaluator |
| FSD | frozen prior logistic calibration, `p_fake >= 0.5` | [FSD/AIDE calibration report](prior_calibrations/fsd_aide_calibration_report.json), fit on disjoint Stage 1 calibration groups |
| AIDE | frozen prior logistic calibration, `p_fake >= 0.5` | Same report; official input order is four DCT views then original image |
| SAFE | score `>= 0.9561132788658143` | [SAFE threshold](prior_calibrations/safe_threshold.json), frozen on disjoint SAFE calibration images |

Default uncalibrated decisions for the older experts are also reported separately. No threshold was refit on these 100 groups. PROBE's test-set oracle threshold is a diagnostic only and is not a valid test result. For majority vote, a 2:2 tie resolves to PROBE, fixed before scoring. The source group is the independent sampling unit; image-level metrics are descriptive.

## Results and artifacts

The full summary, per-generator metrics, aligned predictions, and error overlap are in [results/analysis](results/analysis/). Raw per-image expert scores and official output are in [results](results/).

- [Chinese report](REPORT.md)
- [Environment record](environment.txt)
- [Checkpoint and source hashes](checkpoint_info.txt)
- [Frozen manifest](dataset_manifest.jsonl)
- [PROBE predictions](results/probe_predictions.csv)
- [Aligned four-expert predictions](results/analysis/aligned_predictions.csv)
- [Overall metrics and diagnostics](results/analysis/metrics.json)
- [Per-generator metrics](results/analysis/metrics_by_generator.csv)
- [Error overlap](results/analysis/error_overlap.csv)

Large image data and downloaded checkpoints remain in ignored `runs/` and the isolated AutoDL data directory. The 4090 scoring processes have exited; the GPU was idle at final inspection.

## References

- Cao et al., “Where Detectors Fail: Probing Generative Space for Generalizable AI-Generated Image Detection,” ICML 2026. [PMLR paper](https://proceedings.mlr.press/v306/cao26s.html), [arXiv full text](https://arxiv.org/html/2605.24906).
- [B-Free extended Synthbuster](https://github.com/grip-unina/B-Free).
- [RAISE dataset](https://loki.disi.unitn.it/RAISE/).
