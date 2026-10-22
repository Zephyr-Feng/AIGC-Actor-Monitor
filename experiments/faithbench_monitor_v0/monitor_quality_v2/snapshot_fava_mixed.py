"""Small read-only status snapshot for the current approved job."""
import json
from pathlib import Path
import time

root = Path('/root/autodl-tmp/fava-mixed-v1-20261019')
result = {'observed_epoch': time.time()}
for name in ('authorization', 'failure'):
    path = root/(name+'.json')
    if path.exists():
        result[name] = json.loads(path.read_text())
for name in ('status', 'latest'):
    path = root/'run'/(name+'.json')
    if path.exists():
        result[name] = json.loads(path.read_text())
log = root/'worker.log'
if log.exists():
    with log.open('rb') as f:
        f.seek(max(0, log.stat().st_size-65536))
        lines = f.read().decode('utf8', errors='replace').splitlines()
    for line in reversed(lines):
        try:
            event = json.loads(line)
            result['last_event'] = {k: v for k, v in event.items() if k not in ('ids',)}
            break
        except ValueError:
            continue
    result['log_age_seconds'] = time.time()-log.stat().st_mtime
training = root/'run/training.jsonl'
if training.exists():
    text = training.read_text()
    records = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except ValueError:
            if index != len(lines)-1 or text.endswith('\n'):
                raise
    if records:
        result['training'] = {k: v for k, v in records[-1].items() if k != 'ids'}
        result['mean_last10_update_seconds'] = sum(r['seconds'] for r in records[-10:])/len(records[-10:])
assert result['authorization']['purpose'] == 'mixed_compact_noerror_chinese_replay'
print(json.dumps(result), flush=True)
