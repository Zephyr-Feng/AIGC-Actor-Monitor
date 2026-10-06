# Qwen3-VL weight transfer and snapshot check

- Model: `Qwen/Qwen3-VL-8B-Instruct`
- Frozen revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`
- Hub index tensor bytes: `17,534,247,392`; downloaded safetensors bytes (including shard headers): `17,534,339,512`.
- First transfer backend: Hugging Face Xet high-performance. The Xet CAS host intermittently failed DNS resolution / timed out. The downloader was interrupted after about 65 minutes; incomplete shards and its log were preserved under the remote Actor-0 run root. Local copy of that log: `runs/actor0-bfree-20261002/logs/download_qwen_xet.log`.
- Fallback: `HF_HUB_DISABLE_XET=1`, Hugging Face Hub HTTP backend, same pinned revision and shared Hub cache. Snapshot download exited with code 0 after 20:42. Runtime manifest: `model_download.json`.
- Verification: exactly four complete safetensors, sizes match the runtime manifest, no incomplete files in the snapshot, config `model_type=qwen3_vl`, index total agrees with tensor bytes, and local-only `AutoProcessor` loading passed (`Qwen3VLProcessor`, Transformers 4.57.4, Python 3.12.3). Details and config/index SHA-256 are in `model_verify.json`.
- All four safetensors were read back with sha256sum; digests are in model_weights_sha256.txt and were compared with the blob IDs in the pinned Hub cache.
- No GPU was used during transfer or processor verification. This verifies the snapshot and processor only; model inference still requires the user-opened RTX 4090.
