"""Exclusive deployment, one launch, status and hash-checked backup for this audit."""
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/faithbench_monitor_v0/pilot_v3'))
from control_relation_sft_comparison_v1 import SSH, call
sys.path.insert(0, str(ROOT / 'experiments/actor_b'))
from run_b0 import sha256, write_json

PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private/automatic_audit_v1_20261012'
REMOTE = '/root/autodl-tmp/monitor-automatic-audit-v1-20261012'
PYTHON = '/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python'
PREFIX = 'a=Path(' + repr(REMOTE) + ')\n'


def main(mode):
    if mode == 'inspect':
        print(call(PREFIX + "print(json.dumps({'hostname':socket.gethostname(),'root_exists':a.exists(),'runtime_exists':Path(" + repr(PYTHON) + ").exists(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,utilization.gpu','--format=csv,noheader'],text=True),'processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader'],text=True),'disk':subprocess.check_output(['df','-h','/root/autodl-tmp'],text=True)}))\n"))
    elif mode == 'deploy':
        frozen = json.loads((PRIVATE / 'freeze.json').read_text())
        assert all(sha256(PRIVATE / n) == h for n, h in frozen['files'].items())
        assert all(sha256(ROOT / n) == h for n, h in frozen['dependencies'].items())
        files = {n: ROOT / n for n in ['experiments/actor_b/run_b0.py',
            'experiments/actor_b/actor_b_protocol.py',
            'experiments/faithbench_monitor_v0/automatic_audit_v1/gpu_worker.py',
            'experiments/faithbench_monitor_v0/automatic_audit_v1/gpu_control.py']}
        for name in ['inputs.json', 'cpu_preflight.json', 'freeze.json', 'packet.json', 'review_template.json']:
            files[(PRIVATE / name).relative_to(ROOT).as_posix()] = PRIVATE / name
        # Review template is provenance only; the worker reads only package messages.
        files[(PRIVATE / 'expected_protection.json').relative_to(ROOT).as_posix()] = ROOT / 'experiments/faithbench_monitor_v0/private/binding_table_probe_v1_20261011/expected_protection.json'
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as stream:
            for name, path in files.items():
                stream.add(path, arcname=name)
        hashes = {name: sha256(path) for name, path in files.items()}
        print(call(PREFIX + "assert not a.exists()\na.mkdir()\nprint('exclusive root created')\n"))
        transfer = subprocess.run(SSH + ['tar -xf - -C ' + REMOTE], input=archive.getvalue(),
                                  capture_output=True, timeout=45)
        transfer.check_returncode()
        print(call(PREFIX + 'h=' + repr(hashes) + "\nfor n,d in h.items():\n assert hashlib.sha256((a/n).read_bytes()).hexdigest()==d,n\nprint(json.dumps({'deployed_files':len(h)}))\n"))
        write_json(PRIVATE / 'deployment.json', {'root': REMOTE, 'files': hashes,
                                               'archive_bytes': len(archive.getvalue())})
    elif mode == 'launch':
        print(call(PREFIX + "assert a.exists() and not (a/'launch.json').exists() and not (a/'output').exists()\ngpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True)\nassert '4090' in gpu and '0 MiB' in gpu,gpu\ncmd=[" + repr(PYTHON) + ",' -u'.strip(),str(a/'experiments/faithbench_monitor_v0/automatic_audit_v1/gpu_worker.py')]\nenv=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')\nf=(a/'worker.log').open('x')\np=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)\nwith (a/'launch.json').open('x') as out:json.dump({'pid':p.pid,'cmd':cmd,'gpu_before':gpu},out)\nprint(json.dumps({'pid':p.pid,'gpu_before':gpu}))\n"))
    elif mode == 'status':
        result = json.loads(call(PREFIX + "pid=json.loads((a/'launch.json').read_text())['pid']\nprint(json.dumps({'pid':pid,'process_exists':Path('/proc/'+str(pid)).exists(),'worker_complete':(a/'worker_completed.json').exists(),'raw_exists':(a/'output/review.json').exists(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True),'log_tail':(a/'worker.log').read_text()[-2200:]}))\n"))
        write_json(PRIVATE / 'runtime.json', result)
        print(json.dumps(result, ensure_ascii=False))
    elif mode == 'fetch':
        data = json.loads(call(PREFIX + "assert (a/'worker_completed.json').exists()\nfiles=[a/n for n in ['output/review.json','worker.log','launch.json','worker_completed.json','deployment_preflight.json','protection_before.json','protection_after.json']]\nprint(json.dumps({p.relative_to(a).as_posix():{'data':base64.b64encode(p.read_bytes()).decode(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}))\n"))
        backup = PRIVATE / 'backup'
        backup.mkdir()
        hashes = {}
        for name, value in data.items():
            raw = base64.b64decode(value['data'])
            assert hashlib.sha256(raw).hexdigest() == value['sha256']
            path = backup / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
            hashes[name] = value['sha256']
        write_json(PRIVATE / 'backup_hashes.json', hashes)
        print(json.dumps({'backup_files': len(hashes), 'hash_verified': True}))
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
