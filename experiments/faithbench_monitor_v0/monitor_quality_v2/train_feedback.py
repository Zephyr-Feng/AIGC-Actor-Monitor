"""One approved feedback epoch, bounded by an absolute deadline."""
import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import time

from assemble_feedback import assemble
from public_helpers import checkpoint,event,loss_for


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def pack(tokenizer,row):
    messages=row['messages'];options=dict(tokenize=True,enable_thinking=False,return_dict=False)
    prefix=tokenizer.apply_chat_template(messages[:-1],add_generation_prompt=True,**options)
    full=tokenizer.apply_chat_template(messages,add_generation_prompt=False,**options)
    assert full[:len(prefix)]==prefix and len(prefix)<len(full)<=4096
    return {'id':row['id'],'group':row['group'],'input_ids':full,'prefix_length':len(prefix)}


def adapter_structure(path):
    file=path/'adapter/adapter_model.safetensors'
    with file.open('rb') as stream:
        size=struct.unpack('<Q',stream.read(8))[0]
        assert 0<size<8*1024*1024
        header=json.loads(stream.read(size))
    offsets=sorted(value['data_offsets'] for key,value in header.items() if key!='__metadata__')
    assert offsets and offsets[0][0]==0 and all(a[1]==b[0] for a,b in zip(offsets,offsets[1:]))
    assert file.stat().st_size==8+size+offsets[-1][1]
    assert (path/'training_state.pt').is_file() and (path/'training_state.pt').stat().st_size>0
    assert json.loads((path/'adapter/adapter_config.json').read_text())['r']==8
    return {'tensor_count':len(offsets),'adapter_bytes':file.stat().st_size,'payload_structure_valid':True}


def evaluate(model,tokenizer,dev,output,phase,deadline,baseline):
    import torch
    model.eval();count=0
    with model.disable_adapter() if baseline else contextlib.nullcontext():
        with (output/f'{phase}.jsonl').open('x',encoding='utf8') as stream:
            for row in dev:
                if time.time()>deadline-90:
                    event('evaluation_deadline',phase=phase,completed=count)
                    return False
                tokens=tokenizer.apply_chat_template(row['messages'],tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)
                assert len(tokens)+1024<=4096
                material=json.loads(row['messages'][1]['content'])
                event('evaluation_start',phase=phase,index=count+1,id=row['id'])
                tick=time.monotonic();x=torch.tensor([tokens],device='cuda')
                with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                    y=model.generate(input_ids=x,attention_mask=torch.ones_like(x),do_sample=False,max_new_tokens=1024,
                        use_cache=True,pad_token_id=tokenizer.pad_token_id,eos_token_id=tokenizer.eos_token_id)
                raw=tokenizer.decode(y[0,x.shape[1]:],skip_special_tokens=True);length=y.shape[1]-x.shape[1]
                try:
                    checked=assemble(material['待核回答'],material['证据卡'],json.loads(raw))
                    valid=checked['source_anchors_verified'];failure=None
                except (ValueError,KeyError,TypeError,IndexError) as exc:
                    valid=False;failure=str(exc)
                result={'id':row['id'],'group':row['group'],'raw':raw,'input_tokens':len(tokens),'output_tokens':length,
                    'hit_token_cap':length==1024,'source_anchors_valid':valid,'validation_failure':failure,
                    'semantic_verified':False,'seconds':time.monotonic()-tick}
                stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush();count+=1
                event('evaluation_end',phase=phase,index=count,id=row['id'],seconds=round(result['seconds'],2),source_anchors_valid=valid)
                del x,y
    event('evaluation_complete',phase=phase,rows=count)
    return count==80


def run(root,base):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_XET='1')
    auth=json.loads((root/'authorization.json').read_text(encoding='utf8'))
    assert auth['approved'] and auth['rows']==7612 and auth['epochs']==1 and auth['generation_limit']==160
    deadline=auth['deadline_epoch'];train_deadline=auth['training_cutoff_epoch']
    assert time.time()<train_deadline<deadline and deadline-auth['start_epoch']==14*3600
    output=root/'run';output.mkdir()
    import torch
    import peft
    import transformers
    from transformers import AutoTokenizer,BitsAndBytesConfig,Qwen3_5ForConditionalGeneration
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    seed=20261017;random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True)
    originals=[json.loads(line) for line in (root/'train_candidate.sft.jsonl').read_text(encoding='utf8').splitlines()]
    dev=[json.loads(line) for line in (root/'proposed_development.inputs.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(originals)==len({r['id'] for r in originals})==7612
    assert len(dev)==len({r['id'] for r in dev})==80
    assert not ({r['group'] for r in originals}&{r['group'] for r in dev})
    train=[pack(tokenizer,row) for row in originals]
    assert sum(len(r['input_ids']) for r in train)==14946187
    assert sum(len(r['input_ids'])-r['prefix_length'] for r in train)==1457070
    order=list(range(len(train)));random.Random(seed).shuffle(order)
    total_updates=math.ceil(len(train)/8);assert total_updates==952
    config={'base':str(base),'initialization':'official_base_new_adapter','rows':7612,'epochs':1,'updates':952,
        'seed':seed,'learning_rate':5e-5,'microbatch':1,'gradient_accumulation':8,'lora_rank':8,'lora_alpha':16,'lora_dropout':.05,
        'generation_cap':1024,'development_rows':80,'context_limit':4096,'thinking':False,'loss':'assistant_token_cross_entropy',
        'transformers':transformers.__version__,'peft':peft.__version__,'torch':torch.__version__,**auth}
    write(output/'config.json',config);event('load_start',pid=os.getpid())
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    model=Qwen3_5ForConditionalGeneration.from_pretrained(base,local_files_only=True,dtype=torch.bfloat16,
        quantization_config=quant,device_map={'':0},attn_implementation='sdpa')
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
    model.get_input_embeddings().to(dtype=torch.bfloat16);model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    targets=r'model\.language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|linear_attn\.(in_proj_qkv|in_proj_z|in_proj_b|in_proj_a|out_proj)|mlp\.(gate_proj|up_proj|down_proj))'
    model=get_peft_model(model,LoraConfig(task_type='CAUSAL_LM',r=8,lora_alpha=16,lora_dropout=.05,target_modules=targets))
    parameters=[(name,p) for name,p in model.named_parameters() if p.requires_grad]
    assert parameters and all('lora_' in name and 'language_model.layers.' in name for name,p in parameters)
    assert len({int(name.split('layers.')[1].split('.')[0]) for name,p in parameters})==32
    write(output/'trainable.json',{'total':sum(p.numel() for name,p in parameters),'parameters':[{'name':n,'shape':list(p.shape)} for n,p in parameters]})
    optimizer=torch.optim.AdamW([p for n,p in parameters],lr=5e-5,weight_decay=.01)
    longest=max(train,key=lambda r:len(r['input_ids']))
    model.train();model.config.use_cache=False
    event('backward_preflight_start',id=longest['id'],tokens=len(longest['input_ids']))
    loss=loss_for(model,longest);assert bool(torch.isfinite(loss));loss.backward()
    assert all(p.grad is None for n,p in model.named_parameters() if not p.requires_grad)
    assert any(p.grad is not None and bool(torch.any(p.grad!=0)) for n,p in parameters)
    assert all(p.grad is None or bool(torch.all(torch.isfinite(p.grad))) for n,p in parameters)
    optimizer.zero_grad(set_to_none=True);del loss
    event('backward_preflight_complete',peak_allocated=torch.cuda.max_memory_allocated())
    before_complete=evaluate(model,tokenizer,dev,output,'before',train_deadline,True)
    assert before_complete,'baseline incomplete; do not train'
    model.train();model.config.use_cache=False
    position=updates=seen_tokens=0;last_save=time.monotonic();owned=[];latest=None

    def save():
        nonlocal latest,last_save
        latest=checkpoint(model,optimizer,output,position,updates,seen_tokens)
        structure=adapter_structure(latest);event('checkpoint_structure',checkpoint=latest.name,**structure)
        owned.append(latest)
        while len(owned)>2:
            old=owned.pop(0)
            assert old.resolve().is_relative_to(output.resolve()) and not old.is_symlink() and old.name.startswith('checkpoint-')
            shutil.rmtree(old)
        last_save=time.monotonic()

    with (output/'training.jsonl').open('x',encoding='utf8') as stream:
        while position<len(order) and time.time()<train_deadline:
            window=[train[i] for i in order[position:position+8]]
            target_tokens=sum(len(r['input_ids'])-r['prefix_length'] for r in window)
            warmup=math.ceil(total_updates*.03)
            scale=min(1.,(updates+1)/warmup) if updates<warmup else .1+.9*.5*(1+math.cos(math.pi*(updates-warmup)/(total_updates-warmup)))
            for group in optimizer.param_groups:group['lr']=5e-5*scale
            optimizer.zero_grad(set_to_none=True);tick=time.monotonic();loss_sum=0.
            event('update_start',update=updates+1,sample=position+1,ids=[r['id'] for r in window])
            for row in window:
                loss=loss_for(model,row,reduction='sum')/target_tokens
                assert bool(torch.isfinite(loss));loss.backward();loss_sum+=float(loss.detach());del loss
                position+=1;seen_tokens+=len(row['input_ids'])
            gradient=torch.nn.utils.clip_grad_norm_([p for n,p in parameters],1.);assert bool(torch.isfinite(gradient))
            optimizer.step();updates+=1
            record={'update':updates,'samples':position,'loss':loss_sum,'grad_norm':float(gradient),'lr':optimizer.param_groups[0]['lr'],
                'seconds':time.monotonic()-tick,'seen_tokens':seen_tokens,'target_tokens':target_tokens,'peak_allocated':torch.cuda.max_memory_allocated()}
            stream.write(json.dumps(record)+'\n');stream.flush();event('update_complete',**record)
            if updates%100==0 or time.monotonic()-last_save>=1800:save()
    if latest is None or json.loads((output/'latest.json').read_text())['position']!=position:save()
    event('training_stopped',samples=position,updates=updates,epoch_complete=position==7612)
    after_complete=evaluate(model,tokenizer,dev,output,'after',deadline,False)
    write(output/'status.json',{'epoch_complete':position==7612,'samples':position,'updates':updates,'checkpoint':str(latest),
        'baseline_complete':before_complete,'after_complete':after_complete,'finished_epoch':time.time(),'deadline_epoch':deadline})
    del model,optimizer;torch.cuda.empty_cache();event('worker_exit',epoch_complete=position==7612,after_complete=after_complete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--base',type=Path,required=True)
    args=parser.parse_args()
    try:run(args.root.resolve(),args.base.resolve())
    except Exception as exc:
        write(args.root/'failure.json',{'error':repr(exc),'time_epoch':time.time()})
        raise
