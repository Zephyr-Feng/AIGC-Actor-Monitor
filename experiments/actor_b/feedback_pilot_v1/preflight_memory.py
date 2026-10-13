"""CPU preflight using verified local dependencies in remote memory, no deployment."""
import base64
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pilot
from control import SSH


def main():
    package = pilot.verify(pilot.PRIVATE)
    modules = {name: (pilot.ACTOR / (name + '.py')).read_bytes().decode('utf-8')
               for name in ('actor_b_protocol', 'run_b0', 'contract_replay')}
    assets = {key: base64.b64encode((pilot.PRIVATE / item['file']).read_bytes()).decode()
              for key, item in package['assets'].items()}
    source = Path(__file__).with_name('pilot.py').read_text(encoding='utf-8')
    code = (
        "import os\nos.environ['CUDA_VISIBLE_DEVICES']=''\nos.environ['HF_HUB_OFFLINE']='1'\n"
        "os.environ['TRANSFORMERS_OFFLINE']='1'\n"
        "from pathlib import Path\nimport socket,json,base64,hashlib,sys,types\n"
        "assert socket.gethostname()=='autodl-container-8fc0409877-3d080f20'\n"
        "r=Path('/root/autodl-tmp/monitor-pilot-20261009')\n"
        "runtime=json.loads(Path('/root/autodl-tmp/monitor-sft-smoke-20261010/evidence_contract_v3_trial/runtime.json').read_text())\n"
        "package=json.loads(" + repr(json.dumps(package, ensure_ascii=False)) + ")\n"
        "modules=" + repr(modules) + "\n"
        "remote_dependency_state={}\n"
        "for name,digest in package['dependencies'].items():\n"
        " p=r/name\n"
        " remote_dependency_state[name]='missing' if not p.exists() else 'matching'\n"
        " if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name\n"
        "for name,source in modules.items():\n"
        " assert hashlib.sha256(source.encode()).hexdigest()==package['dependencies']['experiments/actor_b/'+name+'.py']\n"
        " module=types.ModuleType(name);module.__file__=str(r/'experiments/actor_b'/ (name+'.py'));sys.modules[name]=module\n"
        " exec(compile(source,module.__file__,'exec'),module.__dict__)\n"
        "scope={'__file__':str(r/'experiments/actor_b/feedback_pilot_v1/pilot.py'),'__name__':'cpu_memory_check'}\n"
        "exec(compile(" + repr(source) + ",scope['__file__'],'exec'),scope)\n"
        "assets=" + repr(assets) + "\n"
        "import torch\ntorch.set_num_threads(2)\n"
        "report,_,_=scope['cpu_check'](package,Path(runtime['base']),lambda key:base64.b64decode(assets[key]))\n"
        "report.update(hostname=socket.gethostname(),base=runtime['base'],torch=torch.__version__,cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],remote_files_written=False,remote_dependency_state=remote_dependency_state,dependencies_imported_from_verified_local_sources=True)\n"
        "print(json.dumps(report))\n"
    )
    result = subprocess.run(SSH + ['env PYTHONDONTWRITEBYTECODE=1 /root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python -'],
                            input=code, text=True, encoding='utf-8', capture_output=True, timeout=55)
    if result.returncode:
        print(result.stdout, result.stderr)
        result.check_returncode()
    report = json.loads(result.stdout)
    pilot.dump(pilot.PRIVATE / 'cpu_preflight.json', report)
    pilot.dump(pilot.PRIVATE / 'cpu_preflight_hashes.json', {
        'cpu_preflight.json': pilot.sha256(pilot.PRIVATE / 'cpu_preflight.json'),
        'freeze.json': pilot.sha256(pilot.PRIVATE / 'freeze.json'),
        'preflight_memory.py': pilot.sha256(Path(__file__))})
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
