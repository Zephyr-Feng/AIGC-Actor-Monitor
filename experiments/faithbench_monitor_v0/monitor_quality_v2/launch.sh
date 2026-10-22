#!/bin/bash
set -eu
root=/root/autodl-tmp/monitor-quality-v2-20261017
test -f "$root/preflight.json"
test ! -e "$root/run"
test ! -e "$root/launch.txt"
test -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)"
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
test "$used" -lt 1000
mkdir "$root/launch.lock"
nohup timeout --signal=TERM --kill-after=20s 1800s env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/root/autodl-tmp/monitor-public-sft-20261016/vendor:/root/monitor-retraining-qwen35-20261016/vendor /root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python -u "$root/feedback_probe.py" --root "$root" > "$root/worker.log" 2>&1 < /dev/null &
pid=$!
printf 'wrapper_pid=%s\nstarted=%s\nhard_seconds=1800\n' "$pid" "$(date -Is)" > "$root/launch.txt"
cat "$root/launch.txt"
