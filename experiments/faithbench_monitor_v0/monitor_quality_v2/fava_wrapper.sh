#!/bin/bash
set -u
root=$1
python=/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python
timeout --signal=TERM --kill-after=5s 7190s env PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=/root/autodl-tmp/monitor-public-sft-20261016/vendor:/root/monitor-retraining-qwen35-20261016/vendor "$python" -u "$root/fava_trial.py" --mode train --root "$root" --base /root/monitor-retraining-qwen35-20261016/assets/model --initial /root/autodl-tmp/monitor-feedback-sft-20261017/run/checkpoint-00952/adapter
code=$?
"$python" - "$root" "$code" <<'PY'
import json,sys,time
from pathlib import Path
with (Path(sys.argv[1])/'wrapper_exit.json').open('x') as f:
    json.dump({'exit_code': int(sys.argv[2]), 'finished_epoch': time.time()}, f)
PY
exit "$code"
