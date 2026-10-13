"""Key-only deployment, one launch and backup for the authorized six-case preflight."""
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from control_relation_sft_comparison_v1 import SSH, call

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / 'experiments/faithbench_monitor_v0/private/binding_compact_probe_v1_20261011'
PREFIX = "t=s/'binding_compact_probe_v1_trial'\no=s/'binding_compact_probe_v1_operation'\n"


def remote(code, timeout=55):
    return call(PREFIX + code, timeout=timeout)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(output):
    return "rt=json.loads((s/'evidence_contract_v3_trial/runtime.json').read_text())\ncmd=[str(s/'venv/bin/python'),str(r/'experiments/faithbench_monitor_v0/pilot_v3/run_binding_compact_probe_v1.py'),'--inputs',str(r/'experiments/faithbench_monitor_v0/private/binding_compact_probe_v1_20261011/inputs.json'),'--base',rt['base'],'--output',str(s/" + repr(output) + "),'--expected-protection',str(r/'experiments/faithbench_monitor_v0/private/binding_compact_probe_v1_20261011/expected_protection.json'),'--old-adapter',str(s/'evidence_contract_v3_trial/adapter')]\n"


def main(mode):
    if mode == 'deploy':
        package = json.loads((LOCAL / 'inputs.json').read_text(encoding='utf-8'))
        hashes = dict(package['frozen_dependencies'])
        for name in ['inputs.json', 'expected_protection.json']:
            hashes[(LOCAL / name).relative_to(ROOT).as_posix()] = sha(LOCAL / name)
        hashes[Path(__file__).relative_to(ROOT).as_posix()] = sha(Path(__file__))
        missing = json.loads(remote("assert not t.exists() and not o.exists()\nh=" + repr(hashes) + "\nmissing=[]\nfor name,digest in h.items():\n p=r/name\n if p.exists():\n  assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name\n else:missing.append(name)\nprint(json.dumps(missing))\n"))
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as stream:
            for name in missing:
                stream.add(ROOT / name, arcname=name)
        if missing:
            result = subprocess.run(SSH + ['tar -xf - -C /root/autodl-tmp/monitor-pilot-20261009'], input=archive.getvalue(), capture_output=True, timeout=50)
            result.check_returncode()
        print(remote("h=" + repr(hashes) + "\nfor name,digest in h.items():\n assert hashlib.sha256((r/name).read_bytes()).hexdigest()==digest,name\nprint(json.dumps({'uploaded_new_files':" + str(len(missing)) + ",'verified':len(h)}))\n"))
    elif mode == 'preflight':
        print(remote(command('binding_compact_probe_v1_cpu_preflight') + "p=subprocess.run(cmd+['--preflight-only'],capture_output=True,text=True,timeout=45)\nprint(p.stdout,p.stderr)\nassert p.returncode==0\nprint((s/'binding_compact_probe_v1_cpu_preflight/preflight.json').read_text())\n"))
    elif mode == 'launch':
        print(remote(command('binding_compact_probe_v1_trial') + "assert (s/'binding_compact_probe_v1_cpu_preflight/preflight.json').exists()\nassert not t.exists() and not o.exists()\ngpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True)\nassert '4090' in gpu and '0 MiB' in gpu,gpu\no.mkdir()\nf=(o/'worker.log').open('x')\np=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)\nwith (o/'launch.json').open('x') as stream:json.dump({'pid':p.pid,'cmd':cmd},stream)\nprint(json.dumps({'pid':p.pid,'gpu_before':gpu}))\n"))
    elif mode == 'status':
        print(remote("print(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True))\nif (o/'launch.json').exists():\n pid=json.loads((o/'launch.json').read_text())['pid']\n print('process_exists',Path('/proc'/Path(str(pid))).exists())\np=t/'predictions.jsonl'\nprint('predictions',len(p.read_text().splitlines()) if p.exists() else 0)\nprint((o/'worker.log').read_text()[-1400:] if (o/'worker.log').exists() else 'no log')\nprint((t/'completed.json').read_text() if (t/'completed.json').exists() else 'incomplete')\n"))
    elif mode == 'fetch':
        data = json.loads(remote("assert (t/'completed.json').exists()\nfiles=list(t.glob('*'))+list(o.glob('*'))+list((s/'binding_compact_probe_v1_cpu_preflight').glob('*'))\nprint(json.dumps({str(p.relative_to(s)):{'data':base64.b64encode(p.read_bytes()).decode(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files if p.is_file()}))\n"))
        target = LOCAL / 'backup'
        target.mkdir(exist_ok=False)
        hashes = {}
        for name, row in data.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = base64.b64decode(row['data'])
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
            with path.open('xb') as stream:
                stream.write(raw)
            hashes[name] = row['sha256']
        with (LOCAL / 'backup_hashes.json').open('x', encoding='utf-8') as stream:
            json.dump(hashes, stream, indent=2)
        print(json.dumps(dict(files=len(hashes), bytes=sum((target / name).stat().st_size for name in hashes), hash_verified=True)))
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
