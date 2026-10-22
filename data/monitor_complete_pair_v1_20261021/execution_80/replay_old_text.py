"""CPU-only post-hoc diagnosis; never changes frozen scores or original outputs."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MODULE = ROOT.parents[2] / 'experiments/faithbench_monitor_v0/monitor_quality_v2/full_action_feedback.py'
spec = importlib.util.spec_from_file_location('full_action_feedback', MODULE)
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)
ARMS = ('S_actor', 'M_current00373')
TEXT = ('action_reason', 'evidence_gap', 'unresolved_conflicts')


def project(original, raw):
    candidate = json.loads(raw)
    if not isinstance(candidate, dict) or set(candidate) != set(original):
        raise ValueError('complete action keys differ')
    evidence = candidate['current_evidence']
    if not isinstance(evidence, list) or len(evidence) != len(original['current_evidence']):
        raise ValueError('evidence count differs')
    result = deepcopy(original)
    for key in TEXT:
        result[key] = deepcopy(candidate[key])
    for before, after, target in zip(original['current_evidence'], evidence, result['current_evidence']):
        if not isinstance(after, dict) or set(before) != set(after) or before['source'] != after['source']:
            raise ValueError('evidence identity differs; refuse index projection')
        target['interpretation'] = after['interpretation']
    return feedback.validate_revision(original, json.dumps(result, ensure_ascii=False))


def differences(before, after, path=''):
    if isinstance(before, dict) and isinstance(after, dict) and set(before) == set(after):
        return [d for key in before for d in differences(before[key], after[key], path + '/' + key)]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [d for i, (a, b) in enumerate(zip(before, after)) for d in differences(a, b, path + '/' + str(i))]
    return [] if before == after else [dict(path=path, before=before, after=after)]


def main():
    cases = json.loads((ROOT / 'old_monitor_complete_cases.json').read_text(encoding='utf-8'))
    freeze = json.loads((ROOT / 'freeze.json').read_text(encoding='utf-8'))
    expected = freeze['primary_error_ids'] + freeze['protection_ids']
    assert len(cases) == len(expected) == len(set(expected)) == 28
    assert {c['id'] for c in cases} == set(expected)
    saved = {}
    for name in ('editor/actor_outputs.jsonl', 'old_baseline_remaining/editor/actor_outputs.jsonl'):
        for line in (ROOT / name).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['arm'] in ARMS:
                key = (row['case_id'], row['arm'])
                assert key not in saved
                saved[key] = row
    assert len(saved) == 56
    originals = deepcopy(cases)
    rows = []
    for case in cases:
        original = case['original']['original_action']
        for arm in ARMS:
            edit = case['branches'][arm]['edit']
            assert edit == saved[case['id'], arm]
            raw = json.loads(edit['raw'])
            projected = project(original, edit['raw'])
            changes = differences(original, raw)
            protected_changes = [d for d in changes if d['path'] not in ('/' + k for k in TEXT)
                                 and not d['path'].startswith('/unresolved_conflicts/')
                                 and not d['path'].endswith('/interpretation')]
            fallback = bool(edit['validation_error'])
            assert fallback == bool(protected_changes)
            assert edit['final_action'] == (original if fallback else raw)
            assert fallback or projected == edit['final_action']
            rows.append(dict(id=case['id'], arm=arm, primary=case['id'] in freeze['primary_error_ids'],
                             natural=case['id'] in freeze['natural_error_ids'], fallback=fallback,
                             protected_changes=protected_changes,
                             text_changes=[d['path'] for d in differences(original, projected)],
                             projected_action=projected, semantic_status='not_automatically_scored'))
    assert cases == originals
    # Self-check: protected writes are discarded; source swaps and bad text fail closed.
    original = cases[0]['original']['original_action']
    bad = deepcopy(original)
    bad['final_verdict'] = 'inconclusive'
    bad['current_evidence'][0]['direction'] = 'fake'
    bad['action_reason'] = 'test explanation'
    result = project(original, json.dumps(bad))
    assert result['final_verdict'] == original['final_verdict']
    assert result['current_evidence'][0]['direction'] == original['current_evidence'][0]['direction']
    assert result['action_reason'] == 'test explanation'
    for key, value in [('source', 'wrong-source'), ('interpretation', 123)]:
        bad = deepcopy(original)
        bad['current_evidence'][0][key] = value
        try:
            project(original, json.dumps(bad))
        except ValueError:
            pass
        else:
            raise AssertionError('invalid projection accepted')
    summary = {arm: dict(rows=28, primary_fallbacks=sum(r['primary'] and r['fallback'] for r in rows if r['arm'] == arm),
                        protection_fallbacks=sum(not r['primary'] and r['fallback'] for r in rows if r['arm'] == arm),
                        changed_from_final=sum(r['fallback'] and bool(r['text_changes'])
                                               for r in rows if r['arm'] == arm)) for arm in ARMS}
    report = dict(scope='post_hoc_development_diagnosis_not_frozen_score', model_calls=0,
                  summary=summary, rows=rows)
    with (ROOT / 'old_text_replay.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
