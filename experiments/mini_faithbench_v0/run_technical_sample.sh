#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/autodl-tmp/mini-faithbench-v0
CODE="$ROOT/experiments/mini_faithbench_v0"
PYTHON="$ROOT/actor-venv/bin/python"
MODEL_DIR="$($PYTHON -c 'import json; print(json.load(open("/root/autodl-tmp/mini-faithbench-v0/model_snapshot.json"))["snapshot_path"])')"
MANIFEST="$CODE/config/technical_sample_manifest.jsonl"
IMAGE_ROOT=/root/autodl-tmp/actor0-bfree-20261002/data
EVIDENCE=/root/autodl-tmp/probe-evidence-v1/output/evidence
OUTPUT="$ROOT/technical_sample/trajectories"

for condition in full summary_mask output_rename; do
  "$PYTHON" "$CODE/run_mini.py" \
    --manifest "$MANIFEST" \
    --tool-results "$CODE/inputs/$condition.jsonl" \
    --image-root "$IMAGE_ROOT" \
    --evidence-dir "$EVIDENCE" \
    --model-dir "$MODEL_DIR" \
    --config-dir "$CODE/config" \
    --output-root "$OUTPUT" \
    --condition "$condition" \
    --crop-mode pixels \
    --limit 6 \
    --preflight
done

"$PYTHON" "$CODE/check_technical_sample.py" \
  --sample-manifest "$MANIFEST" \
  --inputs-dir "$CODE/inputs" \
  --trajectories-dir "$OUTPUT" \
  --output "$ROOT/technical_sample/check.json"
