"""Key-only control of the approved 14601 paired trial; exclusive new paths."""
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / 'experiments/faithbench_monitor_v0/private/relation_sft_comparison_20261011'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'UserKnownHostsFile=D:/Codex/AIGC/experiments/faithbench_monitor_v0/private/clone_20261011_14601_known_hosts', '-p', '14601', 'root@connect.bjb1.seetacloud.com']
PREFIX = "from pathlib import Path\nimport json,subprocess,socket,hashlib,base64,os\nassert socket.gethostname()=='autodl-container-8fc0409877-3d080f20'\nr=Path('/root/autodl-tmp/monitor-pilot-20261009')\ns=Path('/root/autodl-tmp/monitor-sft-smoke-20261010')\nt=s/'relation_sft_comparison_v1_trial'\no=s/'relation_sft_comparison_v1_operation'\n"


def call(code, timeout=55):
    result = subprocess.run(SSH + ['/root/miniconda3/bin/python -'], input=PREFIX + code, text=True, encoding='utf8', capture_output=True, timeout=timeout)
    if result.returncode:
        print(result.stdout, result.stderr)
        result.check_returncode()
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(output):
    return "rt=json.loads((s/'evidence_contract_v3_trial/runtime.json').read_text())\ncmd=[str(s/'venv/bin/python'),str(r/'experiments/faithbench_monitor_v0/pilot_v3/run_relation_sft_comparison_v1.py'),'--inputs',str(r/'experiments/faithbench_monitor_v0/private/relation_sft_comparison_20261011/inputs.json'),'--base',rt['base'],'--output',str(s/" + repr(output) + "),'--expected-protection',str(r/'experiments/faithbench_monitor_v0/private/relation_sft_comparison_20261011/expected_protection.json'),'--old-adapter',str(s/'evidence_contract_v3_trial/adapter')]\n"


def main(mode):
    if mode == 'deploy':
        package = json.loads((LOCAL / 'inputs.json').read_text(encoding='utf8'))
        hashes = dict(package['frozen_dependencies'])
        for path in LOCAL.glob('*.json'):
            hashes[path.relative_to(ROOT).as_posix()] = sha(path)
        control = Path(__file__)
        hashes[control.relative_to(ROOT).as_posix()] = sha(control)
        remote = json.loads(call("assert not t.exists() and not o.exists()\nh=" + repr(hashes) + "\nmissing=[]\nfor name,digest in h.items():\n p=r/name\n if p.exists():\n  assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name\n else:missing.append(name)\nprint(json.dumps(missing))\n"))
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as stream:
            for name in remote:
                stream.add(ROOT / name, arcname=name)
        result = subprocess.run(SSH + ['tar -xf - -C /root/autodl-tmp/monitor-pilot-20261009'], input=archive.getvalue(), capture_output=True, timeout=50)
        result.check_returncode()
        print(call("h=" + repr(hashes) + "\nfor name,digest in h.items():\n assert hashlib.sha256((r/name).read_bytes()).hexdigest()==digest,name\nprint(json.dumps({'uploaded_new_files':" + str(len(remote)) + ",'all_hashes_verified':len(h)}))\n"))
    elif mode == 'preflight':
        print(call(command('relation_sft_comparison_v1_cpu_preflight') + "p=subprocess.run(cmd+['--preflight-only'],capture_output=True,text=True,timeout=45)\nprint(p.stdout,p.stderr)\nassert p.returncode==0\nprint((s/'relation_sft_comparison_v1_cpu_preflight/preflight.json').read_text())\n"))
    elif mode == 'launch':
        print(call(command('relation_sft_comparison_v1_trial') + "assert (s/'relation_sft_comparison_v1_cpu_preflight/preflight.json').exists()\nassert not t.exists() and not o.exists()\ngpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True)\nassert '4090' in gpu and '0 MiB' in gpu,gpu\no.mkdir()\nf=(o/'worker.log').open('x')\np=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)\nwith (o/'launch.json').open('x') as stream:json.dump({'pid':p.pid,'cmd':cmd},stream)\nprint(json.dumps({'pid':p.pid,'gpu_before':gpu}))\n"))
    elif mode == 'status':
        print(call("print(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True))\nif (o/'launch.json').exists():\n pid=json.loads((o/'launch.json').read_text())['pid']\n print('process_exists',Path('/proc'/Path(str(pid))).exists())\nfor method in ['ordinary','relation']:\n p=t/method/'training.jsonl'\n print(method,'updates',len(p.read_text().splitlines()) if p.exists() else 0)\np=t/'predictions.jsonl'\nprint('predictions',len(p.read_text().splitlines()) if p.exists() else 0)\nprint((o/'worker.log').read_text()[-1800:] if (o/'worker.log').exists() else 'no log')\nprint((t/'completed.json').read_text() if (t/'completed.json').exists() else 'incomplete')\n"))
    elif mode == 'fetch':
        data = json.loads(call("assert (t/'completed.json').exists()\nfiles=list(t.rglob('*'))+list(o.glob('*'))+list((s/'relation_sft_comparison_v1_cpu_preflight').glob('*'))\nprint(json.dumps({str(p.relative_to(s)):{'data':base64.b64encode(p.read_bytes()).decode(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files if p.is_file()}))\n", timeout=55))
        target = LOCAL / 'backup'
        target.mkdir()
        hashes = {}
        for name, row in data.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = base64.b64decode(row['data'])
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
            with path.open('xb') as stream:
                stream.write(raw)
            hashes[name] = row['sha256']
        with (LOCAL / 'backup_hashes.json').open('x', encoding='utf8') as stream:
            json.dump(hashes, stream, indent=2)
        print(json.dumps({'backup_files': len(hashes), 'bytes': sum((target / name).stat().st_size for name in hashes), 'hash_verified': True}))
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    main(sys.argv[1])
