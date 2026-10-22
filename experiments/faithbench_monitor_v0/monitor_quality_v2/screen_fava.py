"""Screen existing FAVA edits and group shared text; no split allocation."""
import argparse
from collections import Counter
import json
from pathlib import Path


def normalized(text):
    return ' '.join(text.split())


def source_groups(rows):
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # Compare sorted text directly, without content digests.
    keys = []
    for i, r in enumerate(rows):
        keys.append(('answer', normalized(r['input']['待核回答']), i))
        keys.extend(('reference', normalized(c['text']), i) for c in r['input']['证据卡'])
    keys.sort()
    previous = None
    for kind, text, i in keys:
        if not text:
            continue
        if previous is not None and (kind, text) == previous[:2]:
            a, b = find(previous[2]), find(i)
            parent[max(a, b)] = min(a, b)
        previous = (kind, text, i)
    names = {r: f'fava:g{n:06d}' for n, r in enumerate(sorted({find(i) for i in range(len(rows))}), 1)}
    return [names[find(i)] for i in range(len(rows))]


def assess(row):
    answer = row['input']['待核回答']
    target = row['supervision']['corrected_answer']
    issues = row['supervision']['issues']
    if not issues or not all(i['explicit_edit'] for i in issues) or target is None:
        return 'partial_supervision', None
    if not normalized(answer) or not normalized(target):
        return 'empty_input_or_target', None
    if any(normalized(i['quote']) == normalized(i['replacement']) for i in issues):
        return 'contains_no_effective_edit', None
    if normalized(answer) == normalized(target):
        return 'no_effective_target_change', None
    cursor = 0
    for issue in issues:
        a, b = issue['start'], issue['end']
        if not 0 <= cursor <= a <= b <= len(answer) or answer[a:b] != issue['quote']:
            raise ValueError('invalid_edit_anchor')
        cursor = b
    edited = answer
    for i in reversed(issues):
        edited = edited[:i['start']] + i['replacement'] + edited[i['end']:]
    if edited != target:
        raise ValueError('edit_replay_mismatch')
    ratio = sum(max(len(i['quote']), len(i['replacement'])) for i in issues) / len(answer)
    return ('broad_edit_review' if ratio > 0.5 else 'candidate'), ratio


def duplicate_decisions(rows):
    keyed = []
    for i, r in enumerate(rows):
        if not r['supervision']['all_flagged_issues_have_explicit_edits']:
            continue
        key = (tuple(sorted(normalized(c['text']) for c in r['input']['证据卡'])), r['input']['待核回答'])
        signature = json.dumps(r['supervision'], sort_keys=True, ensure_ascii=False)
        keyed.append((key, signature, i))
    keyed.sort()
    decisions = {}
    a = 0
    while a < len(keyed):
        b = a + 1
        while b < len(keyed) and keyed[b][0] == keyed[a][0]:
            b += 1
        block = keyed[a:b]
        if any(x[1] != block[0][1] for x in block):
            decisions.update((x[2], 'conflicting_annotation') for x in block)
        else:
            decisions.update((x[2], 'duplicate_input_and_annotation') for x in sorted(block, key=lambda x: x[2])[1:])
        a = b
    return decisions


def run(source, output):
    with source.open(encoding='utf8') as f:
        rows = [json.loads(line) for line in f]
    groups, duplicates = source_groups(rows), duplicate_decisions(rows)
    output.mkdir(exist_ok=False)
    counts, sizes, candidate_groups, types = Counter(), Counter(groups), Counter(), Counter()
    samples, covered, operations = [], set(), set()
    with (output / 'candidates.jsonl').open('x', encoding='utf8') as good, (output / 'screening_index.jsonl').open('x', encoding='utf8') as idx, (output / 'needs_review.jsonl').open('x', encoding='utf8') as pending:
        for n, r in enumerate(rows):
            reason, ratio = assess(r)
            reason = duplicates.get(n, reason)
            counts[reason] += 1
            record = {'id': r['id'], 'source_record_index': r['source_record_index'], 'source_group': groups[n], 'status': reason, 'edit_character_ratio': ratio, 'new_split_allocation': False, 'approved_for_training': False}
            idx.write(json.dumps(record) + '\n')
            if reason not in ('candidate', 'broad_edit_review'):
                continue
            result = {**r, 'screening': record}
            (good if reason == 'candidate' else pending).write(json.dumps(result, ensure_ascii=False) + '\n')
            if reason == 'candidate':
                candidate_groups[groups[n]] += 1
                types.update(i['author_type'] for i in r['supervision']['issues'])
            row_types = {i['author_type'] for i in r['supervision']['issues']}
            row_ops = {'insertion' if not i['quote'] else 'deletion' if not i['replacement'] else 'replacement' for i in r['supervision']['issues']}
            if len(samples) < 9 and (row_types - covered or row_ops - operations or reason == 'broad_edit_review' and not any(x['screening']['status'] == reason for x in samples)):
                samples.append(result)
                covered.update(row_types)
                operations.update(row_ops)
    with (output / 'review_samples.jsonl').open('x', encoding='utf8') as f:
        for r in samples:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    summary = {'input_converted_rows': len(rows), 'original_complete_edit_rows': sum(r['supervision']['all_flagged_issues_have_explicit_edits'] for r in rows), 'status_counts': dict(counts), 'all_source_groups': len(sizes), 'largest_all_source_group': max(sizes.values()), 'candidate_source_groups': len(candidate_groups), 'largest_candidate_group': max(candidate_groups.values(), default=0), 'candidate_error_types': dict(types), 'review_sample_ids': [r['id'] for r in samples], 'review_sample_types': sorted(covered), 'review_sample_operations': sorted(operations), 'grouping_method': 'connected by identical whitespace-normalized reference OR answer across all converted rows', 'grouping_limit': 'conservative exact-text links; paraphrase/topic overlap and historical model exposure unverified', 'broad_edit_policy': 'sum(max(span chars,replacement chars))/answer chars > 0.5; review heuristic, not semantic failure', 'new_split_allocation': False, 'approved_for_training': 0, 'training_started': False, 'model_calls': 0, 'supervised_tokens': None}
    assert sum(counts.values()) == len(rows)
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args.input, args.output), ensure_ascii=False))
