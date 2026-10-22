"""Frozen native feedback -> local candidate -> exact text selection with order check."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import random
import time

from actor_feedback_bridge import ACTOR_BASE, actor_encoder, event, monitor, read
from feedback_control import apply_decisions, prepare
from feedback_interface_v3 import explicit_labels
from feedback_selection_v1 import ABSTAIN, SYSTEM as SELECTION_SYSTEM, reconcile_choices
from prepare_feedback_control_run import apply_to_action, write

IDS = ('case_001', 'case_002', 'case_003')
PROPOSE_SYSTEM = '''你是固定Actor，依据原始证据为一个指定片段提出一份最小修订候选。Monitor可能错误，不要照抄其理由或编造事实。原句有据且无须修改时可原样返回；证据不足不靠删除逃避。保留真实工具信号、冲突和必要局限。不改变最终真假、置信度、direction或动作，不调用工具。
只输出一个JSON对象：{"替换文本":"该片段的完整候选文本"}。仅修改指定片段，不重复原稿其他段落，不输出判定标签或理由。'''


def rows(root):
    data = read(root/'inputs.json')
    assert [r['id'] for r in data] == read(root/'authorization.json').get('frozen_ids', list(IDS))
    assert data and len({r['id'] for r in data}) == len(data)
    return data


def preparations(root):
    outputs = [json.loads(x) for x in (root/'monitor_outputs.jsonl').read_text(encoding='utf8').splitlines()]
    source = rows(root)
    assert len(outputs) == len(source) and {r['id'] for r in outputs} == {r['id'] for r in source}
    cached = {r['id']: r for r in outputs}
    result = []
    for row in source:
        try:
            payload = json.loads(cached[row['id']]['raw'])
        except ValueError:
            payload = None
        p = prepare(row['answer'], row['cards'], payload, controlled=True,
                    allowed_ranges=[(r['start'], r['end']) for r in row['regions']])
        result.append((row, p))
    return result


def prompt(row, item, candidate=None, reverse=False):
    images = deepcopy(row['prefix'][1]['content'])
    quote = item['回答原文']
    data = {'原始证据': row['cards'], '当前原文': quote,
            '核查范围': '只核对这段文字的证据归因、对象、数量和不确定性，不改固定标签或请求新工具。'}
    if candidate is None:
        data.update(待核回答=row['answer'], Monitor质疑=item['理由'], Monitor建议=item['建议'])
        system = PROPOSE_SYSTEM
    else:
        choices = [quote, candidate]
        seed = row.get('selection_order_seed')
        if seed is None:
            seed = 20261026 + IDS.index(row['id'])*100
        random.Random(seed + item['number']).shuffle(choices)
        if reverse:
            choices.reverse()
        data['候选正文'] = choices
        system = SELECTION_SYSTEM
        if row.get('selection_identity_blind'):
            del data['当前原文']
            system = system.replace('原文已经有据且无需纠错时优先保持原文，不为润色选择其他候选。', '')
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': images + [
        {'type': 'text', 'text': json.dumps(data, ensure_ascii=False)}]}]


def candidate_boundary_failure(row, item, candidate):
    quote = item['回答原文']
    for region in row['regions']:
        field = row['answer'][region['start']:region['end']]
        if quote != field and quote in field and field in candidate:
            return 'whole_existing_field_copied_into_subspan'
    return None


def actor(root, execute):
    import torch
    torch.set_num_threads(2)
    packets = preparations(root)
    processor, encode, _ = actor_encoder(root)
    lengths = []
    for row, p in packets:
        for item in p['items']:
            if item['route'] == 'review':
                for stage, trail in [('proposal', prompt(row, item)), ('selection_original_placeholder', prompt(row, item, item['回答原文']))]:
                    lengths.append(dict(id=row['id'], issue=item['number'], stage=stage, tokens=int(encode(trail)['input_ids'].shape[1])))
    report = dict(cases=[dict(id=r['id'], status=p['status'], review_items=sum(x['route']=='review' for x in p['items'])) for r, p in packets],
                  lengths=lengths, output_limit=768, selection_candidate_lengths_checked_at_runtime=True, truncated=False,
                  execution_guards='symmetric_order;no_whole_field_copy_into_subspan;unchanged_candidate_unresolved')
    if not execute:
        write(root/'actor_preflight.json', report); print(json.dumps(report, ensure_ascii=False)); return
    assert read(root/'actor_preflight.json') == report and not (root/'case_results.jsonl').exists()
    if not lengths:
        with (root/'actor_calls.jsonl').open('x', encoding='utf8'), (root/'case_results.jsonl').open('x', encoding='utf8') as outputs:
            for row, p in packets:
                outputs.write(json.dumps(dict(id=row['id'], prepared=p, details=[], result=apply_decisions(p, None),
                    blocked_candidate=None, candidate_action=row['original_action']), ensure_ascii=False)+'\n')
        write(root/'actor_completed.json', dict(completed=True, cases=len(packets), generations=0, training_updates=0, model_loaded=False))
        return
    from transformers import Qwen3VLForConditionalGeneration
    torch.manual_seed(20261006); torch.cuda.manual_seed_all(20261006)
    event('candidate_pipeline_load', pid=os.getpid())
    model = Qwen3VLForConditionalGeneration.from_pretrained(ACTOR_BASE, local_files_only=True, dtype=torch.bfloat16, device_map='cuda').eval()
    model.requires_grad_(False); count = 0
    with (root/'actor_calls.jsonl').open('x', encoding='utf8') as calls, (root/'case_results.jsonl').open('x', encoding='utf8') as outputs:
        def generate(row, item, stage, trail):
            nonlocal count
            event('pipeline_call_start', id=row['id'], issue=item['number'], stage=stage, call=count+1)
            inputs = {k: v.to('cuda') for k, v in encode(trail).items()}
            n = int(inputs['input_ids'].shape[1]); tick = time.monotonic()
            with torch.inference_mode():
                y = model.generate(**inputs, max_new_tokens=768, do_sample=False, repetition_penalty=1.05)
            raw = processor.decode(y[0, n:], skip_special_tokens=True); count += 1
            record = dict(id=row['id'], issue=item['number'], stage=stage, raw=raw, messages=trail,
                          input_tokens=n, output_tokens=int(y.shape[1])-n, seconds=time.monotonic()-tick)
            calls.write(json.dumps(record, ensure_ascii=False)+'\n'); calls.flush()
            event('pipeline_call_end', id=row['id'], stage=stage, call=count, output_tokens=record['output_tokens'])
            del inputs, y
            return raw
        for row, p in packets:
            decisions, details = [], []
            for item in p['items']:
                if item['route'] != 'review':
                    continue
                quote = item['回答原文']; decision, replacement, reason = '未决', None, '候选接口失败或证据不足'
                detail = dict(issue=item['number'], candidate=None, choices=[], failure=None)
                raw = generate(row, item, 'proposal', prompt(row, item))
                try:
                    proposed = json.loads(raw)
                    if not isinstance(proposed, dict) or set(proposed) != {'替换文本'} or not isinstance(proposed['替换文本'], str):
                        raise ValueError('invalid single replacement candidate')
                    candidate = proposed['替换文本']; detail['candidate'] = candidate
                    boundary_failure = candidate_boundary_failure(row, item, candidate)
                    if candidate == quote or candidate.strip() == quote.strip():
                        reason = '未提出变更，不增加相同候选选择调用；原文未获事实认证'
                    elif not candidate.strip():
                        detail['failure'] = 'empty_candidate_not_selectable'; reason = '空候选不能通过正文复制选择，保留未决'
                    elif boundary_failure:
                        detail['failure'] = boundary_failure
                        reason = '局部替换复制了完整旧字段，可能重复拼接；不执行'
                    else:
                        selected = generate(row, item, 'selection', prompt(row, item, candidate)).strip()
                        detail['choices'].append(selected)
                        if selected in (quote, candidate):
                            again = generate(row, item, 'selection_reversed', prompt(row, item, candidate, reverse=True)).strip()
                            detail['choices'].append(again)
                        decision, replacement, reason = reconcile_choices(detail['choices'], quote, candidate)
                        if any(x not in (quote, candidate, ABSTAIN) for x in detail['choices']):
                            detail['failure'] = 'selection_not_exact_candidate'
                except (ValueError, KeyError, TypeError) as exc:
                    detail['failure'] = str(exc)
                decisions.append({'问题编号':item['number'], '决定':decision, '依据':reason, '证据ID':[c['id'] for c in row['cards']],
                                  '回答原文':quote, '替换文本':replacement})
                details.append(detail)
            result = apply_decisions(p, {'复核': decisions} if p['status'] == 'ready' else None)
            blocked = None
            if explicit_labels(result['answer']) != explicit_labels(row['answer']):
                blocked = result
                result = apply_decisions(p, None); result['failure'] = 'explicit_terminal_change_outside_scope'
            record = dict(id=row['id'], prepared=p, details=details, result=result, blocked_candidate=blocked,
                          candidate_action=apply_to_action(row['original_action'], row['regions'], result['edits']))
            outputs.write(json.dumps(record, ensure_ascii=False)+'\n'); outputs.flush()
            event('pipeline_case_complete', id=row['id'], status=result['status'], calls=count)
    del model; torch.cuda.empty_cache()
    write(root/'actor_completed.json', dict(completed=True, cases=len(packets), generations=count, training_updates=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--phase', choices=('monitor','actor'), required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    assert read(args.root/'authorization.json')['approved']
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    if not args.run:
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    if args.phase == 'monitor':
        monitor(args.root, args.run, selected_rows=rows(args.root))
    else:
        actor(args.root, args.run)
