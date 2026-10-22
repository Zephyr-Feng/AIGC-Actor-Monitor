"""Prepare and inspect full-answer reviews of the existing natural candidate pool."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import re

from assemble_feedback import assemble
from build_feedback_candidates import restore

HELD = {'ragtruth:' + key for key in ('5030', '11993', '12987', '11240')}


def readl(path):
    with path.open(encoding='utf8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def packets(candidates, records, annotations):
    grouped = defaultdict(list)
    for candidate in candidates:
        grouped[candidate['origin']].append(candidate)
    if len({row['id'] for row in candidates}) != len(candidates):
        raise ValueError('duplicate candidate')
    result = []
    for origin, spans in sorted(grouped.items(), key=lambda item: (item[1][0]['group'], item[0])):
        row = records[origin]
        cards = spans[0]['input']['证据卡']
        answer = row['input']['待核回答']
        if row['split'] != 'train' or restore(cards) != row['input']['原始资料']:
            raise ValueError('source or existing split mismatch')
        for span in spans:
            if span['group'] != row['group'] or span['input']['待核回答'] != answer or span['input']['证据卡'] != cards:
                raise ValueError('inconsistent candidates within origin')
            label = span['human_span_annotation']
            if answer[label['start']:label['end']] != label['text']:
                raise ValueError('invalid inherited span')
        annotation = annotations[origin]
        for label in annotation['labels']:
            if answer[label['start']:label['end']] != label['text']:
                raise ValueError('invalid author annotation')
        source = row['input']['原始资料']
        result.append({
            'id': 'natural_full:' + origin, 'origin': origin, 'group': row['group'],
            'order': len(result) + 1,
            'task': 'news' if isinstance(source, str) else 'business' if 'hours' in source else 'qa',
            'input': {'审核范围': '核对完整回答的所有事实主张、重复错误和必要限制；无标注不等于正确。',
                      '证据卡': deepcopy(cards), '待核回答': answer},
            'original_source': deepcopy(source), 'original_target': deepcopy(row['target']),
            'author_annotation': deepcopy(annotation), 'original_candidates': deepcopy(spans),
            'inherited_hold': origin in HELD, 'human_gold': False,
            'review_status': 'held_for_adjudication' if origin in HELD else 'pending_full_review',
            'approved_for_training': False,
        })
    return result


def validate_review(packet, review):
    if review['origin'] != packet['origin'] or review['group'] != packet['group']:
        raise ValueError('review identity mismatch')
    if review.get('human_gold') is not False or review.get('approved_for_training') is not False:
        raise ValueError('assistant reference cannot be human gold or released training data')
    if review.get('reviewer') != 'assistant_nonblind' or review.get('full_source_read') is not True or review.get('full_answer_read') is not True:
        raise ValueError('missing full review attestation')
    if review['status'] not in ('assistant_reference_prepared', 'held_for_adjudication'):
        raise ValueError('invalid review status')
    if packet['inherited_hold'] and review['status'] != 'held_for_adjudication':
        raise ValueError('inherited hold cannot be released')
    if not review.get('author_annotation_assessment') or not review.get('coverage_note'):
        raise ValueError('missing author-label or full-answer assessment')
    target = review.get('target')
    if target is None and review['status'] != 'held_for_adjudication':
        raise ValueError('reference requires complete feedback')
    if target is not None:
        return assemble(packet['input']['待核回答'], packet['input']['证据卡'], target)


def refresh(output):
    queue = readl(output / 'review_packets.jsonl')
    lookup = {row['origin']: row for row in queue}
    reviews = []
    for path in sorted(output.glob('reviews_*.jsonl')):
        reviews.extend(readl(path))
    origins = [r['origin'] for r in reviews]
    if len(origins) != len(set(origins)):
        raise ValueError('duplicate origin across review batches')
    for review in reviews:
        validate_review(lookup[review['origin']], review)
    usable = [r for r in reviews if r['status'] == 'assistant_reference_prepared']
    reviewed = set(origins)
    unreviewed = [r for r in queue if r['origin'] not in reviewed]
    pending = [r for r in unreviewed if not r['inherited_hold']]
    held = {r['origin'] for r in queue if r['inherited_hold']} | {r['origin'] for r in reviews if r['status'] == 'held_for_adjudication'}
    summary = {
        'candidate_spans': sum(len(r['original_candidates']) for r in queue),
        'complete_answers': len(queue), 'source_groups': len({r['group'] for r in queue}),
        'tasks': dict(Counter(r['task'] for r in queue)),
        'full_reviews_recorded': len(reviews), 'assistant_full_references': len(usable),
        'reference_source_groups': len({r['group'] for r in usable}),
        'held_answers': len(held), 'pending_answers': len(pending),
        'awaiting_full_review': len(unreviewed),
        'unreviewed_held_answers': sum(r['inherited_hold'] for r in unreviewed),
        'multi_issue_references': sum(len(r['target']['问题']) > 1 for r in usable),
        'issue_count_distribution': dict(Counter(len(r['target']['问题']) for r in usable)),
        'answer_characters': {'min': min(len(r['input']['待核回答']) for r in queue),
                              'max': max(len(r['input']['待核回答']) for r in queue)},
        'reference_target_characters': [len(json.dumps(r['target'], ensure_ascii=False)) for r in usable],
        'next_pending': unreviewed[0]['origin'] if unreviewed else None,
        'next_pending_order': unreviewed[0]['order'] if unreviewed else None,
        'human_gold': False, 'approved_for_training': 0, 'new_split_allocation': False,
        'model_calls': 0, 'training_started': False,
        'supervised_token_count': None,
        'token_note': '尚未使用实际训练模板/本地分词器计数；字符长度不是token数量或监督占比。',
        'license_note': '沿用既有RAGTruth仓库MIT记录；底层新闻、Yelp等第三方权利仍适用；仅本地研究，无再发布授权结论。',
        'exposure_note': '全部来自既有train候选；可能被历史公共SFT接触；不是独立评估，不重新划分。',
    }
    write_json(output / 'progress.json', summary)
    return summary


def prepare(data, output):
    candidates = readl(data / 'natural_feedback_review_v2_20261017/review_candidates.jsonl')
    origins = {r['origin'] for r in candidates}
    records = {r['id']: r for r in readl(data / 'built_v3/train.primary.records.jsonl') if r['id'] in origins}
    annotations = {}
    # Filter by the leading ID before decoding provenance of any other allocation.
    with (data / 'built_v3/provenance.jsonl').open(encoding='utf8') as stream:
        for line in stream:
            match = re.match(r'^\{"id":\s*"([^"]+)"', line)
            if match and match[1] in origins:
                row = json.loads(line)
                if row['id'] in annotations:
                    raise ValueError('duplicate selected provenance')
                annotations[row['id']] = row['annotation']
    queue = packets(candidates, records, annotations)
    if (len(candidates), len(queue), len({r['group'] for r in queue})) != (1271, 1020, 659):
        raise ValueError('candidate scope differs from authorized inventory')
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'review_packets.jsonl').open('x', encoding='utf8') as stream:
        for row in queue:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    return refresh(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if not args.refresh and args.data is None:
        parser.error('--data is required to prepare')
    print(json.dumps(refresh(args.output) if args.refresh else prepare(args.data, args.output), ensure_ascii=False))
