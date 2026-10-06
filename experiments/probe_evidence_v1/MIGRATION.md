# PROBE Evidence-Only v1: instance handoff

Date: 2026-10-05. No GPU inference was run during this handoff.

## Instances

- Source: `connect.bjb2.seetacloud.com:15279` (`autodl-container-sbhn4u78c0-c07a45ba`).
- Destination: `connect.bjb1.seetacloud.com:31805` (`autodl-container-40dd41ad1f-569df20a`).
- Destination data disk: fresh 50 GiB XFS mounted at `/root/autodl-tmp`.

## Migrated inputs

| Input | Destination | Verification |
| --- | --- | --- |
| Actor-0 frozen dev/eval images | `/root/autodl-tmp/actor0-bfree-20261002/data/` | 480/480 SHA-256 values match frozen manifest; 180 dev and 300 eval |
| Actor-0 frozen manifest | `/root/autodl-tmp/actor0-bfree-20261002/manifests/actor0_all_manifest.jsonl` | SHA-256 `b2c254d8f8c5111f77fe82785abbca857d059d1933cea588f0666b5ec274eb28` |
| Actor-0 prior PROBE predictions | `/root/autodl-tmp/actor0-bfree-20261002/probe_predictions.csv` | SHA-256 `c6443013822ea6d5ed627129a079aaf854b59fb1248328a5381f0503d2ef143e` |
| PROBE-DINOv2 checkpoint | `/root/autodl-tmp/probe-dinov2-bfree-20261001/weights/DINOv2_best_model_step_34999.pth` | SHA-256 `c8caa9bad54c029e4d22e1909c4673e46a239d8419a986e0ab461d423a450156` |
| Official PROBE checkout and existing adapter | `/root/autodl-tmp/probe-dinov2-bfree-20261001/src/probe/` | Copied without editing; exact source commit identifier is recorded in directory name |
| PROBE Python dependencies | `/root/autodl-tmp/probe-dinov2-bfree-20261001/deps/probe/` | 10,083 files; transfer archive SHA-256 `3a3f2c45c4b442b8c1c75495922cdd12a4ae8323132a801cce8758c665ff98c3`; imports succeed (Transformers 4.50.3, NumPy 2.5.3, SciPy 1.17.0, scikit-learn 1.7.2) |
| Earlier frozen authentic calibration images | `/root/autodl-tmp/probe-evidence-v1/reference_source/images/calibration/raise/` | 100/100 SHA-256 values match earlier manifest |
| Earlier calibration manifest | `/root/autodl-tmp/probe-evidence-v1/reference_source/manifest.jsonl` | SHA-256 `ceb396cbf9a78d2aa04a4e77307e6062e4486de900b6c8bd12be13f7732fcc58` |

The earlier calibration set comes from `runs/stage1-safe-independent-20260929/`. Its 100 source groups overlap neither Actor-0 dev (60 groups) nor Actor-0 eval (100 groups). The Evidence-Only v1 plan prioritizes this frozen set over the 60 Actor-0 dev authentic images. The original manifest, dataset summary, and RAISE license notices were copied with it.

The base Python image is the same on both instances (`torch 2.12.1+cu130`, `torchvision 0.27.1+cu130`). The PROBE-specific dependency directory was transferred because Transformers and other required packages are absent from the base image. Large SAFE, Qwen, AIDE, and RIGID assets were not transferred. Temporary migration archives and the interrupted partial dependency copy were removed after verification; the source originals remain intact.

## Next step

Prepare the evidence-compatible PROBE extraction path without changing official preprocessing or classifier behavior. Before GPU inference, notify the user of the specific task and estimated card time. Stage A must stop if parity fails against the frozen Actor-0 eval predictions.
