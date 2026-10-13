"""Assemble preserved outputs and frozen local-gate results; no model calls."""
import hashlib
import json
from pathlib import Path
from boundary_probe_v1 import local_gate

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'experiments/faithbench_monitor_v0/private/boundary_expansion_20261011'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def assemble():
    for name, expected in json.loads((OUT / 'freeze.json').read_text(encoding='utf8')).items():
        assert digest(ROOT / name) == expected, name
    package = json.loads((OUT / 'inputs.json').read_text(encoding='utf8'))
    trial = OUT / 'backup/boundary_expansion_v1_trial'
    finished = json.loads((trial / 'completed.json').read_text(encoding='utf8'))
    assert finished['predictions'] == 38 and finished['protected_unchanged'] and finished['adapter_unchanged']
    assert digest(trial / 'predictions.jsonl') == finished['predictions_sha256']
    new = [json.loads(s) for s in (trial / 'predictions.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(new) == len(package['schedule']) == 38
    combined = []
    for row, item in zip(new, package['schedule'], strict=True):
        assert all(row[k] == item[k] for k in ['id', 'condition', 'model', 'prompt_sha256'])
        combined.append(row | {'reused': False})
    for item in package['reused']:
        old = item['old_record']
        assert digest(ROOT / item['origin_path']) == item['origin_sha256']
        assert old['prompt_sha256'] == item['prompt_sha256'] and old['model'] == item['model']
        combined.append(old | {k: item[k] for k in ['id', 'condition', 'model', 'prompt_sha256']} | {'reused': True, 'origin_path': item['origin_path'], 'origin_sha256': item['origin_sha256']})
    combined.sort(key=lambda r: (r['id'], r['model'], r['condition']))
    assert len(combined) == len({(r['id'], r['model'], r['condition']) for r in combined}) == 48
    with (OUT / 'combined_predictions.jsonl').open('x', encoding='utf8') as stream:
        for row in combined:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    expected = {r['id']: r for r in json.loads((OUT / 'review_expected.json').read_text(encoding='utf8'))}
    cases = {r['id']: r for r in package['cases']}
    audit = []
    for row in combined:
        case = cases[row['id']]
        catalog = {}
        for actual, refs in zip(case['payload']['actual_returns'], case['payload']['return_field_references'], strict=True):
            for pointer, eid in refs.items():
                value = actual['original_return']
                for part in pointer.split('/')[1:]:
                    value = value[int(part)] if isinstance(value, list) else value[part]
                catalog[eid] = {'pointer': pointer, 'value': value}
        selected = row.get('parsed', {}).get('return_reference_ids', [])
        audit.append({k: row[k] for k in ['id', 'condition', 'model', 'reused', 'parse_valid']} | {
            'parsed': row.get('parsed'), 'expected': expected[row['id']]['judgement'],
            'label_matches_frozen_expectation': row.get('parsed', {}).get('judgement') == expected[row['id']]['judgement'],
            'selected_fields': {eid: catalog.get(eid) for eid in selected}, 'references_exist': all(eid in catalog for eid in selected),
            'gate': local_gate(row, case['payload'], case['requirement'])})
    dump(OUT / 'gate_results.json', audit)
    print(json.dumps({'logical_conditions': 48, 'new_predictions': 38, 'strict_format_valid': sum(r['parse_valid'] for r in combined), 'combined_sha256': digest(OUT / 'combined_predictions.jsonl')}, ensure_ascii=False))


if __name__ == '__main__':
    assemble()
