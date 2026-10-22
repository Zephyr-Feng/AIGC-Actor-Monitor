"""Use the frozen blinded selector to test unknown facts, not program abstention."""
import argparse
import os
from pathlib import Path
import sys

import feedback_interface_v2 as worker
from feedback_selection_v1 import ABSTAIN, original, parse, SYSTEM as OLD_SYSTEM
from selection_unseen_pipeline import prompt

NAME, IDS, ARMS = 'unknown_validation', ('case_004','case_006','case_007'), ('B','R')
SYSTEM = OLD_SYSTEM.replace('原文已经有据且无需纠错时优先保持原文，不为润色选择其他候选。', '')
prepared = worker.prepared


def messages(row, arm):
    trail = prompt(row, prepared(row)['items'][0], row['selection_candidate'], reverse=arm == 'R')
    assert trail[0]['content'] == SYSTEM
    return trail


def normalize(selected, row):
    text = original(row)
    if selected not in (text, row['selection_candidate'], ABSTAIN):
        raise ValueError('output is not an exact candidate or abstention')
    choice = '未决' if selected == ABSTAIN else '拒绝' if selected == text else '接受'
    return {'复核': [{'问题编号':1,'决定':choice,'依据':'身份盲化正文选择，非语义认证',
        '证据ID':[c['id'] for c in row['cards']], '回答原文':text,'替换文本':selected if choice == '接受' else None}]}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--run',action='store_true')
    args = p.parse_args()
    assert worker.read(args.root/'authorization.json')['approved']
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_XET='1')
    if not args.run:
        os.environ['CUDA_VISIBLE_DEVICES']=''
    worker.run(args.root,args.root,args.run,interface=sys.modules[__name__])
