"""Exclusive deploy, CPU preflight, one GPU launch, status and verified backup."""
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from control_relation_sft_comparison_v1 import SSH,call
sys.path.insert(0,str(Path(__file__).parent))
from prepare import PRIVATE,load,dump,sha256

REMOTE='/root/autodl-tmp/deepseek-monitor-actor-v1-20261012'
PYTHON='/root/autodl-tmp/monitor-sft-smoke-20261010/venv/bin/python'
PREFIX='a=Path('+repr(REMOTE)+')\n'
WORKER='experiments/actor_b/deepseek_monitor_pilot_v1/gpu_worker.py'


def main(mode):
    if mode=='inspect':
        print(call(PREFIX+"print(json.dumps({'hostname':socket.gethostname(),'root_exists':a.exists(),'runtime_exists':Path("+repr(PYTHON)+").exists(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,utilization.gpu','--format=csv,noheader'],text=True),'processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader'],text=True),'disk':subprocess.check_output(['df','-h','/root/autodl-tmp'],text=True)}))\n"))
    elif mode=='deploy':
        freeze=load(PRIVATE/'execution_freeze.json')
        files={n:ROOT/n for n in freeze['dependencies']}
        files.update({(PRIVATE/n).relative_to(ROOT).as_posix():PRIVATE/n for n in freeze['files']})
        files[(PRIVATE/'execution_freeze.json').relative_to(ROOT).as_posix()]=PRIVATE/'execution_freeze.json'
        assert all(sha256(ROOT/n)==h for n,h in freeze['dependencies'].items())
        assert all(sha256(PRIVATE/n)==h for n,h in freeze['files'].items())
        hashes={n:sha256(p) for n,p in files.items()}
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as out:
            for n,p in files.items():
                out.add(p,arcname=n)
        print(call(PREFIX+"assert not a.exists()\na.mkdir()\nprint('exclusive remote root created')\n"))
        transfer=subprocess.run(SSH+['tar -xf - -C '+REMOTE],input=archive.getvalue(),capture_output=True,timeout=55)
        transfer.check_returncode()
        print(call(PREFIX+'h='+repr(hashes)+"\nfor n,d in h.items():\n assert hashlib.sha256((a/n).read_bytes()).hexdigest()==d,n\nprint(json.dumps({'deployed_files':len(h)}))\n"))
        dump(PRIVATE/'deployment.json',{'remote':REMOTE,'files':hashes,'archive_bytes':len(archive.getvalue())})
    elif mode in ['cpu','launch']:
        stage='cpu' if mode=='cpu' else 'worker'
        worker_mode='cpu' if mode=='cpu' else 'run'
        code=PREFIX+"assert a.exists() and not (a/"+repr(stage+'_launch.json')+").exists()\n"
        if mode=='launch':
            code+="assert (a/'cpu_preflight.json').exists() and not (a/'output').exists()\ngpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],text=True)\nassert '4090' in gpu and '0 MiB' in gpu,gpu\n"
        code+="cmd=["+repr(PYTHON)+",'-u',str(a/"+repr(WORKER)+"),"+repr(worker_mode)+"]\nenv=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')\n"
        if mode=='cpu':
            code+="env['CUDA_VISIBLE_DEVICES']=''\n"
        code+="f=(a/"+repr(stage+'.log')+").open('x')\np=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)\nwith (a/"+repr(stage+'_launch.json')+").open('x') as out:json.dump({'pid':p.pid,'cmd':cmd},out)\nprint(json.dumps({'stage':"+repr(stage)+",'pid':p.pid}))\n"
        print(call(code))
    elif mode=='status':
        result=json.loads(call(PREFIX+"st={}\nfor stage in ['cpu','worker']:\n p=a/(stage+'_launch.json')\n if p.exists():\n  pid=json.loads(p.read_text())['pid']\n  proc=Path('/proc/'+str(pid))\n  st[stage]={'pid':pid,'process_exists':proc.exists(),'state':(proc/'stat').read_text().split()[2] if proc.exists() else None,'log_tail':(a/(stage+'.log')).read_text()[-2800:]}\nprint(json.dumps({'stages':st,'cpu_complete':(a/'cpu_preflight.json').exists(),'worker_complete':(a/'worker_completed.json').exists(),'terminals':len(list((a/'output').glob('*/terminal.json'))),'raw_requests':len(list((a/'output').glob('*/raw_*.json'))),'cache_returns':len(list((a/'output').glob('*/return_*.json'))),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True),'processes':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader'],text=True)}))\n"))
        print(json.dumps(result,ensure_ascii=False))
        # Status snapshots accumulate instead of overwriting experiment outputs.
        folder=PRIVATE/'status'
        folder.mkdir(exist_ok=True)
        dump(folder/(str(len(list(folder.glob('*.json')))+1).zfill(3)+'.json'),result)
    elif mode in ['fetch_cpu','fetch']:
        code=PREFIX
        if mode=='fetch_cpu':
            code+="assert (a/'cpu_preflight.json').exists()\nfiles=[a/n for n in ['cpu_preflight.json','cpu.log','cpu_launch.json']]\n"
            destination=PRIVATE/'cpu_backup'
        else:
            code+="assert (a/'worker_completed.json').exists()\nfiles=[p for p in (a/'output').rglob('*') if p.is_file()]+[a/n for n in ['worker.log','worker_launch.json','worker_completed.json','protection_before.json','protection_after.json']]\n"
            destination=PRIVATE/'backup'
        code+="print(json.dumps({p.relative_to(a).as_posix():{'data':base64.b64encode(p.read_bytes()).decode(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}))\n"
        data=json.loads(call(code))
        destination.mkdir()
        hashes={}
        for name,record in data.items():
            raw=base64.b64decode(record['data'])
            assert hashlib.sha256(raw).hexdigest()==record['sha256']
            path=destination/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(raw)
            hashes[name]=record['sha256']
        dump(PRIVATE/(destination.name+'_hashes.json'),hashes)
        print(json.dumps({'backup_files':len(hashes),'hash_verified':True}))
    else:
        raise ValueError(mode)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
