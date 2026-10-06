# SAFE Official Positive Control Report

## 1. Verdict

PASS

## 2. Repository

Commit:

```text
4e998724651b227def64f5be0cd60c0aa1552c35
```

Git status before run:

```text
?? CHECKPOINT_SHA256.txt
?? SAFE_COMMIT.txt
```

Git status after run and artifact creation:

```text
?? CHECKPOINT_SHA256.txt
?? SAFE_COMMIT.txt
?? SAFE_POSITIVE_CONTROL_REPORT.md
?? __pycache__/
?? data/__pycache__/
?? models/__pycache__/
?? positive_control_output/
```

## 3. Environment

Python:

```text
3.9.25
```

PyTorch:

```text
2.2.1+cu121
```

Torchvision:

```text
0.17.1+cu121
```

CUDA:

```text
12.1 runtime; cuda_available=True
```

GPU:

```text
NVIDIA GeForce RTX 4090, 24564 MiB
```

## 4. Checkpoint

Path:

```text
checkpoint/checkpoint-best.pth
```

SHA256:

```text
b3f5ecfb46a154ed553aaaf4bf3ba59182310726ddb0cbb1fe42bd0e22d2f20e
```

File size:

```text
5840638 bytes
```

## 5. Dataset

Source:

```text
lioooox/DiTFake
```

Revision:

```text
66105473704c6ebcc03cb971322bb95f04c7bdc4
```

Dataset path:

```text
/root/autodl-tmp/SAFE_official_data/DiTFake_repo/DiTFake/test
```

FLUX:
- real: 5000
- fake: 5000

PixArt:
- real: 5000
- fake: 5000

SD3:
- real: 5000
- fake: 5000

Total:

```text
30000 images; all 30004 manifest files independently matched their official LFS SHA256 or Git blob hash after instance cloning.
```

## 6. Exact Evaluation Command

```bash
set -o pipefail

CUDA_VISIBLE_DEVICES=0 /root/miniconda3/envs/safe_positive_control/bin/python -m torch.distributed.launch \
    --nproc_per_node 1 \
    --nnodes 1 \
    --node_rank 0 \
    --master_addr localhost \
    --master_port 12345 \
    main_finetune.py \
    --input_size 256 \
    --transform_mode crop \
    --model SAFE \
    --eval_data_path /root/autodl-tmp/SAFE_official_data/DiTFake_repo/DiTFake/test \
    --batch_size 256 \
    --num_workers 16 \
    --output_dir ./positive_control_output \
    --resume ./checkpoint/checkpoint-best.pth \
    --eval True \
    2>&1 | tee positive_control_output/run.log
```

## 7. Results

| Dataset | Paper ACC | Observed ACC | Paper AP | Observed AP |
|---|---:|---:|---:|---:|
| FLUX.1-schnell | 99.3 | 99.31 | 99.9 | 99.97 |
| PixArt-Sigma | 99.6 | 99.63 | 100.0 | 100.00 |
| SD3 | 99.4 | 99.40 | 99.9 | 99.99 |

## 8. Deviations From Official Protocol

- Evaluation used one GPU, as specified by this positive-control SOP, instead of the 4-GPU launcher configuration.
- SAFE source was transferred as a verified Git bundle at the same official commit because direct remote GitHub access failed.
- DiTFake files were fetched from the user-approved HF-Mirror transport at the pinned official Hugging Face revision. After two `snapshot_download` attempts failed during repository pagination, the saved complete API manifest was used to retrieve all files individually. Every file was checked against its official LFS SHA256 or Git blob hash; the clone was independently rechecked. Dataset content, revision, evaluation code, and evaluation parameters were unchanged.
- PyPI packages were transported through the Tsinghua PyPI mirror. `requests` was added to the isolated environment solely for the manifest downloader.
- The Python executable was specified by its absolute path; all evaluation arguments remained as shown above. No master-port, worker-count, or batch-size changes were needed.

## 9. Errors / Warnings

- The two initial `huggingface_hub.snapshot_download` attempts failed during mirror directory pagination with `RuntimeError: Cannot send a request, as the client has been closed`; the manifest-based download then completed with zero failed files.
- PyTorch emitted the expected `torch.distributed.launch` deprecation FutureWarning. The prescribed launcher was retained.
- `pytorch_wavelets` emitted a `pkg_resources` deprecation UserWarning.
- No inference errors, CUDA OOM, missing keys, or unexpected keys. The official restore path called `model_without_ddp.load_state_dict(checkpoint['model'])` with the default strict loading, then evaluated all three subsets.

## 10. Interpretation

The official SAFE checkpoint and evaluation pipeline reproduce the reported
DiTFake performance closely. This supports treating the poor performance
previously observed on the RAISE/FLUX/SD3.5 target domain as a target-domain
or processing-chain generalization issue rather than an obvious SAFE
installation/checkpoint failure.
