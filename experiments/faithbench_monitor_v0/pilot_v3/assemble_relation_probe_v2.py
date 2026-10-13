"""Prepare an evidence-linked review table; no automatic semantic grading."""
import hashlib
import json
from pathlib import Path

from relation_probe_v2 import resolve

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'experiments/faithbench_monitor_v0/private/relation_probe_v2_20261011'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble():
    for name, digest in json.loads((OUT / 'freeze.json').read_text(encoding='utf8')).items():
        assert sha(ROOT / name) == digest, name
    package = json.loads((OUT / 'inputs.json').read_text(encoding='utf8'))
    trial = OUT / 'backup/relation_probe_v2_trial'
    completed = json.loads((trial / 'completed.json').read_text(encoding='utf8'))
    assert completed['predictions'] == 96 and completed['optimizer_steps'] == 0
    assert completed['protected_unchanged'] and completed['adapter_unchanged']
    assert completed['input_sha256'] == sha(OUT / 'inputs.json')
    assert completed['predictions_sha256'] == sha(trial / 'predictions.jsonl')
    rows = [json.loads(line) for line in (trial / 'predictions.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(rows) == len(package['schedule']) == 96
    cases = {c['id']: c for c in package['cases']}
    expected = {c['id']: c for c in json.loads((OUT / 'review_expected.json').read_text(encoding='utf8'))}
    audit = []
    for row, request in zip(rows, package['schedule'], strict=True):
        assert all(row[k] == request[k] for k in ['id', 'condition', 'model', 'prompt_sha256'])
        case = cases[row['id']]
        evidence = case['payload']['source_evidence']
        fact = evidence['actual_returns'][0]['original_return']
        catalog = {eid: {'pointer': ptr, 'value': resolve(fact, ptr)}
                   for ptr, eid in evidence['return_field_references'][0].items()}
        parsed = row.get('parsed', {})
        selected = parsed.get('return_reference_ids', [])
        audit.append({k: row[k] for k in ['id', 'model', 'condition', 'parse_valid', 'input_tokens', 'output_tokens', 'seconds']} | {
            'group': case['group'], 'variant': case['variant'], 'relation_cluster': case['relation_cluster'],
            'claim': case['payload']['subject_to_review']['claim'], 'rule': case['rule'],
            'expected': expected[row['id']]['judgement'], 'basis': expected[row['id']]['basis'],
            'label_matches': row['parse_valid'] and parsed.get('judgement') == expected[row['id']]['judgement'],
            'references_exist': row['parse_valid'] and all(eid in catalog for eid in selected),
            'selected_fields': {eid: catalog.get(eid) for eid in selected},
            'parsed': row.get('parsed'), 'raw': row['raw'], 'actual_return': fact,
            'reason_correct': None, 'citation_sufficient': None,
            'semantic_review_status': 'pending_same_assistant_review_not_human_gold'})
    audit.sort(key=lambda x: (x['group'], x['variant'], x['model']))
    with (OUT / 'review_table.json').open('x', encoding='utf8') as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'requests': 96, 'parse_valid': sum(x['parse_valid'] for x in audit),
                      'labels_match': sum(x['label_matches'] for x in audit),
                      'raw_sha256': sha(trial / 'predictions.jsonl'), 'semantic_review': 'pending'}, ensure_ascii=False))


if __name__ == '__main__':
    assemble()
