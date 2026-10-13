import argparse,json,hashlib,shutil,subprocess,importlib.metadata as md
from pathlib import Path
EXPECTED={'transformers':'4.57.4','accelerate':'1.10.1','tokenizers':'0.22.2','huggingface-hub':'0.36.2','safetensors':'0.8.0'}
WHEELS={'peft-0.17.1-py3-none-any.whl':'3d129d64def3d74779c32a080d2567e5f7b674e77d546e3585138216d903f99e','bitsandbytes-0.50.0-py3-none-manylinux_2_24_x86_64.whl':'173d137610468bec9cddbaa2e049254e97792657ab984e3e737bec1772c1668c'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def install(target,wheelhouse):
 actor=Path('/root/autodl-tmp/mini-faithbench-v0/actor-venv/lib/python3.12/site-packages');site=target/'venv/lib/python3.12/site-packages'
 if (target/'environment.json').exists():raise ValueError('already ready')
 distributions={d.metadata['Name'].lower().replace('_','-'):d for d in md.distributions(path=[str(actor)])};copied={};versions={}
 for name in [*EXPECTED,'regex','hf-xet']:
  d=distributions[name]
  if name in EXPECTED and d.version!=EXPECTED[name]:raise ValueError('wrong existing dependency')
  versions[name]=d.version
  for rel in d.files:
   source=(actor/rel).resolve()
   if not source.is_relative_to(actor) or not source.is_file():continue
   dest=(site/rel).resolve()
   if not dest.is_relative_to(site):raise ValueError('unsafe dependency path')
   h=sha(source)
   if dest.exists() and sha(dest)!=h:raise ValueError('different target dependency')
   dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():shutil.copyfile(source,dest)
   if sha(dest)!=h:raise ValueError('copy integrity failed')
   copied[str(rel)]=h
 print(json.dumps({'event':'dependencies_copied','files':len(copied),'versions':versions}),flush=True)
 dump={'source':'Actor_dependency_files_read_only','versions':versions,'copied_file_sha256':copied};(target/'dependency_copy_verified.json').write_text(json.dumps(dump,indent=2),encoding='utf8')
 for n,h in WHEELS.items():
  if sha(wheelhouse/n)!=h:raise ValueError('wheel mismatch '+n)
 py=target/'venv/bin/python';subprocess.run([str(py),'-m','pip','install','--no-deps','--no-index',*[str(wheelhouse/n) for n in WHEELS]],check=True,timeout=60)
 code='import json,sys,importlib.metadata as m,torch,transformers,peft,bitsandbytes; print(json.dumps({"prefix":sys.prefix,"torch":torch.__version__,"cuda":torch.version.cuda,"packages":{n:m.version(n) for n in ["transformers","accelerate","tokenizers","huggingface-hub","safetensors","peft","bitsandbytes"]}}))'
 r=subprocess.run([str(py),'-c',code],capture_output=True,text=True,check=True,timeout=40);v=json.loads(r.stdout)
 if v['prefix']!=str(target/'venv') or v['torch']!='2.12.1+cu130':raise ValueError('isolation mismatch')
 (target/'environment.json').write_text(json.dumps(v,indent=2),encoding='utf8');print(json.dumps({'event':'environment_ready','metadata':v}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);p.add_argument('--wheelhouse',type=Path,required=True);a=p.parse_args();install(a.target,a.wheelhouse)
