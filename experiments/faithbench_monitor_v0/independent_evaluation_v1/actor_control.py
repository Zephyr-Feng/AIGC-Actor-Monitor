"""Exclusive deployment, one CPU/GPU task, status, and verified output backup."""
import io
import base64
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/faithbench_monitor_v0/pilot_v3'))
from control_relation_sft_comparison_v1 import SSH, call
sys.path.insert(0, str(Path(__file__).parent))
from prepare_actor import OUT, sha, write

REMOTE = '/root/autodl-tmp/natural-actor-monitor-20261013'
PYTHON = '/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python'
WORKER = 'experiments/faithbench_monitor_v0/independent_evaluation_v1/actor_worker.py'
PREFIX = 'a=Path(' + repr(REMOTE) + ')\n'


def freeze():
    assert not (OUT / 'actor_freeze.json').exists() and not (OUT / 'baseline_runtime.json').exists()
    preparation = json.loads((OUT / 'preparation.json').read_text())
    assert all(sha(OUT / p) == h for p, h in preparation['files'].items())
    assert all(sha(ROOT / p) == h for p, h in json.loads((OUT / 'payload_sources.json').read_text()).items())
    with (OUT / 'baseline_runtime.json').open('xb') as stream:
        stream.write((ROOT / 'experiments/actor_b/heldout_confirmation/outputs/runtime.json').read_bytes())
    paths = [ROOT / p for p in (
        'experiments/actor_b/actor_b0_d/run_b0_d_condition.py', 'experiments/actor_b/actor_b_protocol.py',
        'experiments/actor_b/contract_replay.py', 'experiments/actor_b/run_b0.py',
        'experiments/actor_b/prompts/system_prompt.txt', 'experiments/actor_b/schemas/actor_b_action.schema.json',
        'experiments/actor_b/config/model_config.json', 'experiments/actor_b/config/generation_config.json', WORKER)]
    paths += [OUT / p for p in ('actor_manifest.jsonl', 'tool_results.jsonl', 'tool_cards.json', 'baseline_runtime.json')]
    assets = json.loads((OUT / 'assets.json').read_text())
    assert len(assets) == 120
    write('actor_freeze.json', {'files': {p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
        'assets': {p: v['sha256'] for p, v in assets.items()}, 'model_revision': '0c351dd01ed87e9c1b53cbc748cba10e6187ff3b',
        'model_config_sha256': '5cd452860dc1e9c29dd71cc3cef7f39b338b7a40793f7a260655c2d3568f3661',
        'expected_protection': json.loads((ROOT / 'experiments/faithbench_monitor_v0/private/deepseek_monitor_actor_v1_20261012/expected_protection.json').read_text())})
    print('13 runtime files and 120 assets frozen; selection/GT/preaudit excluded', flush=True)


def deploy():
    frozen = json.loads((OUT / 'actor_freeze.json').read_text())
    assert all(sha(ROOT / p) == h for p, h in frozen['files'].items())
    assets = json.loads((OUT / 'assets.json').read_text())
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as stream:
        for p in frozen['files']:
            stream.add(ROOT / p, arcname=p)
        freeze_path = OUT / 'actor_freeze.json'
        stream.add(freeze_path, arcname=freeze_path.relative_to(ROOT).as_posix())
        for dest, spec in assets.items():
            if 'local_source' in spec:
                assert sha(ROOT / spec['local_source']) == spec['sha256']
                stream.add(ROOT / spec['local_source'], arcname=dest)
    print(call(PREFIX + "assert not a.exists()\na.mkdir()\nprint('exclusive root created')\n"))
    result = subprocess.run(SSH + ['tar -xf - -C ' + REMOTE], input=archive.getvalue(), capture_output=True, timeout=55)
    result.check_returncode()
    images = {p: v for p, v in assets.items() if 'remote_source' in v}
    code = PREFIX + 'import shutil\nimages=' + repr(images) + '\n'
    code += "for dest,spec in images.items():\n src=Path(spec['remote_source']).resolve()\n assert src.is_relative_to(Path('/root/autodl-tmp/actor0-bfree-20261002/data'))\n assert hashlib.sha256(src.read_bytes()).hexdigest()==spec['sha256']\n target=a/dest\n assert not target.exists() and target.resolve().is_relative_to(a)\n shutil.copyfile(src,target)\n"
    code += 'files=' + repr(frozen['files']) + '\nassets=' + repr(frozen['assets']) + '\n'
    code += "assert all(hashlib.sha256((a/p).read_bytes()).hexdigest()==h for p,h in {**files,**assets}.items())\nprint(json.dumps({'runtime_files_verified':len(files),'assets_verified':len(assets)}))\n"
    print(call(code))
    write('deployment.json', {'remote': REMOTE, 'files': frozen['files'], 'assets': frozen['assets'],
                            'archive_bytes': len(archive.getvalue()), 'identity_map_uploaded': False})


def launch(mode):
    stage = 'cpu' if mode == 'cpu' else 'worker'
    code = PREFIX + "assert a.exists() and not (a/" + repr(stage + '_launch.json') + ").exists()\n"
    if mode == 'run':
        code += "assert (a/'cpu_preflight.json').exists() and not (a/'output').exists()\ngpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True)\nassert '4090' in gpu and '0 MiB' in gpu,gpu\n"
    code += "env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')\n"
    if mode == 'cpu':
        code += "env['CUDA_VISIBLE_DEVICES']=''\n"
    code += "cmd=[" + repr(PYTHON) + ",'-u',str(a/" + repr(WORKER) + ")," + repr(mode) + "]\nf=(a/" + repr(stage + '.log') + ").open('x')\np=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)\nwith (a/" + repr(stage + '_launch.json') + ").open('x') as f:json.dump({'pid':p.pid,'cmd':cmd},f)\nprint(json.dumps({'stage':" + repr(stage) + ",'pid':p.pid}))\n"
    print(call(code))


def status():
    code = PREFIX + "st={}\nfor stage in ['cpu','worker']:\n p=a/(stage+'_launch.json')\n if p.exists():\n  pid=json.loads(p.read_text())['pid']\n  proc=Path('/proc/'+str(pid))\n  st[stage]={'pid':pid,'process_exists':proc.exists(),'state':(proc/'stat').read_text().split()[2] if proc.exists() else None,'log_tail':(a/(stage+'.log')).read_text()[-1800:]}\n"
    code += "print(json.dumps({'stages':st,'cpu_complete':(a/'cpu_preflight.json').exists(),'worker_complete':(a/'worker_completed.json').exists(),'failures':[p.name for p in a.glob('*_failed.json')],'records':len(list((a/'output/records').glob('*.json'))),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True),'processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader'],text=True)}))\n"
    print(call(code))


def fetch():
    destination = OUT / 'actor_backup'
    assert not destination.exists()
    code = PREFIX + "assert (a/'worker_completed.json').exists()\nfiles=[p for p in (a/'output').rglob('*') if p.is_file()]+[a/p for p in ['cpu_preflight.json','cpu.log','cpu_launch.json','worker.log','worker_launch.json','worker_completed.json','protection_before.json','protection_after.json']]\nprint(json.dumps({p.relative_to(a).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))\n"
    hashes = json.loads(call(code))
    destination.mkdir()
    transfer = subprocess.run(SSH + ['tar -cf - -C ' + REMOTE + ' ' + ' '.join(hashes)], capture_output=True, timeout=55)
    transfer.check_returncode()
    with tarfile.open(fileobj=io.BytesIO(transfer.stdout)) as archive:
        assert set(archive.getnames()) == set(hashes)
        for entry in archive:
            target = (destination / entry.name).resolve()
            assert entry.isfile() and target.is_relative_to(destination.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.extractfile(entry).read()
            with target.open('xb') as stream:
                stream.write(data)
    assert all(sha(destination / p) == h for p, h in hashes.items())
    write('actor_backup_hashes.json', hashes)
    print(json.dumps({'verified_backup_files': len(hashes)}))


def peek():
    code = PREFIX + "files=sorted((a/'output/records').glob('*.json'))\nprint(json.dumps({p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'data':base64.b64encode(p.read_bytes()).decode()} for p in files}))\n"
    records = json.loads(call(code))
    folder = OUT / 'actor_preview'
    folder.mkdir(exist_ok=True)
    for name, spec in records.items():
        assert Path(name).name == name
        data = base64.b64decode(spec['data'])
        path = folder / name
        if path.exists():
            assert sha(path) == spec['sha256']
        else:
            with path.open('xb') as stream:
                stream.write(data)
            assert sha(path) == spec['sha256']
    print(json.dumps({'immutable_preview_records': len(records)}))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    mode = sys.argv[1]
    if mode in ('cpu', 'run'):
        launch(mode)
    else:
        {'freeze': freeze, 'deploy': deploy, 'status': status, 'fetch': fetch, 'peek': peek}[mode]()
