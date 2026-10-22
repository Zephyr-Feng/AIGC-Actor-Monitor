"""One source-disjoint, single-pass Monitor pilot; reuse cached evidence and helpers."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import random
import time

from actor_feedback_bridge import ADAPTER, MONITOR_BASE, event, monitor_messages, read, weights_ready
from feedback_control import prepare
from prepare_feedback_control_run import write
from prepare_selection_unseen import make as make_sources
from public_helpers import checkpoint, loss_for
from train_feedback import pack

TRAIN_IDS = ('case_001','case_002','case_004','case_006','case_007','case_008','case_009','case_010')
DEV_IDS = ('case_011','case_012','case_013')
SEED = 20261021


def controls(row):
    cards=row['cards']
    tools={c['value']['tool']:c for c in cards if 'tool' in c['value']}
    g=tools['global_forensic_analyzer']
    s=next(c for c in cards if c['path']==['task_state'])
    state=s['value']; used=len(state['used_tools']); remaining=state['remaining_calls']
    assert used+remaining==state['max_tool_calls']==4
    directional=next(c for c in tools.values() if c['value'].get('signal') in ('real','real_like','fake','synthetic_like'))
    name=directional['value']['tool']; signal=directional['value']['signal']
    opposite={'real':'fake','fake':'real','real_like':'synthetic_like','synthetic_like':'real_like'}[signal]
    provenance=tools.get('provenance_inspector')
    assert provenance is None or provenance['value']['signal']=='inconclusive'
    prov_quote='来源检查返回inconclusive，缺少可用凭据不能证明图像伪造。' if provenance else '轨迹未调用来源检查工具，没有其实际返回。'
    return [
      ('global_correct','pass','表征偏离只表示与参考库的距离，不能证明图像真假来源。',[g['id'],'E001'],'',''),
      ('budget_correct','pass',f'轨迹记录已调用{used}项工具，剩余{remaining}次调用额度。',[s['id']],'',''),
      ('signal_correct','pass',f'{name}的原始信号为{signal}。',[directional['id']],'',''),
      ('provenance_correct','pass',prov_quote,[provenance['id'] if provenance else s['id'],'E001'],'',''),
      ('global_error','revise','表征偏离已经证明图像由AI生成。',[g['id'],'E001','E002'],'表征距离不是真假方向或来源证明。','撤回来源证明，保留偏离距离及其局限。'),
      ('budget_error','revise',f'轨迹记录已调用{used+1}项工具，剩余{remaining}次调用额度。',[s['id']],f'实际只调用{used}项、剩余{remaining}次，本轮禁新工具不覆盖历史轨迹。',f'改为已用{used}项、剩余{remaining}次，不规定必须继续或停止。'),
      ('signal_error','revise',f'{name}的原始信号为{opposite}。',[directional['id']],f'实际原始signal为{signal}，原句说反了。',f'改为实际信号{signal}，不替Actor指定最终真假。'),
      ('provenance_error','revise','缺少可用来源凭据已经证明图像由AI生成。',['E001','E002'],'缺凭据不能证明伪造，且未调用工具不能补造其返回。','撤回缺凭据定假的推断，保留已知来源局限。'),
      ('library_unknown','uncertain','真实参考库包含1000张图像。',[g['id']],'reference未提供库规模，既不能确认1000，也不能反断不是1000。','待提供参考库规模，不猜其他数字。'),
      ('false_positive_unknown','uncertain','局部纹理模型在这类图像上的假阳性率为1%。',['E001','E002'],'只给可能误报的局限，未给本类图像的假阳性率。','待提供对应评估数据，不猜误报率。'),
      ('weight_unknown','uncertain','最终综合判断应给互补模型70%的权重。',['E001','E002'],'没有冻结模型综合权重政策，不能指定70%或其他值。','待提供权重政策，不替Actor分配综合权重。'),
      ('capture_unknown','uncertain','图像首次拍摄日期为2025年1月1日。',['E001','E002'],'给定材料未提供首次拍摄日期，不能凭取证分数推定日期。','待提供可验证的拍摄记录，不猜日期。')]


def example(row, spec):
    name,status,quote,eids,reason,suggestion=spec
    material={'证据卡':row['cards'],'待核回答':quote,'指定主张':quote,
              '审核范围':'只核该主张与给定资料/明确规则的关系，无像素不判断视觉真假，不新增工具。'}
    payload={'结论':status,'问题':[],'保留':[],'说明':'只核指定主张，保留给定局限，不替Actor选择最终真假。'}
    if status=='pass':payload['保留']=[{'回答原文':quote,'证据ID':eids}]
    else:payload['问题']=[{'状态':'明确错误' if status=='revise' else '未决','回答原文':quote,'证据ID':eids,'理由':reason,'建议':suggestion}]
    p=prepare(quote,row['cards'],payload,controlled=True,allowed_ranges=[(0,len(quote))])
    assert p['status']=={'pass':'retained','revise':'ready','uncertain':'unresolved'}[status]
    return dict(id=row['id']+'_'+name,group=row['id'],task=name,quote=quote,reference_status=status,
        messages=[{'role':'system','content':row['monitor_system']},{'role':'user','content':json.dumps(material,ensure_ascii=False)}],
        target=payload,human_gold=False,construction='explicit source-derived control, not original Actor output')


def build(root):
    make_sources(Path.cwd(),root,ids=TRAIN_IDS+DEV_IDS)
    sources=read(root/'inputs.json'); train=[]; dev=[]
    assert len({r['prefix'][1]['content'][0]['image'] for r in sources})==len(sources)
    for row in sources:
        generated=[example(row,s) for s in controls(row)]
        if row['id'] in TRAIN_IDS:
            for ex in generated:
                ex['messages'].append({'role':'assistant','content':json.dumps(ex['target'],ensure_ascii=False)})
            train.extend(generated)
        else:
            dev.extend(ex for ex in generated if ex['task'] in ('global_error','budget_correct','library_unknown'))
            dev.append(dict(id=row['id']+'_native',group=row['id'],task='native',quote=row['answer'],
                            reference_status=None,messages=monitor_messages(row),target=None,human_gold=False))
    assert len(train)==96 and len(dev)==12
    assert not {r['group'] for r in train}&{r['group'] for r in dev}
    assert Counter(r['reference_status'] for r in train)=={'pass':32,'revise':32,'uncertain':32}
    write(root/'train.json',train);write(root/'development.json',dev)
    write(root/'training_authorization.json',dict(approved=True,user_authorization='2026-10-21 允许，继续进行，下面除非我打断你否则不需要向我再确认了',
        purpose='targeted_monitor_single_pass_v1',train_ids=list(TRAIN_IDS),dev_ids=list(DEV_IDS),
        max_updates=128,max_gpu_seconds=7200,epochs=1,accumulation=8,learning_rate=1e-5,warmup_updates=2,
        planned_updates=12,initial_adapter=ADAPTER.as_posix(),teacher_api_calls=0,new_tool_calls=0,actor_training_updates=0,
        no_hash_operations=True,independent_validation=False,source_groups_verified=False,
        source='existing natural30 cached evidence; source IDs and asset paths disjoint, underlying photo identity not certified',
        license_scope='reuse existing authorized project cache, no new download or external distribution; source image licenses not newly certified'))
    print(json.dumps(dict(train=96,development=12,planned_single_pass_updates=12,classes=dict(Counter(r['reference_status'] for r in train)))))


def preflight(root):
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(MONITOR_BASE,local_files_only=True)
    train=[pack(tokenizer,r) for r in read(root/'train.json')]
    dev=[]
    for row in read(root/'development.json'):
        tokens=tokenizer.apply_chat_template(row['messages'],tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)
        assert len(tokens)+768<=4096
        dev.append(dict(row,input_ids=tokens))
    assert max(len(r['input_ids']) for r in train)<=4096
    write(root/'train.tokens.json',train);write(root/'development.tokens.json',dev)
    write(root/'token_preflight.json',dict(train_rows=len(train),dev_rows=len(dev),max_train=max(len(r['input_ids']) for r in train),
        max_dev=max(len(r['input_ids']) for r in dev),supervised_tokens=sum(len(r['input_ids'])-r['prefix_length'] for r in train),
        base_files=weights_ready(MONITOR_BASE),adapter_files=weights_ready(ADAPTER),truncated=False))
    event('targeted_preflight',**read(root/'token_preflight.json'))


def authorize(auth):
    assert auth['approved'] is True and auth['purpose']=='targeted_monitor_single_pass_v1'
    assert auth['epochs']==1 and auth['max_updates']==128 and auth['max_gpu_seconds']==7200
    assert auth['actor_training_updates']==auth['teacher_api_calls']==auth['new_tool_calls']==0
    assert auth['initial_adapter']==ADAPTER.as_posix() and auth['no_hash_operations'] is True


def run(root):
    import torch
    from transformers import AutoTokenizer,BitsAndBytesConfig,Qwen3_5ForConditionalGeneration
    from peft import PeftModel,prepare_model_for_kbit_training
    auth=read(root/'training_authorization.json');authorize(auth)
    train=read(root/'train.tokens.json');dev=read(root/'development.tokens.json')
    assert len(train)==96 and len(dev)==12 and not {r['group'] for r in train}&{r['group'] for r in dev}
    assert math.ceil(len(train)/auth['accumulation'])==auth['planned_updates']<=auth['max_updates']
    output=root/'run';output.mkdir(exist_ok=False)
    started=time.time();deadline=started+auth['max_gpu_seconds'];cutoff=deadline-600
    write(output/'config.json',dict(auth,start_epoch=started,deadline_epoch=deadline,training_cutoff_epoch=cutoff,seed=SEED))
    torch.set_num_threads(2);random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED)
    tokenizer=AutoTokenizer.from_pretrained(MONITOR_BASE,local_files_only=True)
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
    event('targeted_load',pid=os.getpid())
    model=Qwen3_5ForConditionalGeneration.from_pretrained(MONITOR_BASE,local_files_only=True,dtype=torch.bfloat16,quantization_config=quant,device_map={'':0},attn_implementation='sdpa')
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
    model.get_input_embeddings().to(dtype=torch.bfloat16);model.get_output_embeddings().to(dtype=torch.bfloat16);model.model.visual.to(device='cpu')
    model=PeftModel.from_pretrained(model,ADAPTER,is_trainable=True,local_files_only=True)
    parameters=[(n,p) for n,p in model.named_parameters() if p.requires_grad]
    assert parameters and all('lora_' in n and 'language_model.layers.' in n for n,p in parameters)
    write(output/'trainable.json',dict(parameters=[n for n,p in parameters],count=sum(p.numel() for n,p in parameters)))
    optimizer=torch.optim.AdamW([p for n,p in parameters],lr=auth['learning_rate'],weight_decay=.01)
    def evaluate(phase):
        model.eval();count=0
        with (output/(phase+'.jsonl')).open('x',encoding='utf8') as stream:
            for row in dev:
                assert time.time()<deadline-30,'evaluation deadline reached; do not silently certify partial results'
                x=torch.tensor([row['input_ids']],device='cuda');tick=time.monotonic()
                with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                    y=model.generate(input_ids=x,attention_mask=torch.ones_like(x),max_new_tokens=768,do_sample=False,use_cache=True,
                        pad_token_id=tokenizer.pad_token_id,eos_token_id=tokenizer.eos_token_id)
                raw=tokenizer.decode(y[0,len(row['input_ids']):],skip_special_tokens=True)
                record=dict(id=row['id'],group=row['group'],task=row['task'],reference_status=row['reference_status'],raw=raw,
                    output_tokens=int(y.shape[1])-len(row['input_ids']),seconds=time.monotonic()-tick)
                stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush();count+=1
                event('targeted_evaluation',phase=phase,id=row['id'],tokens=record['output_tokens'])
                del x,y
        return count
    assert evaluate('before')==len(dev)
    model.train();model.config.use_cache=False
    longest=max(train,key=lambda r:len(r['input_ids']));loss=loss_for(model,longest)
    assert bool(torch.isfinite(loss));loss.backward()
    assert any(p.grad is not None and bool(torch.any(p.grad!=0)) for n,p in parameters)
    assert all(p.grad is None or bool(torch.all(torch.isfinite(p.grad))) for n,p in parameters)
    optimizer.zero_grad(set_to_none=True);del loss
    event('targeted_backward_checked',peak_bytes=torch.cuda.max_memory_allocated())
    order=list(range(len(train)));random.Random(SEED).shuffle(order);write(output/'sample_order.json',[train[i]['id'] for i in order])
    position=updates=seen=0
    with (output/'training.jsonl').open('x',encoding='utf8') as stream:
        while position<len(order) and updates<auth['max_updates'] and time.time()<cutoff-180:
            window=[train[i] for i in order[position:position+auth['accumulation']]]
            optimizer.zero_grad(set_to_none=True);tick=time.monotonic();loss_sum=0.
            for group in optimizer.param_groups:group['lr']=auth['learning_rate']*min(1.,(updates+1)/auth['warmup_updates'])
            for row in window:
                loss=loss_for(model,row);assert bool(torch.isfinite(loss))
                (loss/len(window)).backward();loss_sum+=float(loss.detach())/len(window);del loss
            assert all(p.grad is None or bool(torch.all(torch.isfinite(p.grad))) for n,p in parameters)
            norm=torch.nn.utils.clip_grad_norm_([p for n,p in parameters],1.0);assert bool(torch.isfinite(norm))
            optimizer.step();position+=len(window);updates+=1;seen+=sum(len(r['input_ids']) for r in window)
            item=dict(update=updates,position=position,loss=loss_sum,grad_norm=float(norm),seconds=time.monotonic()-tick)
            stream.write(json.dumps(item)+'\n');stream.flush();event('targeted_update',**item)
    saved=checkpoint(model,optimizer,output,position,updates,seen)
    after=evaluate('after')
    write(output/'status.json',dict(completed=True,updates=updates,samples=position,epoch_complete=position==len(train),
        checkpoint=str(saved),before=12,after=after,elapsed_seconds=time.time()-started,deadline_epoch=deadline,actor_training_updates=0))
    del model,optimizer;torch.cuda.empty_cache();event('targeted_complete',updates=updates,after=after)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_XET='1')
    if args.prepare:build(args.root)
    elif args.run:run(args.root)
    else:
        os.environ['CUDA_VISIBLE_DEVICES']='';preflight(args.root)
