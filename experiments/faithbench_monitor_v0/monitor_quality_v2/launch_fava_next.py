"""Start the approved two-hour inference window, never resume or extend it."""
import json
import os
from pathlib import Path
import subprocess
import time

from fava_trial import write

root = Path('/root/autodl-tmp/fava-next-stage-20261019')
assert (root/'token_preflight.json').is_file()
assert not (root/'authorization.json').exists()
apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip()
assert not apps, 'GPU occupied: do not start or stop other jobs'
start = time.time()
authorization = {'approved': True, 'purpose': 'fava_next_development_comparison',
                 'human_authorization': '2026-10-19: 按照这个方案执行，卡开着',
                 'training_updates': 0, 'training_epochs': 0, 'max_gpu_seconds': 7200,
                 'max_generations': 384, 'planned_generations': 334,
                 'start_epoch': start, 'deadline_epoch': start+7200}
write(root/'authorization.json', authorization)
env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1',
           PYTHONPATH='/root/autodl-tmp/monitor-public-sft-20261016/vendor:/root/monitor-retraining-qwen35-20261016/vendor')
command = ['timeout', '--signal=TERM', '--kill-after=10s', '7190s',
           '/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python', '-u', str(root/'evaluate_fava_next.py'),
           '--root', str(root), '--base', '/root/monitor-retraining-qwen35-20261016/assets/model',
           '--old', '/root/autodl-tmp/monitor-feedback-sft-20261017/run/checkpoint-00952/adapter',
           '--current', '/root/autodl-tmp/monitor-fava-trial-20261018/continuation_v2/run/checkpoint-00373/adapter', '--run']
with (root/'worker.log').open('xb') as log:
    process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
launch = {**authorization, 'timeout_pid': process.pid, 'command': command}
write(root/'remote_launch.json', launch)
print(json.dumps({'timeout_pid': process.pid, 'start_epoch': start, 'deadline_epoch': start+7200}))
