"""Install only in a new Monitor venv, reusing the existing system torch."""
import argparse,json,subprocess,venv,time
from pathlib import Path
PACKAGES=['transformers==4.57.4','accelerate==1.10.1','tokenizers==0.22.2','huggingface-hub==0.36.2','safetensors==0.8.0','peft==0.17.1','bitsandbytes==0.50.0']
def setup(target):
 target.mkdir(parents=True,exist_ok=False)
 constraint=target/'constraints.txt';constraint.write_text('torch==2.12.1+cu130\nnumpy==2.4.6\n',encoding='utf8')
 print(json.dumps({'event':'venv_start','at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}),flush=True)
 venv.EnvBuilder(system_site_packages=True,with_pip=True).create(target/'venv')
 py=target/'venv/bin/python';argv=[str(py),'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--timeout','15','--retries','1','--index-url','https://pypi.org/simple','-c',str(constraint),*PACKAGES]
 print(json.dumps({'event':'install_start','argv':argv}),flush=True);subprocess.run(argv,check=True,timeout=600)
 code='import json,sys,importlib.metadata as m,torch,transformers,peft,bitsandbytes; print(json.dumps({"prefix":sys.prefix,"torch":torch.__version__,"cuda":torch.version.cuda,"packages":{n:m.version(n) for n in ["transformers","accelerate","tokenizers","huggingface-hub","safetensors","peft","bitsandbytes"]}}))'
 r=subprocess.run([str(py),'-c',code],capture_output=True,text=True,check=True,timeout=45);metadata=json.loads(r.stdout)
 if metadata['prefix']!=str(target/'venv') or metadata['torch']!='2.12.1+cu130':raise ValueError('environment isolation mismatch')
 (target/'environment.json').write_text(json.dumps(metadata,indent=2),encoding='utf8');print(json.dumps({'event':'environment_ready','metadata':metadata}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);setup(p.parse_args().target)
