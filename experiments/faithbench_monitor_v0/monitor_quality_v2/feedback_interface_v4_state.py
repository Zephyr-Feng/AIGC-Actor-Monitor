"""Three new state-only inputs, compared with already saved v3 trajectory inputs."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import feedback_interface_v2 as worker
import feedback_interface_v3 as previous

NAME, ARMS, ORDER_SEED = 'v4_state', ('Q',), 20261023
IDS = ('case_005', 'case_016', 'case_017')
ARM_DESCRIPTIONS = {'Q': '同图像/证据/账本的当前状态；对照复用v3-T'}
SYSTEM, prepared, normalize = previous.SYSTEM, previous.prepared, previous.normalize


def messages(row, arm):
    trail = previous.messages(row, 'T')
    images = [deepcopy(part) for message in trail if isinstance(message['content'], list)
              for part in message['content'] if part.get('type') == 'image']
    state = deepcopy(row['original_action'])
    state.pop('action_reason'); state.pop('evidence_gap')
    for item in state['current_evidence']:
        item.pop('observation'); item.pop('interpretation')
    data = json.loads(trail[-1]['content'])
    data['不可修改的冻结状态'] = state
    content = images + [{'type': 'text', 'text': json.dumps(data, ensure_ascii=False)}]
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': content}]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    if args.prepare:
        worker.make(args.source, args.root, interface=sys.modules[__name__])
    else:
        if not args.run:
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
        worker.run(args.root, args.source, args.run, interface=sys.modules[__name__])
