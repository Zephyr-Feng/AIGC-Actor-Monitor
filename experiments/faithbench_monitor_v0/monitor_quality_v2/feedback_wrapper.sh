#!/bin/bash
set -u
root=/root/autodl-tmp/monitor-feedback-sft-20261017
python=/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python
remaining=$($python - "$root" <<'PY'
import json,sys,time
from pathlib import Path
a=json.loads((Path(sys.argv[1])/'authorization.json').read_text())
assert a['approved'] and a['generation_limit']==160 and a['rows']==7612
print(int(a['deadline_epoch']-time.time())-15)
PY
)
code=124
if [ "$remaining" -gt 0 ]; then
  timeout --signal=TERM --kill-after=5s "${remaining}s" env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/root/autodl-tmp/monitor-public-sft-20261016/vendor:/root/monitor-retraining-qwen35-20261016/vendor "$python" -u "$root/train_feedback.py" --root "$root" --base /root/monitor-retraining-qwen35-20261016/assets/model
  code=$?
fi
"$python" - "$root" "$code" <<'PY'
import json,sys,time
from pathlib import Path
with (Path(sys.argv[1])/'wrapper_exit.json').open('x') as f:
 json.dump({'exit_code':int(sys.argv[2]),'finished_epoch':time.time()},f)
PY
exit "$code"
