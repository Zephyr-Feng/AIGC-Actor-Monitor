"""Descriptive paired counts from locked manual reviews; no independence claims."""
from collections import Counter
from review_relation_sft_comparison_v1 import HERE, PRIVATE, read, dump, sha, case_map


def joint(row):
    return all(row[key] for key in ['label_correct', 'reason_correct', 'citation_sufficient', 'label_reason_consistent'])


def main():
    rows = read(HERE / 'first_review_locked.json')['rows']
    predictions = read(HERE / 'combined_predictions.json')
    raw = {(row['model'], row['id']): row for row in predictions}
    cases = case_map()
    metrics = {}
    for model in ['base', 'ordinary', 'relation']:
        for scope in ['held_abstract_relation_development', 'seen_48_fixed_regression']:
            selected = [row for row in rows if row['model'] == model and row['scope'] == scope]
            groups = sorted({row['group'] for row in selected})
            lookup = {row['id']: row for row in selected}
            metrics[model + '/' + scope] = {
                'n': len(selected), 'label_correct': sum(row['label_correct'] for row in selected),
                'label_reason_joint': sum(row['label_correct'] and row['reason_correct'] and row['label_reason_consistent'] for row in selected),
                'citation_joint': sum(joint(row) for row in selected),
                'groups': len(groups), 'all_four_pass': sum(all(joint(row) for row in selected if row['group'] == group) for group in groups),
                'decisive_change_pairs': sum(joint(lookup[group + '_supported']) and joint(lookup[group + '_evidence_changed']) for group in groups),
                'missing_pairs': sum(joint(lookup[group + '_supported']) and joint(lookup[group + '_missing_key']) for group in groups),
                'actor_pairs': sum(joint(lookup[group + '_supported']) and joint(lookup[group + '_actor_changed']) for group in groups),
                'false_support': sum(raw[(model, row['id'])].get('parsed', {}).get('judgement') == '支持' and cases[row['id']]['judgement'] == '无法据此支持' for row in selected),
                'false_reject': sum(raw[(model, row['id'])].get('parsed', {}).get('judgement') == '无法据此支持' and cases[row['id']]['judgement'] == '支持' for row in selected),
                'format_failures': sum(not raw[(model, row['id'])]['parse_valid'] for row in selected),
                'reason_first_valid_outputs': sum(row['output_order_compliant'] for row in selected),
                'family_joint': {family: {'n': sum(row['family'] == family for row in selected), 'correct': sum(joint(row) for row in selected if row['family'] == family)} for family in sorted({row['family'] for row in selected})},
                'failure_types': dict(Counter(row['failure_type'] for row in selected if row['failure_type'])),
            }
    paired = {}
    for a, b in [('base', 'ordinary'), ('base', 'relation'), ('ordinary', 'relation')]:
        for scope in ['held_abstract_relation_development', 'seen_48_fixed_regression']:
            left = {row['id']: row for row in rows if row['model'] == a and row['scope'] == scope}
            right = {row['id']: row for row in rows if row['model'] == b and row['scope'] == scope}
            assert left.keys() == right.keys()
            paired[a + '->' + b + '/' + scope] = {'fixed': [key for key in left if not joint(left[key]) and joint(right[key])], 'regressed': [key for key in left if joint(left[key]) and not joint(right[key])], 'shared_failures': [key for key in left if not joint(left[key]) and not joint(right[key])]}
    gates = {}
    for model in ['ordinary', 'relation']:
        b = metrics['base/seen_48_fixed_regression']; m = metrics[model + '/seen_48_fixed_regression']
        bh = metrics['base/held_abstract_relation_development']; mh = metrics[model + '/held_abstract_relation_development']
        tests = {'regression_joint_plus_one': m['citation_joint'] >= b['citation_joint'] + 1, 'regression_groups_plus_one': m['all_four_pass'] >= b['all_four_pass'] + 1, 'held_joint_retained': mh['citation_joint'] >= bh['citation_joint'], 'regression_errors_not_increased': m['false_support'] <= b['false_support'] and m['false_reject'] <= b['false_reject'], 'held_errors_not_increased': mh['false_support'] <= bh['false_support'] and mh['false_reject'] <= bh['false_reject']}
        gates[model] = tests | {'candidate_passed': all(tests.values())}
    result = {'review_sha256': sha(HERE / 'first_review_locked.json'), 'metrics': metrics, 'paired_changes': paired, 'candidate_gates': gates, 'independent_test': False, 'human_gold': False}
    dump(HERE / 'review_metrics.json', result)
    print(__import__('json').dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
