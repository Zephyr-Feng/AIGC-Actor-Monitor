"""Read-only adapter diagnosis. No optimizer, backward, merge or model save."""
import argparse,contextlib,hashlib,json,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/faithbench_monitor_v0/sft_smoke_v1'))
import train_smoke as old
SELECT=['R13_terminal_0005_A006','R13_terminal_0005_A007','R13_terminal_0001_A009','R14_terminal_0002_A006']
def pack(tok,row):
 p=old.tokenize_record(tok,row);target=json.dumps(row['answer'],ensure_ascii=False)
 full=tok.apply_chat_template([{'role':'user','content':row['user_text']},{'role':'assistant','content':target}],tokenize=False,add_generation_prompt=False)
 enc=tok(full,add_special_tokens=False,return_offsets_mapping=True)
 assert enc['input_ids']==p['input_ids'] and full.endswith(target+tok.eos_token+'\n')
 start=len(full)-len(target)-len(tok.eos_token)-1;spans={};decoder=json.JSONDecoder()
 for key in row['answer']:
  pos=target.index(json.dumps(key)+': ')+len(json.dumps(key)+': ');_,end=decoder.raw_decode(target[pos:]);spans[key]=(start+pos,start+pos+end)
 fields=[]
 for begin,end in enc['offset_mapping'][p['prefix_length']:]:
  fields.append(next((k for k,(a,b) in spans.items() if begin<b and end>a),'format'))
 reason=[i for i,k in enumerate(fields) if k=='reason']
 # First lexical reason token: exclude the opening quotation mark itself.
 lexical=next(i for i in reason if enc['offset_mapping'][p['prefix_length']+i][1]>spans['reason'][0]+1)
 return {**p,'fields':fields,'reason_first':lexical}
def run(a):
 from transformers import AutoTokenizer
 old.verify(a.inputs);tok=AutoTokenizer.from_pretrained(a.base,local_files_only=True)
 rows=json.loads((a.inputs/'train.json').read_text(encoding='utf8'));ev=json.loads((a.inputs/'evaluation.json').read_text(encoding='utf8'))
 packed=[pack(tok,r) for r in rows];chosen=[next(r for r in ev if r['id']==name) for name in SELECT]
 assert len(packed)==14 and len(chosen)==4
 a.output.mkdir(parents=True,exist_ok=False)
 old.dump(a.output/'preflight.json',{'records':14,'selected':SELECT,'offsets_exact':True,'mask_exact':True,'max_tokens':max(len(p['input_ids']) for p in packed),'input_manifest_sha256':old.sha(a.inputs/'manifest.json'),'code_sha256':old.sha(Path(__file__)),'plan_sha256':old.sha(Path(__file__).with_name('PLAN_20261010.md'))})
 if a.preflight_only:return
 import torch
 import torch.nn.functional as F
 from transformers import Qwen3VLForConditionalGeneration,BitsAndBytesConfig
 from peft import PeftModel,prepare_model_for_kbit_training
 sft=a.adapter_root;paths={n:sft/d/'adapter' for n,d in [('v1','trial_v1'),('v2','curated_trial_v2')]}
 pinned={'v1':'93775d127ef6420b679534a2cff9ec175228b341b0f50585e4f7d05793ffee8f','v2':'a5f3c0af46900023dffc04b78306565ea9eef3c15b0c4f6879835be47f4b4048'}
 assert all(old.sha(paths[n]/'adapter_model.safetensors')==h for n,h in pinned.items())
 old.event('frozen_before');before=old.frozen_snapshot(a.base);assert before==json.loads((sft/'curated_trial_v2/frozen_after.json').read_text());old.dump(a.output/'frozen_before.json',before)
 torch.manual_seed(42);torch.cuda.manual_seed_all(42)
 q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
 old.event('load_start')
 base=Qwen3VLForConditionalGeneration.from_pretrained(a.base,local_files_only=True,torch_dtype=torch.bfloat16,quantization_config=q,device_map={'':0},attn_implementation='sdpa')
 base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
 model=PeftModel.from_pretrained(base,paths['v1'],adapter_name='v1',is_trainable=False);model.load_adapter(paths['v2'],adapter_name='v2',is_trainable=False)
 model.eval();model.config.use_cache=False
 assert not any(p.requires_grad for p in model.parameters())
 old.event('load_end',allocated=torch.cuda.memory_allocated())
 def precision(enabled):return torch.autocast('cuda',dtype=torch.bfloat16) if enabled else contextlib.nullcontext()
 nf=(a.output/'nll.jsonl').open('x',encoding='utf8');gf=(a.output/'generations.jsonl').open('x',encoding='utf8');dtype_log=[]
 prior={'base':sft/'trial_v1/before.jsonl','v1':sft/'trial_v1/after.jsonl','v2':sft/'curated_trial_v2/after.jsonl'}
 previous={n:{r['id']:r['raw'] for r in [json.loads(s) for s in f.read_text().splitlines()]} for n,f in prior.items()}
 start=time.monotonic()
 for state in ['base','v1','v2']:
  model.set_adapter('v1' if state=='base' else state)
  # set_adapter enables training flags in PEFT; freeze again for this diagnosis.
  for param in model.parameters():param.requires_grad_(False)
  model.eval()
  for auto in [False,True]:
   old.event('condition_start',state=state,autocast=auto)
   with (model.disable_adapter() if state=='base' else contextlib.nullcontext()),torch.inference_mode():
    captured={};hooks=[]
    for name,module in model.named_modules():
     if name.endswith('embed_tokens') or name.endswith('lm_head') or name.endswith('layers.0.self_attn.q_proj.base_layer') or name.endswith('layers.0.self_attn.q_proj.lora_A.'+('v1' if state=='base' else state)):
      def hook(mod,ins,out,name=name):
       if name not in captured:captured[name]={'input':str(ins[0].dtype),'output':str(out.dtype)}
      hooks.append(module.register_forward_hook(hook))
    for index,p in enumerate(packed,1):
     old.event('forward_start',state=state,autocast=auto,index=index,id=p['id']);x=torch.tensor([p['input_ids']],device='cuda')
     with precision(auto):out=model(input_ids=x,attention_mask=torch.ones_like(x),use_cache=False)
     prefix=p['prefix_length'];logits=out.logits[0,prefix-1:-1].float();target=x[0,prefix:];loss=F.cross_entropy(logits,target,reduction='none');assert bool(torch.isfinite(loss).all())
     stats={k:{'tokens':sum(z==k for z in p['fields']),'nll':float(loss[torch.tensor([z==k for z in p['fields']],device='cuda')].mean())} for k in set(p['fields'])}
     j=p['reason_first'];probs=logits[j].log_softmax(-1);vals,ids=probs.topk(8)
     rec={'state':state,'bf16_autocast':auto,'id':p['id'],'nll':float(loss.mean()),'fields':stats,'reason_first_target':tok.decode([int(target[j])]),'reason_first_target_logprob':float(probs[target[j]]),'reason_first_top8':[{'token':tok.decode([int(t)]),'logprob':float(v)} for t,v in zip(ids,vals)]}
     nf.write(json.dumps(rec,ensure_ascii=False)+'\n');nf.flush();old.event('forward_end',state=state,autocast=auto,index=index,nll=rec['nll'])
     del out,logits,target,loss,probs,x
    for h in hooks:h.remove()
    dtype_log.append({'state':state,'bf16_autocast':auto,'modules':captured})
    for index,r in enumerate(chosen,1):
     old.event('generation_start',state=state,autocast=auto,index=index,id=r['id']);ids=tok.apply_chat_template([{'role':'user','content':r['user_text']}],tokenize=True,add_generation_prompt=True);x=torch.tensor([ids],device='cuda');t=time.monotonic()
     with precision(auto):out=model.generate(input_ids=x,attention_mask=torch.ones_like(x),do_sample=False,max_new_tokens=384,pad_token_id=tok.pad_token_id,eos_token_id=tok.eos_token_id,use_cache=True)
     raw=tok.decode(out[0,len(ids):],skip_special_tokens=True);rec={'state':state,'bf16_autocast':auto,'id':r['id'],'raw':raw,'seconds':round(time.monotonic()-t,4),'tokens':out.shape[1]-len(ids),'original_path_raw_equal':raw==previous[state][r['id']] if not auto else None}
     gf.write(json.dumps(rec,ensure_ascii=False)+'\n');gf.flush();old.event('generation_end',state=state,autocast=auto,index=index,equal=rec['original_path_raw_equal'],seconds=rec['seconds'])
     del out,x
    if not auto:
     gf.flush();done=[json.loads(s) for s in (a.output/'generations.jsonl').read_text().splitlines()]
     if any(r['original_path_raw_equal'] is False for r in done):raise RuntimeError('original path failed reproduction; inspect reload/state before proceeding')
 nf.close();gf.close();old.dump(a.output/'dtypes.json',dtype_log)
 assert not any(p.requires_grad or p.grad is not None for p in model.parameters())
 peak=torch.cuda.max_memory_allocated();del model,base;torch.cuda.empty_cache()
 after=old.frozen_snapshot(a.base);assert before==after and all(old.sha(paths[n]/'adapter_model.safetensors')==h for n,h in pinned.items())
 old.dump(a.output/'frozen_after.json',after);old.dump(a.output/'completed.json',{'seconds':time.monotonic()-start,'forwards':84,'generations':24,'optimizer_steps':0,'frozen_unchanged':True,'adapter_unchanged':True,'peak_allocated':peak,'gold':False,'independent_test':False});old.event('completed')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--adapter-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');run(p.parse_args())
