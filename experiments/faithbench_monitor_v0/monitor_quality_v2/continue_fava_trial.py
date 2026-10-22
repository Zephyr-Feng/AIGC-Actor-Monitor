"""One approved continuation; budget remains anchored to the first launch."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def write(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2)


def coordinate(root):
    original = json.loads((root/'launch.json').read_text())
    amendment = json.loads((root/'budget_amendment.json').read_text())
    assert amendment['approved'] and amendment['max_gpu_seconds'] == 28800
    assert amendment['epochs'] == 1 and amendment['max_updates'] == 500
    assert amendment['start_epoch'] == original['start_epoch']
    deadline = original['start_epoch']+28800
    while not (root/'wrapper_exit.json').exists():
        assert time.time() < original['start_epoch']+7260, 'first worker exceeded its bound'
        time.sleep(5)
    assert json.loads((root/'wrapper_exit.json').read_text())['exit_code'] == 0, 'first stage failed; no blind restart'
    status = json.loads((root/'run/status.json').read_text())
    if status['epoch_complete']:
        write(root/'continuation_not_needed.json', status)
        return
    assert 0 < status['updates'] < 500 and status['samples'] < 6184 and status['after_complete']
    initial = Path(status['checkpoint']).resolve()
    assert initial.is_relative_to((root/'run').resolve()) and (initial/'training_state.pt').is_file()
    assert not subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip()
    assert shutil.disk_usage(root).free > 1_500_000_000
    stage = root/'continuation_v2'
    stage.mkdir(exist_ok=False)
    for name in ('train.tokens.jsonl', 'development_pool.tokens.jsonl', 'token_preflight.json', 'data_freeze.json'):
        os.link(root/name, stage/name)
    shutil.copy2(root/'continuation_fava_trial.py', stage/'fava_trial.py')
    shutil.copy2(root/'public_helpers.py', stage/'public_helpers.py')
    auth = {**amendment, 'deadline_epoch': deadline, 'training_cutoff_epoch': deadline-900,
            'planned_continuation': True, 'automatic_failure_restart': False,
            'resume_checkpoint': str(initial), 'prior_updates': status['updates'], 'prior_samples': status['samples']}
    write(stage/'authorization.json', auth)
    remaining = int(deadline-time.time())-15
    assert remaining > 900
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               PYTHONPATH='/root/autodl-tmp/monitor-public-sft-20261016/vendor:/root/monitor-retraining-qwen35-20261016/vendor')
    command = ['timeout', '--signal=TERM', '--kill-after=5s', f'{remaining}s', sys.executable,
               '-u', str(stage/'fava_trial.py'), '--mode', 'train', '--root', str(stage),
               '--base', '/root/monitor-retraining-qwen35-20261016/assets/model',
               '--initial', str(initial/'adapter'), '--resume', str(initial), '--baseline-root', str(root)]
    with (stage/'worker.log').open('xb') as log:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        write(stage/'launch.json', {'timeout_pid': child.pid, 'deadline_epoch': deadline, 'original_start_epoch': original['start_epoch']})
        code = child.wait()
    write(stage/'wrapper_exit.json', {'exit_code': code, 'finished_epoch': time.time()})
    print(json.dumps({'continuation_exit_code': code}), flush=True)


if __name__ == '__main__':
    root = Path(sys.argv[1]).resolve()
    write(root/'continuation_launch.json', {'controller_pid': os.getpid(), 'created_epoch': time.time()})
    try:
        coordinate(root)
    except Exception as exc:
        write(root/'continuation_failure.json', {'error': repr(exc), 'epoch': time.time()})
        raise
