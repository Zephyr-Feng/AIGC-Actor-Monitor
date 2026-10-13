"""Validate missing-evidence labels through pairs of compatible completions."""
import copy
import hashlib
import json
from pathlib import Path
from relation_probe_v2 import ROOT, OUT, global_fixture, local_fixture, remove, expected, resolve, sha


def validate():
    package = json.loads((OUT / 'inputs.json').read_text(encoding='utf8'))
    frozen = json.loads((OUT / 'freeze.json').read_text(encoding='utf8'))
    for name, digest in frozen.items():
        assert sha(ROOT / name) == digest, name
    rows = {c['id']: c for c in package['cases']}
    mixed = global_fixture([96, 90, 79, 50, 20, 10])
    ids_other = copy.deepcopy(mixed)
    for i, region in enumerate(ids_other['most_atypical_regions'], 7):
        region['region_id'] = 'R' + str(i)
    bbox_other = copy.deepcopy(mixed)
    bbox_other['most_atypical_regions'][0]['bbox'] = [10, 0, 110, 100]
    limitation_other = copy.deepcopy(mixed)
    limitation_other['limitations'][0] = '表征偏离提供区域统计特征。'
    witnesses = {
        'Q01': (global_fixture([100] * 9), global_fixture([100] * 5 + [20] * 4), ['/observations/num_atypical_regions', '/observations/atypical_fraction']),
        'Q02': (global_fixture([100] * 3), global_fixture([100, 100, 96]), ['/most_atypical_regions/2/deviation_percentile']),
        'Q03': (mixed, global_fixture([96, 90, 79, 50, 20, 10], top=2), ['/most_atypical_regions']),
        'Q04': (global_fixture([100, 95, 80, 60, 40, 20]), global_fixture([100] * 6), ['/observations/median_deviation_percentile', '/observations/num_atypical_regions', '/observations/atypical_fraction', '/most_atypical_regions']),
        'A01': (mixed, ids_other, ['/most_atypical_regions']),
        'A02': (local_fixture(), local_fixture(0.18820304274559021), ['/score', '/observation']),
        'A03': (local_fixture(), local_fixture(threshold=0.6), []),
        'A04': (mixed, bbox_other, ['/most_atypical_regions/0/bbox']),
        'T03': (mixed, limitation_other, ['/limitations']),
    }
    witnesses['T01'] = witnesses['Q01']
    witnesses['T02'] = witnesses['A02']
    witnesses['T04'] = witnesses['Q03']
    checks = []
    for group, (true_completion, false_completion, paths) in witnesses.items():
        case = rows[group + '_missing_key']
        observed = case['payload']['source_evidence']['actual_returns'][0]['original_return']
        assert expected(true_completion, case['rule'])
        assert not expected(false_completion, case['rule'])
        if group == 'A03':
            true_projected, false_projected = copy.deepcopy(true_completion), copy.deepcopy(false_completion)
            for value in [true_projected, false_projected]:
                value['observation'] = '局部纹理原始合成分数为 0.088203，信号为 real_like。'
        else:
            true_projected = remove(true_completion, *paths)
            false_projected = remove(false_completion, *paths)
        assert true_projected == false_projected == observed, group
        checks.append({'group': group, 'same_observed_missing_return': True, 'compatible_true_completion': true_completion,
                       'compatible_false_completion': false_completion, 'projection_removed_fields': paths,
                       'claim_under_determined_by_given_return': True})
    refs_checked = 0
    for case in rows.values():
        evidence = case['payload']['source_evidence']
        for actual, refs in zip(evidence['actual_returns'], evidence['return_field_references'], strict=True):
            assert actual['returned_after_step'] == 1
            for pointer in refs:
                resolve(actual['original_return'], pointer)
                refs_checked += 1
    for item in package['schedule']:
        assert hashlib.sha256(item['prompt'].encode()).hexdigest() == item['prompt_sha256']
        assert '明确标识的抽象关系诊断fixture' in item['prompt']
    report = {'material_kind': 'explicit_abstract_diagnostic_fixture', 'missing_cases_verified_by_counterexamples': len(checks),
              'all_frozen_files_verified': len(frozen), 'reference_pointers_resolved': refs_checked,
              'cases': 48, 'requests': 96, 'independent_human_review': False, 'model_loaded': False,
              'input_sha256': sha(OUT / 'inputs.json'), 'validation_code_sha256': sha(Path(__file__)), 'witnesses': checks}
    with (OUT / 'input_validation.json').open('x', encoding='utf8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != 'witnesses'}, ensure_ascii=False))


if __name__ == '__main__':
    validate()
