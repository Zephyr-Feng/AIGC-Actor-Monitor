import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/sft_smoke_v1'))
import train_smoke as smoke
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from prepare_reasoned_portable import dump
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');a=p.parse_args();smoke.verify(a.inputs)
 probes=json.loads((a.inputs/'probe_evaluation.json').read_text(encoding='utf8'));assert len(probes)==16
 if a.preflight_only:
  tokenizer,_=smoke.cpu_preflight(a.inputs,a.base,a.output);counts=[]
  for row in probes:
   n=len(tokenizer.apply_chat_template([{'role':'user','content':row['user_text']}],tokenize=True,add_generation_prompt=True));assert n+384<=4096;counts.append({'id':row['id'],'input_tokens':n})
  dump(a.output/'probe_preflight.json',counts)
 else:
  evaluate=smoke.evaluate
  def with_probe(model,tokenizer,rows,phase,output):
   evaluate(model,tokenizer,rows,phase,output)
   if phase=='after':evaluate(model,tokenizer,probes,'after_probe',output)
  smoke.evaluate=with_probe;smoke.run(a.inputs,a.base,a.output)
