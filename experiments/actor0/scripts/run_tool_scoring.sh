#!/usr/bin/env bash
set -euo pipefail

RUN=/root/autodl-tmp/actor0-bfree-20261002
CODE="$RUN/code/actor0"
TOOLBOX=/root/autodl-tmp/toolbox_screening
PROBE_ROOT=/root/autodl-tmp/probe-dinov2-bfree-20261001
SAFE_ROOT=/root/autodl-tmp/SAFE_positive_control
PY=/root/miniconda3/bin/python
PATCHCRAFT_PY=/root/miniconda3/envs/safe_positive_control/bin/python
mkdir -p "$RUN/logs" "$RUN/scores"

source /root/miniconda3/etc/profile.d/conda.sh
conda activate base
"$PY" -c 'import torch; assert torch.cuda.is_available(), "GPU is not enabled"; print("torch",torch.__version__,"cuda",torch.version.cuda)'

"$PY" "$CODE/scripts/prepare_actor0_tool_inputs.py" \
  --dev-manifest "$CODE/data/actor0_dev_manifest.jsonl" \
  --eval-manifest "$CODE/data/actor0_eval_manifest.jsonl" \
  --image-root "$RUN/data" --output-root "$RUN"
ALL_MANIFEST="$RUN/manifests/actor0_all_manifest.jsonl"

PROBE_SRC=$(find "$PROBE_ROOT/src/probe" -maxdepth 1 -type d -name 'PROBE-AIGI-Detection-*' -print -quit)
PROBE_DETECTOR="$PROBE_SRC/Detector"
PROBE_CONFIG="$PROBE_ROOT/src/probe/dinov2_config.json"
PROBE_CHECKPOINT="$PROBE_ROOT/weights/DINOv2_best_model_step_34999.pth"
export PYTHONPATH="$PROBE_DETECTOR:$PROBE_ROOT/deps/probe:$PROBE_ROOT/deps/aide${PYTHONPATH:+:$PYTHONPATH}"
"$PY" "$PROBE_ROOT/src/probe/evaluate_dino_with_predictions.py" \
  --root_list "$RUN/tool_layout/probe/real" "$RUN/tool_layout/probe/fake_flux" "$RUN/tool_layout/probe/fake_sd35" \
  --fake_equal_real --batch_size 1 --crop_size 336 --dino_config "$PROBE_CONFIG" \
  --ckpt "$PROBE_CHECKPOINT" --predictions_csv "$RUN/scores/probe_predictions.csv" \
  2>&1 | tee "$RUN/logs/score_probe.log"

"$PATCHCRAFT_PY" "$CODE/scripts/score_patchcraft_actor0.py" \
  --manifest "$ALL_MANIFEST" --image-root "$RUN/data" \
  --official-source "$TOOLBOX/vendor/modelscope/PatchCraft" \
  --checkpoint "$TOOLBOX/vendor/modelscope/PatchCraft/weights/RPTC.pth" \
  --run-root "$RUN/scores/patchcraft" --name full --expected-count 480 \
  2>&1 | tee "$RUN/logs/score_patchcraft.log"

conda run -n safe_positive_control python "$CODE/scripts/score_safe_actor0.py" \
  --dataset "$RUN/data" --manifest "$ALL_MANIFEST" \
  --source "$SAFE_ROOT" --checkpoint "$SAFE_ROOT/checkpoint/checkpoint-best.pth" \
  --output "$RUN/scores/safe_raw.jsonl" --expected-count 480 \
  2>&1 | tee "$RUN/logs/score_safe.log"

PROVENANCE_CSV="$RUN/scores/provenance/provenance_results.csv"
PROVENANCE_CONFIG="$RUN/scores/provenance/raw/config.json"
if [[ -f "$PROVENANCE_CSV" ]]; then
  "$PY" -c 'import csv,json,sys; c=json.load(open(sys.argv[1])); n=sum(1 for _ in csv.DictReader(open(sys.argv[2],newline="",encoding="utf-8"))); assert c.get("c2pa_scan_status")=="completed" and c.get("images_scanned")==480 and n==480, (c,n); print("Reusing complete Provenance scan:",n)' "$PROVENANCE_CONFIG" "$PROVENANCE_CSV"
else
  C2PA_BIN="$TOOLBOX/bin/c2patool-v0.28.1/c2patool/c2patool"
  GLIBC_ROOT="$TOOLBOX/bin/runtime-glibc239/root"
  LOADER="$GLIBC_ROOT/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"
  LIBS="$GLIBC_ROOT/usr/lib/x86_64-linux-gnu"
  WRAPPER="$RUN/bin/c2patool_glibc239.sh"
  mkdir -p "$RUN/bin"
  cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
exec "$LOADER" --library-path "$LIBS:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu" "$C2PA_BIN" "\$@"
EOF
  chmod 755 "$WRAPPER"
  "$WRAPPER" --version
  "$PY" "$CODE/scripts/score_provenance_actor0.py" \
    --manifest "$ALL_MANIFEST" --image-root "$RUN/data" \
    --c2patool "$WRAPPER" --exiftool "$TOOLBOX/bin/exiftool-13.59/exiftool" \
    --run-root "$RUN/scores/provenance" --expected-count 480 \
    --positive-control-status sample_C_parsed_one_manifest_signature_untrusted \
    2>&1 | tee "$RUN/logs/score_provenance.log"
fi

"$PY" "$CODE/scripts/export_tool_observations.py" \
  --manifest "$ALL_MANIFEST" --image-root "$RUN/data" \
  --probe-csv "$RUN/scores/probe_predictions.csv" \
  --patchcraft-csv "$RUN/scores/patchcraft/predictions.csv" \
  --safe-jsonl "$RUN/scores/safe_raw.jsonl" \
  --safe-threshold "$CODE/config/safe_threshold_frozen.json" \
  --provenance-csv "$RUN/scores/provenance/provenance_results.csv" \
  --output "$RUN/scores/all_tool_observations.jsonl"
"$PY" "$CODE/scripts/split_actor0_tool_outputs.py" \
  --dev-manifest "$CODE/data/actor0_dev_manifest.jsonl" \
  --eval-manifest "$CODE/data/actor0_eval_manifest.jsonl" \
  --all-tools "$RUN/scores/all_tool_observations.jsonl" \
  --output-dir "$RUN/scores"
echo "Actor-0 tool scoring complete: 480 aligned images" | tee "$RUN/logs/tool_scoring_complete.txt"
