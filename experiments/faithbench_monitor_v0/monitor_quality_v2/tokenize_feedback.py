"""CPU-only native-template sizing; never load a model or silently truncate."""
import argparse
import json
import os
from pathlib import Path


def run(root,base):
    os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True)
    lengths=[];answers=[];long=[]
    with (root/'lengths.jsonl').open('x',encoding='utf8') as stream:
        for line in (root/'train_candidate.sft.jsonl').open(encoding='utf8'):
            row=json.loads(line);messages=row['messages']
            assert [m['role'] for m in messages]==['system','user','assistant']
            options=dict(tokenize=True,enable_thinking=False,return_dict=False)
            prefix=tokenizer.apply_chat_template(messages[:-1],add_generation_prompt=True,**options)
            full=tokenizer.apply_chat_template(messages,add_generation_prompt=False,**options)
            assert full[:len(prefix)]==prefix and len(full)>len(prefix)
            item={'id':row['id'],'group':row['group'],'input_tokens':len(prefix),'total_tokens':len(full),'supervised_tokens':len(full)-len(prefix)}
            lengths.append(len(full));answers.append(item['supervised_tokens'])
            if len(full)>4096:long.append(item)
            stream.write(json.dumps(item)+'\n')
            if len(lengths)%1000==0:print(json.dumps({'rows':len(lengths)}),flush=True)
    assert len(lengths)==json.loads((root/'summary.json').read_text(encoding='utf8'))['candidate_rows']
    ordered=sorted(lengths)
    report={'rows':len(lengths),'total_tokens':sum(lengths),'supervised_tokens':sum(answers),
        'p50':ordered[len(ordered)//2],'p95':ordered[int(len(ordered)*.95)],'max':ordered[-1],
        'max_supervised_tokens':max(answers),'over_4096':long,'model_loaded':False,'gpu_visible':False,'truncated':False,
        'native_prefix_matches':True,'ready_for_4096_context':not long,'training_started':False}
    with (root/'token_preflight.json').open('x',encoding='utf8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({**report,'over_4096_count':len(long),'over_4096':long[:5]},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--base',type=Path,required=True)
    args=parser.parse_args();run(args.root,args.base)
