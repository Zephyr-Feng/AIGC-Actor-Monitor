"""Six cached, paired proposal ablations; no edits are applied to source actions."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import time

from actor_feedback_bridge import ACTOR_BASE, actor_encoder, event, read, weights_ready
from prepare_feedback_control_run import write

IDS = tuple(f'case_{cid}_{arm}' for cid in ('004', '006', '007') for arm in ('correct', 'false'))
REMOVED = ('Monitor质疑', 'Monitor建议')


def without_feedback(messages):
    result = deepcopy(messages)
    texts = [part for part in result[1]['content'] if part.get('type') == 'text']
    assert len(result) == 2 and len(texts) == 1
    data = json.loads(texts[0]['text'])
    for name in REMOVED:
        del data[name]
    texts[0]['text'] = json.dumps(data, ensure_ascii=False)
    return result


def make(root):
    source = Path('data/feedback_selection_validation_v1_20261020_control')
    calls = [json.loads(line) for line in (source/'actor_calls.jsonl').read_text(encoding='utf8').splitlines()]
    rows = []
    for cid in IDS:
        matches = [c for c in calls if c['id'] == cid and c['issue'] == 1 and c['stage'] == 'proposal']
        assert len(matches) == 1
        prior = matches[0]
        rows.append(dict(id=cid, source=str(source), issue=1, messages=without_feedback(prior['messages']),
                         reference=prior, independent_validation=False, human_gold=False))
    root.mkdir()
    write(root/'inputs.json', rows)
    write(root/'authorization.json', dict(approved=True, user_instruction='2026-10-21继续改进，复用既有结果；零训练',
        ssh_host='connect.bjb1.seetacloud.com', ssh_port=23483, actor_generations=6, monitor_generations=0,
        training_updates=0, new_tool_calls=0, teacher_api_calls=0, no_hash_operations=True,
        source_groups=3, reserved_data_used=False, automatic_application=False))
    print(json.dumps(dict(rows=len(rows), new_generations=6, cached_references=6)))


def run(root, execute):
    import torch
    torch.set_num_threads(2)
    auth = read(root/'authorization.json')
    rows = read(root/'inputs.json')
    assert auth['approved'] and auth['actor_generations'] == len(rows) == 6
    assert [r['id'] for r in rows] == list(IDS)
    assert auth['training_updates'] == auth['new_tool_calls'] == auth['teacher_api_calls'] == 0
    assert all(r['messages'] == without_feedback(r['reference']['messages']) for r in rows)
    processor, encode, limit = actor_encoder(root)
    lengths = [int(encode(r['messages'])['input_ids'].shape[1]) for r in rows]
    report = dict(ids=list(IDS), input_tokens=lengths, max_new_tokens=768, model_files=weights_ready(ACTOR_BASE),
                  context_limit=limit, truncated=False, seed=20261006, do_sample=False, repetition_penalty=1.05)
    if not execute:
        write(root/'actor_preflight.json', report)
        event('ablation_preflight', **report)
        return
    assert read(root/'actor_preflight.json') == report and not (root/'actor_calls.jsonl').exists()
    from transformers import Qwen3VLForConditionalGeneration
    torch.manual_seed(20261006)
    torch.cuda.manual_seed_all(20261006)
    event('ablation_load', pid=os.getpid())
    model = Qwen3VLForConditionalGeneration.from_pretrained(ACTOR_BASE, local_files_only=True,
            dtype=torch.bfloat16, device_map='cuda').eval()
    model.requires_grad_(False)
    assert not any(p.requires_grad for p in model.parameters())
    with (root/'actor_calls.jsonl').open('x', encoding='utf8') as stream:
        for row in rows:
            event('ablation_start', id=row['id'])
            inputs = {k: v.to('cuda') for k, v in encode(row['messages']).items()}
            n = int(inputs['input_ids'].shape[1])
            tick = time.monotonic()
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=768, do_sample=False, repetition_penalty=1.05)
            result = dict(id=row['id'], issue=1, stage='proposal_without_feedback',
                raw=processor.decode(output[0,n:], skip_special_tokens=True), input_tokens=n,
                output_tokens=int(output.shape[1])-n, seconds=time.monotonic()-tick)
            stream.write(json.dumps(result, ensure_ascii=False)+'\n')
            stream.flush()
            event('ablation_end', **{k:v for k,v in result.items() if k!='raw'})
            del inputs, output
    del model
    torch.cuda.empty_cache()
    write(root/'actor_completed.json', dict(completed=True, generations=len(rows), training_updates=0, actions_applied=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    if args.prepare:
        make(args.root)
    else:
        if not args.run:
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
        run(args.root, args.run)
