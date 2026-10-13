"""Exclusive isolated deployment and single-worker lifecycle for the approved pilot."""
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pilot
from control import SSH

REMOTE = '/root/autodl-tmp/actor-feedback-pilot-v1-20261011'
PYTHON = '/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python'
PREFIX = "from pathlib import Path\nimport json,subprocess,socket,hashlib,base64,os\nassert socket.gethostname()=='autodl-container-8fc0409877-3d080f20'\nr=Path(" + repr(REMOTE) + ")\n"


def call(code, timeout=55):
    result = subprocess.run(SSH + ['/root/miniconda3/bin/python -'], input=PREFIX + code,
                            text=True, encoding='utf-8', capture_output=True, timeout=timeout)
    if result.returncode:
        print(result.stdout, result.stderr)
        result.check_returncode()
    return result.stdout


def main(mode):
    if mode == 'inspect':
        print(call("print(json.dumps({'hostname':socket.gethostname(),'root_exists':r.exists(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True),'disk':subprocess.check_output(['df','-h','/root/autodl-tmp'],text=True)}))\n"))
    elif mode == 'deploy':
        pilot.verify(pilot.PRIVATE)
        freeze = json.loads((pilot.PRIVATE / 'freeze.json').read_text())
        files = set(freeze['dependencies']) | set(freeze['scripts'])
        for name in [*freeze['files'], 'freeze.json', 'cpu_preflight.json', 'cpu_preflight_hashes.json']:
            files.add((pilot.PRIVATE / name).relative_to(pilot.ROOT).as_posix())
        files.update('experiments/actor_b/feedback_pilot_v1/' + n for n in ['gpu_worker.py', 'gpu_control.py'])
        protection_source = pilot.ROOT / 'experiments/faithbench_monitor_v0/private/binding_table_probe_v1_20261011/expected_protection.json'
        with io.BytesIO() as buffer:
            with tarfile.open(fileobj=buffer, mode='w') as archive:
                for name in sorted(files):
                    archive.add(pilot.ROOT / name, arcname=name)
                archive.add(protection_source, arcname=(pilot.PRIVATE / 'expected_protection.json').relative_to(pilot.ROOT).as_posix())
            payload = buffer.getvalue()
        hashes = {name: pilot.sha256(pilot.ROOT / name) for name in files}
        hashes[(pilot.PRIVATE / 'expected_protection.json').relative_to(pilot.ROOT).as_posix()] = pilot.sha256(protection_source)
        print(call("assert not r.exists()\nr.mkdir()\nprint('isolated root created')\n"))
        result = subprocess.run(SSH + ['tar -xf - -C ' + REMOTE], input=payload, capture_output=True, timeout=45)
        result.check_returncode()
        print(call("h=" + repr(hashes) + "\nfor name,digest in h.items():\n assert hashlib.sha256((r/name).read_bytes()).hexdigest()==digest,name\nprint(json.dumps({'deployed_files':len(h),'bytes':" + str(len(payload)) + "}))\n"))
        pilot.dump(pilot.PRIVATE / 'deployment.json', {'root': REMOTE, 'files': hashes, 'archive_bytes': len(payload)})
    elif mode == 'launch':
        print(call("assert r.exists() and not (r/'launch.json').exists() and not (r/'output').exists()\ngpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True)\nassert '4090' in gpu and '0 MiB' in gpu,gpu\ncmd=[" + repr(PYTHON) + ",' -u'.strip(),str(r/'experiments/actor_b/feedback_pilot_v1/gpu_worker.py')]\nenv=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')\nf=(r/'worker.log').open('x')\np=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)\nwith (r/'launch.json').open('x') as stream:json.dump({'pid':p.pid,'cmd':cmd,'gpu_before':gpu},stream)\nprint(json.dumps({'pid':p.pid,'gpu_before':gpu}))\n"))
    elif mode == 'status':
        print(call("pid=json.loads((r/'launch.json').read_text())['pid']\nprint(json.dumps({'pid':pid,'process_exists':Path('/proc/'+str(pid)).exists(),'output_files':[p.name for p in (r/'output').glob('*.json')] if (r/'output').exists() else [],'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True),'worker_complete':(r/'worker_completed.json').exists()}))\nprint((r/'worker.log').read_text()[-2400:])\n"))
    elif mode == 'fetch':
        data = json.loads(call("assert (r/'worker_completed.json').exists()\nfiles=[p for p in (r/'output').glob('*') if p.is_file()]+[r/name for name in ['worker.log','launch.json','worker_completed.json','deployment_preflight.json','protection_before.json','protection_after.json']]\nprint(json.dumps({p.relative_to(r).as_posix():{'data':base64.b64encode(p.read_bytes()).decode(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}))\n"))
        backup = pilot.PRIVATE / 'backup'
        if backup.exists():
            assert not any(p.is_file() for p in backup.rglob('*')), 'backup already has files'
        else:
            backup.mkdir()
        hashes = {}
        for name, value in data.items():
            path = backup / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = base64.b64decode(value['data'])
            assert hashlib.sha256(raw).hexdigest() == value['sha256']
            with path.open('xb') as stream:
                stream.write(raw)
            hashes[name] = value['sha256']
        pilot.dump(pilot.PRIVATE / 'backup_hashes.json', hashes)
        print(json.dumps({'backup_files': len(hashes), 'hash_verified': True}))
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
