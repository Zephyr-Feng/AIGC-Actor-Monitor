"""Existing train-only supervision: compact edits, natural no-error, Chinese replay."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import re

from assemble_feedback import assemble
from build_feedback_candidates import evidence_cards, restore
from fava_trial import readl, write
from prepare_fava_next import SYSTEM, write_rows

OLD = Path('data/monitor_public_v1_20261016')
PREVIOUS = Path('data/fava_next_stage_20261019')
OUT = Path('data/fava_mixed_v1_20261019')
SEED = 20261019


def quality_flag(text):
    if re.search(r',\s*[.!?](?:\s|$)|[.!?]\s+[.!?](?:\s|$)', text):
        return 'orphan_punctuation'
    if re.search(r'\b(the|a|an|and|of|to)\s+\1\b', text, flags=re.I):
        return 'repeated_function_word'
    if re.search(r'\b(?:but|and|or)\s*[.!?](?:\s|$)', text, flags=re.I):
        return 'dangling_conjunction'
    return None


def negative(row, raw):
    assert row['dataset'] == 'ragtruth' and row['split'] == 'train'
    assert row['original_split'] == raw['split'] == 'train'
    assert raw['quality'] == 'good' and isinstance(raw['labels'], list) and raw['labels'] == []
    assert row['target'] == {'判定': '未标注来源忠实性问题', '问题片段': []}
    assert row['input']['待核回答'] == raw['response']
    source = row['input']['原始资料']
    cards = evidence_cards(source, SEED+int(raw['id']))
    assert restore(cards) == source
    # Same text-card shape as FAVA, retaining the source path and literal value.
    cards = [{'id': c['id'], 'text': c['value'] if isinstance(c['value'], str) else json.dumps(c['value'], ensure_ascii=False),
              'original_path': c['path']} for c in cards]
    material = {'证据卡': cards, '待核回答': raw['response']}
    return {'id': 'noerror:'+row['id'], 'group': row['group'], 'task': 'compact_noerror',
            'human_gold': False, 'source_record_id': row['id'], 'source_id': raw['source_id'],
            'supervision': 'original_RAGTruth_good_explicit_empty_labels_not_new_semantic_certification',
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)},
                         {'role': 'assistant', 'content': '{"问题":[]}'}],
            'target': {'问题': []}, 'numeric_target': {'问题': []}, 'author_corrected_answer': raw['response']}


def choose_replay(old, count):
    # Keep all available natural references; fill by status/family and source coverage.
    chosen = [r for r in old if r['id'].startswith('natural_review:')]
    selected = {r['id'] for r in chosen}
    buckets = defaultdict(list)
    rng = random.Random(SEED)
    for row in old:
        if row['id'] in selected:
            continue
        target = json.loads(row['messages'][-1]['content'])
        family = row['id'].split(':')[-2]
        buckets[(target['结论'], family)].append(row)
    for values in buckets.values():
        values.sort(key=lambda r: r['id'])
        rng.shuffle(values)
    group_counts = Counter(r['group'] for r in chosen)
    while len(chosen) < count:
        for key in sorted(buckets):
            values = buckets[key]
            if not values:
                continue
            index = min(range(len(values)), key=lambda i: group_counts[values[i]['group']])
            row = values.pop(index)
            chosen.append(row)
            group_counts[row['group']] += 1
            if len(chosen) == count:
                break
    return [dict(row, task='chinese_feedback_replay', human_gold=False) for row in chosen]


def main():
    OUT.mkdir(exist_ok=False)
    candidates = readl(PREVIOUS/'train.compact.candidate.jsonl')
    positives, quarantine = [], []
    for row in candidates:
        reason = quality_flag(row['author_corrected_answer'])
        if reason:
            quarantine.append({'id': row['id'], 'reason': reason, 'semantic_failure_certified': False})
        else:
            positives.append(dict(row, task='compact_edit', approved_for_this_trial=True))
    write_rows(OUT/'positive.sft.jsonl', positives)
    write_rows(OUT/'positive.quarantine.jsonl', quarantine)
    old = readl(OLD/'feedback_training_v1_20261017/trained_snapshot_2137/train_candidate.sft.jsonl')
    replay = choose_replay(old, 1024)
    for row in replay:
        m = json.loads(row['messages'][1]['content'])
        assemble(m['待核回答'], m['证据卡'], json.loads(row['messages'][-1]['content']))
    write_rows(OUT/'replay1024.sft.jsonl', replay)
    old_development = readl(OLD/'feedback_training_v1_20261017/trained_snapshot_2137/proposed_development.inputs.jsonl')
    held_groups = {r['group'] for r in old_development}
    assert not held_groups & {r['group'] for r in old}
    records = readl(OLD/'built_v3/train.primary.records.jsonl')
    raw = {str(r['id']): r for r in readl(OLD/'raw/ragtruth/response.jsonl')}
    pool = [r for r in records if r['id'].startswith('ragtruth:') and not r['target']['问题片段']
            and r['group'] not in held_groups and not quality_flag(r['input']['待核回答'])]
    rng = random.Random(SEED)
    pool.sort(key=lambda r: r['id'])
    rng.shuffle(pool)
    negatives, groups = [], set()
    for row in pool:
        if row['group'] in groups:
            continue
        original = raw[row['id'].split(':')[1]]
        negatives.append(negative(row, original))
        groups.add(row['group'])
        if len(negatives) == 1024:
            break
    assert len(negatives) == 1024
    write_rows(OUT/'negative.candidates1024.jsonl', negatives)
    evaluation = readl(PREVIOUS/'evaluation.tokens.jsonl')
    adapted = []
    for row in evaluation:
        row = {k: v for k, v in row.items() if k not in ('input_ids', 'prefix_length', 'generation_limit')}
        if row['task'] == 'fava':
            row['numeric_target'] = row['target']
            row['target'] = {'问题': [{k: x[k] for k in ('回答原文', '建议')} for x in row['target']['问题']]}
            row['messages'] = [{'role': 'system', 'content': SYSTEM}, row['messages'][1],
                               {'role': 'assistant', 'content': json.dumps(row['target'], ensure_ascii=False)}]
            row['task'] = 'compact_eval'
        adapted.append(row)
    write_rows(OUT/'evaluation.sft.jsonl', adapted)
    assert not {r['group'] for r in positives+negatives+replay} & {r['group'] for r in adapted}
    summary = {'seed': SEED, 'original_fava_candidates': len(candidates), 'positive_rows': len(positives),
               'positive_quarantine': len(quarantine), 'quality_flags': dict(Counter(r['reason'] for r in quarantine)),
               'negative_candidates': len(negatives), 'negative_final_target': 512,
               'negative_candidate_groups': len(groups), 'replay_rows': len(replay),
               'replay_natural_references': sum(r['id'].startswith('natural_review:') for r in replay),
               'replay_groups': len({r['group'] for r in replay}),
               'replay_statuses': dict(Counter(json.loads(r['messages'][-1]['content'])['结论'] for r in replay)),
               'evaluation_rows': len(adapted), 'groups_disjoint': True, 'human_gold': False,
               'training_started': False, 'negative_selection': '512 context-eligible rows from 1024 ranked unique-source candidates; no truncation',
               'limitations': ['Author no-error labels are not independent gold.', 'Only16 natural Chinese-feedback references over8 groups are available.',
                              'Quality flags are narrow observed-risk heuristics, not complete semantic certification.']}
    write(OUT/'preparation.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
