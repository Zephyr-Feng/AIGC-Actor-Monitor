"""Finish the same epoch within the user-approved ten-hour aggregate budget."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(value, ensure_ascii=False), flush=True)


def own_worker(pid, root):
    path = Path(f'/proc/{pid}')
    try:
        status = (path/'status').read_text()
        command = (path/'cmdline').read_bytes().split(b'\0')
    except FileNotFoundError:
        return False
    if '\nState:\tZ' in status:
        return False
    return b'train.py' in command and str(root).encode() in command


def run(root):
    first = json.loads((root/'worker.log').open(encoding='utf8').readline())
    assert first['event'] == 'load_start' and first['train_rows'] == 12141
    pid = first['pid']
    deadline = datetime.fromisoformat(first['at']).timestamp() + 10*3600
    approval = root/'budget_10h.json'
    assert not approval.exists(), 'one continuation controller only'
    write(approval, {'authorized_total_hours':10, 'original_pid':pid,
        'deadline_unix':deadline, 'epochs':1, 'new_data':False})
    while own_worker(pid, root):
        if time.time() >= deadline:
            os.kill(pid, signal.SIGTERM)
            write(root/'controller_status.json', {'state':'budget_exhausted_original_worker', 'pid':pid})
            return
        time.sleep(min(30, max(1, deadline-time.time())))
    output = root/'run'
    status_path = output/'status.json'
    if not status_path.exists():
        write(root/'controller_status.json', {'state':'worker_failed_no_automatic_restart'})
        return
    status = json.loads(status_path.read_text())
    if status['epoch_complete']:
        write(root/'controller_status.json', {'state':'epoch_complete_without_resume', **status})
        return
    latest = json.loads((output/'latest.json').read_text())
    assert latest['position'] == status['samples'] and latest['updates'] == status['updates']
    checkpoint = output/latest['checkpoint']
    remaining = deadline-time.time()
    if remaining < 300:
        write(root/'controller_status.json', {'state':'budget_exhausted', **status})
        return
    config = json.loads((output/'config.json').read_text())
    command = [sys.executable, '-u', str(root/'train.py'), '--root', str(root),
        '--base', config['base'], '--resume', str(checkpoint), '--hours', str(remaining/3600)]
    with (root/'resume.log').open('x', encoding='utf8') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        write(root/'controller_status.json', {'state':'resuming_same_epoch', 'pid':process.pid,
            'checkpoint':str(checkpoint), 'remaining_seconds':remaining})
        try:
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            write(root/'controller_status.json', {'state':'budget_exhausted_resumed_worker', 'pid':process.pid})
            return
    write(root/'controller_status.json', {'state':'resumed_worker_exited', 'exit_code':code,
        'status':json.loads(status_path.read_text())})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root.resolve())
