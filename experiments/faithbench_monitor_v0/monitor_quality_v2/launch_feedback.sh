#!/bin/bash
set -eu
root=/root/autodl-tmp/monitor-feedback-sft-20261017
test -f "$root/development_token_preflight.json"
test ! -e "$root/run"
test ! -e "$root/launch.json"
test -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)"
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
test "$used" -lt 1000
free=$(df --output=avail -B1 "$root" | tail -n 1)
test "$free" -gt 2000000000
mkdir "$root/launch.lock"
nohup bash "$root/feedback_wrapper.sh" > "$root/worker.log" 2>&1 < /dev/null &
pid=$!
/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python - "$root" "$pid" <<'PY'
import json,sys,time
from pathlib import Path
root=Path(sys.argv[1]);auth=json.loads((root/'authorization.json').read_text())
data={'wrapper_pid':int(sys.argv[2]),'launched_epoch':time.time(),'deadline_epoch':auth['deadline_epoch'],'root':str(root)}
with (root/'launch.json').open('x') as f:json.dump(data,f,indent=2)
print(json.dumps(data))
PY
