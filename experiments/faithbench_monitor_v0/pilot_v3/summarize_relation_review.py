"""Summarize locked manual reviews and paired changes; no semantic auto-judge."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def joint(row):
    return row['label_correct'] and row['reason_correct'] and row['label_reason_consistent']


def summarize(rows):
    groups = {g: {r['variant']: r for r in rows if r['group'] == g}
              for g in sorted({r['group'] for r in rows})}
    assert len(rows) == 48 and len(groups) == 12 and all(len(v) == 4 for v in groups.values())
    return {'n': len(rows), 'labels': sum(r['label_correct'] for r in rows),
            'label_reason_joint': sum(joint(r) for r in rows),
            'label_reason_citation_joint': sum(joint(r) and r['citation_sufficient'] for r in rows),
            'explicit_contradictions': sum(r.get('explicit_label_reason_contradiction', not r['label_reason_consistent']) for r in rows),
            'label_reason_conflicts': sum(not r['label_reason_consistent'] for r in rows),
            'correct_label_bad_reason': sum(r['label_correct'] and not r['reason_correct'] for r in rows),
            'groups_all_four_joint_pass': sum(all(joint(r) for r in v.values()) for v in groups.values()),
            'decisive_pairs_joint_pass': sum(joint(v['supported']) and joint(v['evidence_changed']) for v in groups.values()),
            'missing_pairs_joint_pass': sum(joint(v['supported']) and joint(v['missing_key']) for v in groups.values()),
            'actor_pairs_correct_and_stable': sum(joint(v['supported']) and joint(v['actor_changed']) for v in groups.values()),
            'supported_false_rejections': sum(not r['label_correct'] for r in rows if r['variant'] in ['supported', 'actor_changed']),
            'unsupported_false_supports': sum(not r['label_correct'] for r in rows if r['variant'] in ['evidence_changed', 'missing_key']),
            'group_joint': {g: sum(joint(r) for r in v.values()) for g, v in groups.items()},
            'failure_types': dict(collections.Counter(r['failure_type'] for r in rows if r['failure_type']))}


def run(args):
    current = json.loads(args.review.read_text(encoding='utf8'))['rows']
    baseline = json.loads(args.baseline.read_text(encoding='utf8'))['rows']
    old = {(r['id'], r['model']): r for r in baseline}
    assert len(old) == 96
    result = {'review_sha256': hashlib.sha256(args.review.read_bytes()).hexdigest(),
              'baseline_review_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'summarizer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'conditions': {}}
    for model, condition in sorted({(r['model'], r['condition']) for r in current}):
        rows = [r for r in current if r['model'] == model and r['condition'] == condition]
        stats = summarize(rows)
        stats.update(baseline=summarize([r for r in baseline if r['model'] == model]),
                     fixed=[r['id'] for r in rows if joint(r) and not joint(old[(r['id'], model)])],
                     regressed=[r['id'] for r in rows if not joint(r) and joint(old[(r['id'], model)])])
        result['conditions'][model + '/' + condition] = stats
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: {n: v[n] for n in ['labels', 'label_reason_joint', 'explicit_contradictions', 'fixed', 'regressed']}
                      for k, v in result['conditions'].items()}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['review', 'baseline', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    run(parser.parse_args())
