"""Paired Monitor input representation test using the existing source ledger."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import random

from actor_feedback_bridge import monitor, monitor_messages, read
from feedback_interface_v3 import fact_ledger
from prepare_feedback_control_run import write


def make(root):
    rows = read(root/'inputs.json')
    assert [r['id'] for r in rows] == ['case_008','case_009','case_010']
    paired = []
    rng = random.Random(20261021)
    for row in rows:
        plain = monitor_messages(row)
        enriched = deepcopy(plain)
        data = json.loads(enriched[1]['content'])
        ledger = fact_ledger(row['cards'])
        assert any('上下文' in entry and 'used_tools' in entry['上下文'] for entry in ledger)
        data['程序事实账本'] = ledger
        enriched[1]['content'] = json.dumps(data, ensure_ascii=False)
        pair = [dict(id=row['id']+'_plain',source_id=row['id'],arm='plain',messages=plain),
                dict(id=row['id']+'_ledger',source_id=row['id'],arm='ledger',messages=enriched)]
        rng.shuffle(pair)
        paired.extend(pair)
    write(root/'paired_inputs.json', paired)
    write(root/'paired_authorization.json', dict(approved=True, monitor_generations=6, actor_generations=0,
        training_updates=0, new_tool_calls=0, teacher_api_calls=0, monitor_adapter='00373',
        ssh_host='connect.bjb1.seetacloud.com', ssh_port=23483, source_groups=3,
        no_hash_operations=True, human_gold=False, independent_validation=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_XET='1')
    if args.prepare:
        make(args.root)
    else:
        auth=read(args.root/'paired_authorization.json')
        rows=read(args.root/'paired_inputs.json')
        assert auth['approved'] and auth['monitor_generations']==len(rows)==6
        assert auth['training_updates']==auth['new_tool_calls']==auth['teacher_api_calls']==0
        if not args.run:
            os.environ['CUDA_VISIBLE_DEVICES']=''
        monitor(args.root,args.run,selected_rows=rows,build_messages=lambda r:r['messages'],output_limit=768)
