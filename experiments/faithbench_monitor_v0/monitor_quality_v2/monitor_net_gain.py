"""Frozen, paired development review using existing offline model runners."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import time

from actor_feedback_bridge import ACTOR_BASE, actor_encoder, event, monitor, read
from actor_only_baseline import SYSTEM as EDIT_SYSTEM, apply_response
from assemble_feedback import assemble
from prepare_feedback_control_run import write


REVIEW_APPEND = '''
本轮重点是证据与推断是否对应，审核范围内的明确误用必须指出；“不替Actor决定最终真假”不妨碍判定证据误用。先逐字段核对，再输出上述JSON：
一、将每项工具解释及综合推断与真实返回和规则对照。global无真假方向，不能支持真实或合成，也不能与有方向工具形成真假一致或冲突；原稿即使另有一句局限，也不能抵消其他句子的方向误用。
二、同一错误若出现在工具解释、综合理由、缺口中，分别引用受影响原句，明确要求一并修复。保留卡片中确有的local/comp方向及真实冲突，不能因没有像素就撤回Actor视觉描述，不能将未规定的权重/置信度政策判错。
三、区分检查区域数、异常数、top3、检索k和参考库容量；缺失容量列未决，不编数、不借用k或检查数。缺来源不证明伪造。
四、理由说明具体哪条推断违反哪项证据；建议写明撤回/限定什么和保留什么，不用“不能指定真假”代替识错。不要复述全稿，不做文风修改。每个理由和建议各用一句短中文，最多列4项主要问题和2项保留。
'''


def review_messages(row):
    return row['messages']


def valid_feedback(row, raw):
    try:
        payload = json.loads(raw)
        material = json.loads(row['messages'][1]['content'])
        assemble(material['待核回答'], material['证据卡'], payload)
        return payload, None
    except (ValueError, KeyError, TypeError) as exc:
        return None, str(exc)


def edit_messages(row, feedback):
    fields = [dict(字段=i, 路径=r['path'], 原文=row['answer'][r['start']:r['end']])
              for i, r in enumerate(row['regions'], 1)]
    images = [deepcopy(p) for p in row['prefix'][1]['content'] if p.get('type') == 'image']
    data = dict(原始证据=row['cards'], 待核回答=row['answer'], 可修改字段=fields, 外部审核=feedback,
                核查范围='逐项核对反馈和原始证据，可接受、部分接受或拒绝。修复全文中相同证据误用；保留正确事实及真实冲突。只返回需要修订或未决的字段。')
    return [dict(role='system', content=EDIT_SYSTEM),
            dict(role='user', content=images + [dict(type='text', text=json.dumps(data, ensure_ascii=False))])]


def prepare_edits(root):
    reviews = {r['id']: r for r in read(root/'review_rows.json')}
    source = {r['source_id']: r for r in read(root/'natural_rows.json')}
    arms = {'M_current': read(root/'baseline_natural.json')}
    for name in ('M_candidate', 'S_actor'):
        output = root/name/('monitor_outputs.jsonl' if name == 'M_candidate' else 'actor_outputs.jsonl')
        arms[name] = [json.loads(s) for s in output.read_text(encoding='utf8').splitlines()]
    jobs, blocked = [], []
    for cid, row in source.items():
        for name in ('S_actor', 'M_current', 'M_candidate'):
            record = next(r for r in arms[name] if r['id'] == cid+'_native')
            payload, failure = valid_feedback(reviews[record['id']], record['raw'])
            if failure:
                blocked.append(dict(id=cid, arm=name, failure=failure, final_action=row['original_action']))
                continue
            job = deepcopy(row)
            job.update(id=cid+'__'+name, source_id=cid, arm=name, feedback=payload,
                       messages=edit_messages(row, payload))
            jobs.append(job)
    folder = root/'edits'
    folder.mkdir()
    write(folder/'inputs.json', jobs)
    write(folder/'blocked.json', blocked)
    write(folder/'authorization.json', read(root/'authorization.json'))
    event('edits_prepared', planned=len(jobs), blocked=len(blocked))


def actor_phase(root, phase, execute):
    import torch
    torch.set_num_threads(2)
    auth = read(root/'authorization.json')
    assert auth['approved'] and auth['training_updates'] == auth['teacher_api_calls'] == auth['new_tool_calls'] == 0
    rows = read(root/'inputs.json')
    assert len(rows) == len({r['id'] for r in rows})
    processor, encode, limit = actor_encoder(root)
    lengths = [int(encode(r['messages'])['input_ids'].shape[1]) for r in rows]
    report = dict(ids=[r['id'] for r in rows], input_tokens=lengths, max_new_tokens=768,
                  model_path=str(ACTOR_BASE), context_limit=limit, truncated=False, phase=phase)
    if not execute:
        write(root/'actor_preflight.json', report)
        event('actor_preflight', calls=len(rows), maximum_input=max(lengths, default=0))
        return
    assert read(root/'actor_preflight.json') == report
    from transformers import Qwen3VLForConditionalGeneration
    torch.manual_seed(20261006)
    torch.cuda.manual_seed_all(20261006)
    event('actor_load', pid=os.getpid(), phase=phase)
    model = Qwen3VLForConditionalGeneration.from_pretrained(ACTOR_BASE, local_files_only=True,
            dtype=torch.bfloat16, device_map='cuda').eval()
    model.requires_grad_(False)
    with (root/'actor_outputs.jsonl').open('x', encoding='utf8') as stream:
        for row in rows:
            event('actor_start', id=row['id'])
            x = {k:v.to('cuda') for k,v in encode(row['messages']).items()}
            n = int(x['input_ids'].shape[1]); tick = time.monotonic()
            with torch.inference_mode():
                y = model.generate(**x, max_new_tokens=768, do_sample=False, repetition_penalty=1.05)
            raw = processor.decode(y[0,n:], skip_special_tokens=True)
            result = apply_response(row, raw) if phase == 'edit' else None
            item = dict(id=row['id'], raw=raw, input_tokens=n, output_tokens=int(y.shape[1])-n,
                        seconds=time.monotonic()-tick, result=result)
            stream.write(json.dumps(item, ensure_ascii=False)+'\n'); stream.flush()
            event('actor_end', id=row['id'], output_tokens=item['output_tokens'])
            del x, y
    del model
    torch.cuda.empty_cache()
    write(root/'actor_completed.json', dict(completed=True, generations=len(rows), phase=phase))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--phase', choices=('monitor', 'review', 'prepare-edits', 'edit'), required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    if not args.run:
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    if args.phase == 'prepare-edits':
        prepare_edits(args.root)
    elif args.phase == 'monitor':
        auth = read(args.root/'authorization.json')
        assert auth['approved'] and auth['training_updates'] == auth['teacher_api_calls'] == auth['new_tool_calls'] == 0
        monitor(args.root, args.run, selected_rows=read(args.root/'inputs.json'),
                build_messages=review_messages, output_limit=768)
    else:
        actor_phase(args.root, args.phase, args.run)
