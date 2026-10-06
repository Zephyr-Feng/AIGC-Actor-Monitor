# SAFE Patch Coverage Diagnostic Report

## 1. Dataset

- Frozen screening manifest SHA-256: `ceb396cbf9a78d2aa04a4e77307e6062e4486de900b6c8bd12be13f7732fcc58`
- RAISE real: 100 images
- FLUX fake: 100 images
- SD3.5 fake: 100 images
- Original images: 300; crops: 1,500 (five positions per image)
- Every original file SHA-256 matched the frozen manifest. Every crop was 512×512 and pixel-identical to the corresponding source region.
- Ten crops were visually inspected using seed `20260930`; no borders, padding, stretching, or resizing were observed.

## 2. Baseline

Baseline is the previously saved SAFE screening run on the original image with official `CenterCrop(256)`. The calibration threshold was kept frozen at `0.9561132788658143`; fake iff score ≥ threshold.

| Metric | Original SAFE baseline |
|---|---:|
| AUC | 0.6550 |
| Accuracy | 44.67% |
| Precision | 74.29% |
| Recall | 26.00% |
| FLUX recall | 25.00% (25/100) |
| SD3.5 recall | 27.00% (27/100) |
| Real false positive rate | 18.00% (18/100) |

## 3. Position Results

All positions use the same frozen threshold and SAFE preprocessing after the 512×512 crop.

| Position | AUC | Accuracy | FLUX Recall | SD3.5 Recall | Real FP |
|---|---:|---:|---:|---:|---:|
| top_left | 0.7082 | 49.67% | 35.00% | 31.00% | 17.00% |
| top_right | 0.6920 | 51.67% | 41.00% | 28.00% | 14.00% |
| bottom_left | 0.6782 | 48.33% | 32.00% | 27.00% | 14.00% |
| bottom_right | 0.6587 | 48.00% | 40.00% | 22.00% | 18.00% |
| center | 0.6424 | 43.33% | 25.00% | 27.00% | 22.00% |

## 4. Aggregation Results

The same frozen threshold was applied to center, max, and mean scores; no threshold was recalibrated for an aggregation method.

| Method | AUC | Accuracy |
|---|---:|---:|
| Center only | 0.6424 | 43.33% |
| Max patch | 0.6661 | 67.33% |
| Mean patch | 0.7483 | 42.67% |

At the frozen threshold, max-patch aggregation has 77.50% fake recall (FLUX 80/100; SD3.5 75/100) and 53.00% real false positives (53/100). Mean-patch aggregation has 15.50% fake recall and 3.00% real false positives. Its higher AUC therefore does not translate to higher accuracy at the frozen operating point.

Max-patch AUC gain over center: `+0.0237`. The range across the five position AUCs is `0.0659` (center `0.6424` to top-left `0.7082`).

## 5. Protocol and Execution

- Crop positions: top-left, top-right, bottom-left, bottom-right, and center.
- Crop size: 512×512; no resize, interpolation, padding, or enlargement.
- Inference: official SAFE code at commit `4e998724651b227def64f5be0cd60c0aa1552c35`; checkpoint `checkpoint-best.pth`, SHA-256 `b3f5ecfb46a154ed553aaaf4bf3ba59182310726ddb0cbb1fe42bd0e22d2f20e`.
- Preprocessing and scoring remained RGB, `CenterCrop(256)`, `ToTensor()`, and `softmax(logits)[1]`; batch size 1; fake score direction unchanged.
- All 1,500 scores completed in 100.907 seconds. Peak PyTorch allocated memory was 152.42 MiB. No inference error or OOM occurred. The RTX 4090 returned to 0 MiB and 0% utilization after the process exited.
- `patch_output/scores.csv` contains 1,500 unique, finite scores in `[0,1]`; its SHA-256 matches the remote copy.

## 6. Interpretation

**Case B — SAFE sensitivity depends on spatial location.** The position AUC range is 0.0659, exceeding the descriptive 0.03 cutoff used to operationalize “different positions clearly differ.” Different image regions contain different amounts of forensic evidence in this screening set. Max-patch aggregation itself improves AUC by only 0.0237 over center, below the 0.10 Case A threshold.

These are descriptive results on the fixed 300-image screening set; no confidence interval or significance test was specified. The real false positive rate of max-patch aggregation rises to 53% at the frozen threshold, so the result does not establish a usable performance improvement or that missing local evidence is the primary cause of SAFE’s target-domain decline.

**Center-coordinate note:** The SOP defines the center 512 crop using integer floor division (`//`), then SAFE applies its official 256 center crop. Pixel comparison found that the resulting 256×256 model input differs by a one-pixel coordinate offset from the original direct SAFE center crop on 25/300 images. The prescribed floor-coordinate crop was retained. Baseline values above come from the previously saved original-image scores; “Center only” is the center-position result under this patch protocol.

## 7. Files

- `baseline_file_list.txt`: the exact 300 frozen screening images and their baseline scores
- `metadata.csv`: coordinates and source path for all 1,500 crops
- `crop_sha256.txt`: per-crop SHA-256 values
- `cropped_images/`: the 1,500 512×512 PNG crops
- `patch_output/run.log`, `patch_output/scores.csv`, `patch_output/metrics.txt`: inference log, raw scores, and calculated metrics
- `inspection_random10.png`: visual QC sample
- `score_safe_patches.py`, `summarize_patch_scores.py`: experiment scoring and summary scripts
