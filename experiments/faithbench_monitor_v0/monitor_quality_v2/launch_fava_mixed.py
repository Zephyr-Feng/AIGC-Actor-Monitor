"""Single approved eight-hour window, including comparison and final evaluation."""
import json
import os
from pathlib import Path
import subprocess
import time

from fava_trial import write

root = Path('/root/autodl-tmp/fava-mixed-v1-20261019')
assert not (root/'authorization.json').exists()
preflight = json.loads((root/'token_preflight.json').read_text(encoding='utf8'))
assert preflight['rows'] == 7376 and preflight['planned_updates'] == 461 and not preflight['truncated']
assert preflight['tasks']['compact_noerror'] == 512 and preflight['tasks']['chinese_feedback_replay'] == 1024
assert not subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip()
start = time.time()
auth = {'approved': True, 'purpose': 'mixed_compact_noerror_chinese_replay',
        'human_authorization': '2026-10-19 user approved no-error supervision with Chinese feedback training and separately selected an eight-hour total cap',
        'epochs': 1, 'max_updates': 500, 'max_gpu_seconds': 28800, 'max_generations': 334,
        'start_epoch': start, 'deadline_epoch': start+28800, 'training_cutoff_epoch': start+25200,
        'data_rows': preflight['rows'], 'initialization': 'old00952', 'before_comparator': 'current00373',
        'loss': 'mean assistant-token CE per example then mean window; prevents short empty targets being token-downweighted',
        'scope': 'local Monitor only; no Actor, teacher API, new data downloads or hash checks'}
write(root/'authorization.json', auth)
env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1',
           PYTHONPATH='/root/autodl-tmp/monitor-public-sft-20261016/vendor:/root/monitor-retraining-qwen35-20261016/vendor')
command = ['timeout', '--signal=TERM', '--kill-after=10s', '28790s',
           '/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python', '-u', str(root/'fava_mixed_trial.py'),
           '--root', str(root), '--base', '/root/monitor-retraining-qwen35-20261016/assets/model',
           '--initial', '/root/autodl-tmp/monitor-feedback-sft-20261017/run/checkpoint-00952/adapter',
           '--comparison', '/root/autodl-tmp/monitor-fava-trial-20261018/continuation_v2/run/checkpoint-00373/adapter', '--run']
with (root/'worker.log').open('xb') as log:
    process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
write(root/'remote_launch.json', {**auth, 'timeout_pid': process.pid, 'command': command})
print(json.dumps({'timeout_pid': process.pid, 'start_epoch': start, 'training_cutoff_epoch': start+25200,
                  'deadline_epoch': start+28800}), flush=True)
