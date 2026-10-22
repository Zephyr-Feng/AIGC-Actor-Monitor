"""CPU sizing for the proposed, unexecuted 80-case development comparison."""
import argparse
import json
import os
from pathlib import Path


def run(root,base):
    os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(base,local_files_only=True)
    lengths=[]
    for line in (root/'proposed_development.inputs.jsonl').open(encoding='utf8'):
        row=json.loads(line)
        assert [m['role'] for m in row['messages']]==['system','user']
        tokens=tokenizer.apply_chat_template(row['messages'],tokenize=True,add_generation_prompt=True,enable_thinking=False,return_dict=False)
        lengths.append({'id':row['id'],'input_tokens':len(tokens)})
    assert len(lengths)==80
    report={'rows':80,'generation_cap':1024,'inference_context_limit':8192,'max_input_tokens':max(r['input_tokens'] for r in lengths),
        'input_tokens':sum(r['input_tokens'] for r in lengths),'over_context':[r for r in lengths if r['input_tokens']+1024>8192],
        'rows_by_id':lengths,'gpu_used':False,'model_loaded':False,'truncated':False,'approved_for_execution':False}
    with (root/'development_token_preflight.json').open('x',encoding='utf8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='rows_by_id'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--base',type=Path,required=True)
    args=parser.parse_args();run(args.root,args.base)
