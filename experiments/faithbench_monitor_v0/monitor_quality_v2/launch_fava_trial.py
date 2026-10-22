"""Start one bounded worker after checking GPU and output state."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

root = Path(sys.argv[1]).resolve()
assert not (root/'run').exists() and not (root/'launch.json').exists()
preflight = json.loads((root/'token_preflight.json').read_text())
assert preflight['groups_disjoint'] and preflight['train_rows'] == 6184 and preflight['evaluation_rows'] == 16
assert not subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip(), 'GPU occupied'
used = int(subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True).strip())
assert used < 1000 and shutil.disk_usage(root).free > 3_000_000_000
start = time.time()
auth = {'approved': True, 'authorization': 'user authorized FAVA training and preliminary paired evaluation',
        'epochs': 1, 'max_updates': 500, 'max_gpu_seconds': 7200, 'start_epoch': start,
        'training_cutoff_epoch': start+4800, 'deadline_epoch': start+7200,
        'actor_calls': 0, 'teacher_api_calls': 0, 'automatic_resume': False}
with (root/'authorization.json').open('x') as f:
    json.dump(auth, f, indent=2)
with (root/'worker.log').open('xb') as log:
    process = subprocess.Popen(['bash', str(root/'fava_wrapper.sh'), str(root)], stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
record = {'wrapper_pid': process.pid, **auth, 'root': str(root)}
with (root/'launch.json').open('x') as f:
    json.dump(record, f, indent=2)
print(json.dumps(record))
