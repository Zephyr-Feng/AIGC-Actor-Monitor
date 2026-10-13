"""Bounded text-only Monitor QLoRA trial; assistant-only loss, immutable base files."""
import argparse,json,hashlib,time,random,sys,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/pilot_v3'))
from prepare_reasoned_portable import dump
import single_source as single
def event(name,**fields):print(json.dumps({'event':name,'at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),**fields}),flush=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def verify(inputs):
 m=json.loads((inputs/'manifest.json').read_text(encoding='utf8'))
 for n,h in m['artifact_hashes'].items():
  if sha(inputs/n)!=h:raise ValueError('input changed '+n)
 for n,h in m['protocol_hashes'].items():
  if sha(ROOT/n)!=h:raise ValueError('protocol changed '+n)
 return m
def tokenize_record(tokenizer,row):
 messages=[{'role':'user','content':row['user_text']}]
 prefix=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
 full=tokenizer.apply_chat_template(messages+[{'role':'assistant','content':json.dumps(row['answer'],ensure_ascii=False)}],tokenize=True,add_generation_prompt=False)
 if full[:len(prefix)]!=prefix or len(full)<=len(prefix):raise ValueError('chat prefix mismatch '+row['id'])
 if len(full)>4096:raise ValueError('do not truncate '+row['id'])
 labels=[-100]*len(prefix)+full[len(prefix):]
 if any(v!=-100 for v in labels[:len(prefix)]) or labels[len(prefix):]!=full[len(prefix):]:raise ValueError('loss mask mismatch')
 return {'input_ids':full,'labels':labels,'prefix_length':len(prefix),'assistant_tokens':len(full)-len(prefix),'id':row['id']}
def cpu_preflight(inputs,base,output):
 from transformers import AutoTokenizer
 verify(inputs);output.mkdir(parents=True,exist_ok=False);tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True)
 train=json.loads((inputs/'train.json').read_text(encoding='utf8'));evaluation=json.loads((inputs/'evaluation.json').read_text(encoding='utf8'))
 packed=[tokenize_record(tokenizer,x) for x in train]
 lengths=[]
 for x in evaluation:
  prefix=tokenizer.apply_chat_template([{'role':'user','content':x['user_text']}],tokenize=True,add_generation_prompt=True)
  if len(prefix)+384>4096:raise ValueError('evaluation overflow')
  lengths.append({'id':x['id'],'input_tokens':len(prefix),'scope':x['evaluation_scope']})
 report={'training_records':len(packed),'evaluation_records':len(lengths),'max_training_tokens':max(len(x['input_ids']) for x in packed),'total_assistant_tokens':sum(x['assistant_tokens'] for x in packed),'mask_verified':True,'truncated':False,'model_loaded':False,'training':[{'id':x['id'],'tokens':len(x['input_ids']),'prefix_tokens':x['prefix_length'],'assistant_tokens':x['assistant_tokens']} for x in packed],'evaluation':lengths}
 dump(output/'cpu_preflight.json',report);event('cpu_preflight',**{k:v for k,v in report.items() if k not in ['training','evaluation']});return tokenizer,packed
def frozen_snapshot(base):
 actor=Path('/root/autodl-tmp/mini-faithbench-v0/actor-venv');files=list(base.glob('*'))+[actor/'pyvenv.cfg']+list((actor/'lib/python3.12/site-packages').glob('*.dist-info/METADATA'))
 values={}
 for p in sorted(files):
  if not p.is_file():continue
  values[str(p)]={'size':p.stat().st_size,'sha256':sha(p)}
  if p.suffix=='.safetensors':event('base_shard_hashed',file=p.name,bytes=p.stat().st_size)
 return values
def evaluate(model,tokenizer,rows,phase,output):
 import torch
 model.eval();dest=output/(phase+'.jsonl')
 with dest.open('x',encoding='utf8') as h:
  for index,row in enumerate(rows,1):
   event('evaluation_start',phase=phase,index=index,id=row['id']);dump(output/'inflight.json',{'phase':phase,'index':index,'id':row['id'],'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')});start=time.monotonic()
   ids=tokenizer.apply_chat_template([{'role':'user','content':row['user_text']}],tokenize=True,add_generation_prompt=True);t=torch.tensor([ids],device='cuda')
   with torch.inference_mode():result=model.generate(input_ids=t,attention_mask=torch.ones_like(t),do_sample=False,max_new_tokens=384,pad_token_id=tokenizer.pad_token_id,eos_token_id=tokenizer.eos_token_id,use_cache=True)
   raw=tokenizer.decode(result[0,len(ids):],skip_special_tokens=True);record={'id':row['id'],'phase':phase,'scope':row['evaluation_scope'],'raw':raw,'seconds':round(time.monotonic()-start,4),'input_tokens':len(ids),'output_tokens':result.shape[1]-len(ids),'max_new_tokens':384}
   try:
    data=json.loads(row['user_text'].split('\n待审核数据：\n',1)[1]);parsed=single.parse(raw,data);record.update(parsed,parse_valid=True,status_matches_provisional_target=parsed['status']==row['answer']['status'])
   except (ValueError,TypeError,KeyError) as e:record.update(parse_valid=False,parse_error=type(e).__name__+': '+str(e))
   h.write(json.dumps(record,ensure_ascii=False)+'\n');h.flush();event('evaluation_end',phase=phase,index=index,valid=record['parse_valid'],seconds=record['seconds'])
   del result,t
def run(inputs,base,output):
 import torch
 from transformers import Qwen3VLForConditionalGeneration,BitsAndBytesConfig
 from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
 if output.resolve().is_relative_to(base.resolve()) or base.resolve().is_relative_to(output.resolve()):raise ValueError('base/output overlap')
 output.mkdir(parents=True,exist_ok=False);verify(inputs);random.seed(42);torch.manual_seed(42);torch.cuda.manual_seed_all(42)
 event('frozen_snapshot_before');before=frozen_snapshot(base);dump(output/'frozen_before.json',before)
 from transformers import AutoTokenizer
 tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True);train=json.loads((inputs/'train.json').read_text(encoding='utf8'));evaluations=json.loads((inputs/'evaluation.json').read_text(encoding='utf8'));packed=[tokenize_record(tokenizer,x) for x in train]
 runtime={'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'inputs_sha256':sha(inputs/'manifest.json'),'base':str(base),'quantization':'NF4_double_bf16','steps':20,'batch_size':1,'gradient_accumulation':1,'learning_rate':2e-4,'lora_r':8,'lora_alpha':16,'lora_dropout':0.05,'target_modules':['q_proj','v_proj'],'max_training_sequence':4096,'max_evaluation_new_tokens':384,'seed':42,'independent_test':False,'gold':False,'actor_actions_executed':False}
 dump(output/'runtime.json',runtime);event('load_start');torch.cuda.reset_peak_memory_stats()
 quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
 model=Qwen3VLForConditionalGeneration.from_pretrained(base,local_files_only=True,torch_dtype=torch.bfloat16,quantization_config=quant,device_map={'':0},attn_implementation='sdpa')
 model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
 model=get_peft_model(model,LoraConfig(task_type='CAUSAL_LM',r=8,lora_alpha=16,lora_dropout=0.05,target_modules=['q_proj','v_proj']))
 trainable=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
 if not trainable or any('lora_' not in n or 'language_model' not in n for n,p in trainable):raise ValueError('non-language-adapter parameter trainable')
 dump(output/'trainable_parameters.json',{'parameters':[{'name':n,'shape':list(p.shape),'numel':p.numel()} for n,p in trainable],'total':sum(p.numel() for n,p in trainable)})
 event('load_end',trainable_parameters=sum(p.numel() for n,p in trainable),allocated_bytes=torch.cuda.memory_allocated())
 with model.disable_adapter():evaluate(model,tokenizer,evaluations,'before',output)
 model.train();model.config.use_cache=False;optimizer=torch.optim.AdamW([p for n,p in trainable],lr=2e-4);order=list(range(len(packed)));random.Random(42).shuffle(order)
 with (output/'training.jsonl').open('x',encoding='utf8') as h:
  for step in range(1,21):
   row=packed[order[(step-1)%len(order)]];event('training_start',step=step,id=row['id']);dump(output/'inflight.json',{'phase':'training','step':step,'id':row['id'],'at':time.strftime('%Y-%m-%dT%H:%M:%S%z')});start=time.monotonic()
   x=torch.tensor([row['input_ids']],device='cuda');labels=torch.tensor([row['labels']],device='cuda');optimizer.zero_grad(set_to_none=True)
   with torch.autocast('cuda',dtype=torch.bfloat16):result=model(input_ids=x,attention_mask=torch.ones_like(x),labels=labels,use_cache=False);loss=result.loss
   if not torch.isfinite(loss):raise ValueError('nonfinite loss')
   loss.backward();grad=torch.nn.utils.clip_grad_norm_([p for n,p in trainable],1.0)
   if not torch.isfinite(grad):raise ValueError('nonfinite gradient')
   if any(p.grad is not None for n,p in model.named_parameters() if not p.requires_grad):raise ValueError('frozen parameter received gradient')
   optimizer.step();record={'step':step,'id':row['id'],'loss':float(loss.detach()),'grad_norm':float(grad),'seconds':round(time.monotonic()-start,4),'allocated_bytes':torch.cuda.memory_allocated(),'peak_allocated_bytes':torch.cuda.max_memory_allocated()};h.write(json.dumps(record)+'\n');h.flush();event('training_end',**record)
   del result,loss,x,labels
 adapter=output/'adapter';model.save_pretrained(adapter,safe_serialization=True);event('adapter_saved')
 evaluate(model,tokenizer,evaluations,'after',output);runtime.update(finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved());dump(output/'runtime.json',runtime)
 del model,optimizer;torch.cuda.empty_cache();event('frozen_snapshot_after');after=frozen_snapshot(base);dump(output/'frozen_after.json',after)
 if before!=after:raise ValueError('base or Actor environment files changed')
 dump(output/'freeze_verification.json',{'unchanged':True,'files':len(before),'actor_base_modified':False});(output/'inflight.json').unlink();event('completed',peak_allocated_bytes=runtime['peak_allocated_bytes'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
 if a.preflight_only:cpu_preflight(a.inputs,a.base,a.output)
 else:run(a.inputs,a.base,a.output)
