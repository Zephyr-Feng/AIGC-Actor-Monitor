"""CPU preparation for the approved bounded development comparison."""
import json
from collections import Counter, defaultdict
from pathlib import Path
import random

from fava_trial import readl, score, write

ROOT = Path('data/fava_trial_v1_20261018')
OUT = Path('data/fava_next_stage_20261019')
SYSTEM = ('你是中文审核助手。依据参考文本给出必要的最小编辑，其他内容保持不变。'
          '只输出JSON：{"问题":[{"回答原文":"原句","建议":"替换文本"}]}。'
          '原句必须在回答中唯一出现；删除时建议为空；插入用包含相邻原文的替换表达。'
          '无需编辑时输出{"问题":[]}。不生成字符位置、理由或证据绑定。')


def compact(row):
    answer = json.loads(row['messages'][1]['content'])['待核回答']
    gold = row['target']['问题']
    edits = []
    for g in gold:
        start, end = g['起点'], g['终点']
        assert answer[start:end] == g['回答原文']
        # Use the shortest unique surrounding span inside neighboring edit boundaries.
        left = max((x['终点'] for x in gold if x is not g and x['终点'] <= start), default=0)
        right = min((x['起点'] for x in gold if x is not g and x['起点'] >= end), default=len(answer))
        candidates = []
        for width in range(0, len(answer)+1):
            for extra_left in range(width+1):
                a, b = start-extra_left, end+(width-extra_left)
                if not left <= a <= start <= end <= b <= right or a == b:
                    continue
                quote = answer[a:b]
                if answer.find(quote) == a and answer.find(quote, a+1) < 0:
                    candidates.append((a, b, answer[a:start]+g['建议']+answer[end:b]))
                    break
            if candidates:
                break
        if not candidates:
            return None, 'no_unique_anchor_within_neighbor_bounds'
        a, b, replacement = candidates[0]
        edits.append({'起点': a, '终点': b, '回答原文': answer[a:b], '建议': replacement})
    ordered = sorted(edits, key=lambda i: (i['起点'], i['终点']))
    if any(a['终点'] > b['起点'] for a, b in zip(ordered, ordered[1:])):
        return None, 'expanded_anchors_overlap'
    checked = score(json.dumps({'问题': edits}, ensure_ascii=False), row)
    assert checked['edits_valid'] and checked['exact_author_corrected_answer']
    target = {'问题': [{k: e[k] for k in ('回答原文', '建议')} for e in edits]}
    result = {k: v for k, v in row.items() if k not in ('input_ids', 'prefix_length')}
    result.update(target=target, numeric_target={'问题': edits}, approved_for_training=False,
                  transformation='unique_quote_minimal_surrounding_anchor')
    result['messages'] = [{'role': 'system', 'content': SYSTEM}, row['messages'][1],
                          {'role': 'assistant', 'content': json.dumps(target, ensure_ascii=False)}]
    return result, None


def write_rows(path, rows):
    with path.open('x', encoding='utf8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+'\n')


def main():
    OUT.mkdir(exist_ok=False)
    train = readl(ROOT/'train.sft.jsonl')
    pool = readl(ROOT/'development_pool.sft.jsonl')
    original = readl(ROOT/'final_eval_373_20261019/development_pool.tokens.jsonl')
    assert len(train) == 6184 and len(pool) == 685 and len(original) == 16
    assert not {r['group'] for r in train} & {r['group'] for r in pool}
    converted, rejected = [], []
    for row in train:
        candidate, reason = compact(row)
        if reason:
            rejected.append({'id': row['id'], 'reason': reason})
        else:
            converted.append(candidate)
    write_rows(OUT/'train.compact.candidate.jsonl', converted)
    write_rows(OUT/'train.compact.quarantine.jsonl', rejected)
    selected = [next(r for r in pool if r['id'] == old['id']) for old in original]
    groups = {r['group'] for r in selected}
    buckets = defaultdict(list)
    for row in pool:
        if row['group'] in groups:
            continue
        answer = json.loads(row['messages'][1]['content'])['待核回答']
        edits = row['target']['问题']
        operation = 'insert' if any(not x['回答原文'] for x in edits) else 'delete' if any(not x['建议'] for x in edits) else 'replace'
        bucket = (min(len(answer)//500, 3), min(len(edits), 3), operation)
        buckets[bucket].append(row)
    rng = random.Random(20261019)
    for rows in buckets.values():
        rows.sort(key=lambda r: r['id'])
        rng.shuffle(rows)
    while len(selected) < 128:
        advanced = False
        for key in sorted(buckets):
            while buckets[key]:
                row = buckets[key].pop()
                if row['group'] not in groups:
                    selected.append(row)
                    groups.add(row['group'])
                    advanced = True
                    break
            if len(selected) == 128:
                break
        assert advanced
    write_rows(OUT/'fava.development128.jsonl', selected)
    old = readl(Path('data/monitor_public_v1_20261016/feedback_training_v1_20261017/trained_snapshot_2137/proposed_development.inputs.jsonl'))
    natural = [r for r in old if ':ragtruth:' in r['id']]
    controls = [r for r in old if ':contract:' in r['id']]
    assert len(natural) == 64 and len(controls) == 16
    # Four evenly spaced natural blocks retain known early and late failure cases.
    regression = [natural[i] for block in (0, 16, 32, 48) for i in range(block, block+4)] + controls
    write_rows(OUT/'regression32.jsonl', regression)
    # Candidates only: accepted controls require the separate evidence review.
    clean = []
    for row in selected[:16]:
        material = json.loads(row['messages'][1]['content'])
        material['待核回答'] = row['author_corrected_answer']
        clean.append({**row, 'id': row['id']+':clean_candidate',
                      'messages': [row['messages'][0], {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)},
                                   {'role': 'assistant', 'content': '{"问题":[]}'}],
                      'target': {'问题': []}, 'control_source_id': row['id'],
                      'approved_for_evaluation': False})
    write_rows(OUT/'clean.candidates16.jsonl', clean)
    report = {'seed': 20261019, 'train_original': len(train), 'compact_candidate': len(converted),
              'quarantine': len(rejected), 'quarantine_reasons': dict(Counter(r['reason'] for r in rejected)),
              'development': len(selected), 'original_diagnostic': 16, 'additional_development': 112,
              'development_unique_groups': len(groups), 'regression_rows': len(regression),
              'regression_natural_groups': len({r['group'] for r in regression[:16]}),
              'regression_control_groups': len({r['group'] for r in controls}),
              'clean_candidates': len(clean), 'clean_accepted': 0, 'training_started': False,
              'human_gold': False, 'development_ids': [r['id'] for r in selected],
              'regression_ids': [r['id'] for r in regression],
              'selection': 'original16 then source-unique round robin length/edit-count/operation buckets',
              'independent_test': False}
    write(OUT/'preparation.json', report)
    print(json.dumps({k: v for k, v in report.items() if not k.endswith('_ids')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
