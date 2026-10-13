import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/sft_smoke_v1'))
from train_smoke import sha,verify,event,frozen_snapshot,evaluate
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from prepare_reasoned_portable import dump
def run(inputs,base,adapter,output):
 import torch
 from transformers import AutoTokenizer,Qwen3VLForConditionalGeneration,BitsAndBytesConfig
 from peft import PeftModel,prepare_model_for_kbit_training
 m=verify(inputs);assert sha(adapter/'adapter_model.safetensors')==m['adapter_sha256']
 output.mkdir(parents=True,exist_ok=False);rows=json.loads((inputs/'evaluation.json').read_text(encoding='utf8'));assert len(rows)==16
 tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True);counts=[]
 for row in rows:
  n=len(tokenizer.apply_chat_template([{'role':'user','content':row['user_text']}],tokenize=True,add_generation_prompt=True));assert n+384<=4096;counts.append({'id':row['id'],'input_tokens':n})
 dump(output/'preflight.json',counts);event('frozen_snapshot_before');before=frozen_snapshot(base);dump(output/'frozen_before.json',before)
 torch.manual_seed(42);torch.cuda.manual_seed_all(42);torch.cuda.reset_peak_memory_stats()
 runtime={'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'inputs_sha256':sha(inputs/'manifest.json'),'adapter_sha256':m['adapter_sha256'],'training_steps':0,'generation_requests':32,'max_new_tokens':384,'gold':False,'independent_test':False};dump(output/'runtime.json',runtime)
 event('load_start');q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
 model=Qwen3VLForConditionalGeneration.from_pretrained(base,local_files_only=True,torch_dtype=torch.bfloat16,quantization_config=q,device_map={'':0},attn_implementation='sdpa');model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False});model=PeftModel.from_pretrained(model,adapter,is_trainable=False);assert not any(p.requires_grad for p in model.parameters());event('load_end')
 with model.disable_adapter():evaluate(model,tokenizer,rows,'before',output)
 evaluate(model,tokenizer,rows,'after',output)
 del model;torch.cuda.empty_cache();event('frozen_snapshot_after');after=frozen_snapshot(base);dump(output/'frozen_after.json',after);assert before==after and sha(adapter/'adapter_model.safetensors')==m['adapter_sha256'];dump(output/'freeze_verification.json',{'unchanged':True,'base_actor_metadata_files':len(before),'adapter_unchanged':True})
 runtime.update(finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved());dump(output/'runtime.json',runtime);(output/'inflight.json').unlink();event('completed')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--adapter',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.inputs,a.base,a.adapter,a.output)
