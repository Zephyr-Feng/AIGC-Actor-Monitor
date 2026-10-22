"""Two source-frozen proposal checks using the existing Monitor runner."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from actor_feedback_bridge import ADAPTER, monitor, read
from prepare_feedback_control_run import write


def make(root):
    base = Path('data/feedback_selection_validation_v1_20261020')
    definitions = [(base.with_name(base.name+'_control'), 'case_006_correct'), (base, 'case_007')]
    rows = []
    for source, cid in definitions:
        records = [json.loads(s) for s in (source/'actor_calls.jsonl').read_text(encoding='utf8').splitlines()]
        call = next(r for r in records if r['id']==cid and r['issue']==1 and r['stage']=='proposal')
        trail = deepcopy(call['messages'])
        assert '你是固定Actor' in trail[0]['content']
        trail[0]['content'] = trail[0]['content'].replace('你是固定Actor', '你是提出修订候选的Monitor', 1)
        text_parts = [p for p in trail[1]['content'] if p.get('type')=='text']
        assert len(text_parts)==1
        trail[1]['content'] = text_parts
        data = json.loads(text_parts[0]['text'])
        source_row = next(r for r in read(source/'inputs.json') if r['id']==cid)
        assert data['当前原文']==source_row['original_action']['action_reason']
        assert data['原始证据']==source_row['cards']
        rows.append(dict(id=cid, messages=trail, existing_actor_candidate=json.loads(call['raw'])['替换文本'],
                         source=str(source), original_full_field=data['当前原文'], human_gold=False))
    assert len(rows)==2
    root.mkdir()
    write(root/'inputs.json', rows)
    write(root/'authorization.json', dict(approved=True, monitor_generations=2, actor_generations=0,
        training_updates=0, teacher_api_calls=0, new_tool_calls=0, source='existing exposed development; candidate feasibility only'))
    print(json.dumps({'rows':2,'maximum_generations':2,'actor_calls':0,'training_updates':0}))


def messages(row):
    return row['messages']


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--prepare',action='store_true');p.add_argument('--run',action='store_true')
    p.add_argument('--base-only',action='store_true');p.add_argument('--adapter',type=Path);args=p.parse_args()
    if args.prepare:
        make(args.root)
    else:
        authorization = read(args.root/'authorization.json')
        assert authorization['approved'] and authorization.get('adapter_enabled',True) == (not args.base_only)
        if args.adapter:
            assert authorization['adapter_path'] == args.adapter.as_posix()
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_XET='1')
        if not args.run:
            os.environ['CUDA_VISIBLE_DEVICES']=''
        monitor(args.root,args.run,selected_rows=read(args.root/'inputs.json'),build_messages=messages,output_limit=768,
                adapter_enabled=not args.base_only,adapter_path=args.adapter or ADAPTER)
