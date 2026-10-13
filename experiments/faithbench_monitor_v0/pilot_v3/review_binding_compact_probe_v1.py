"""Assemble six immutable outputs and field audits; no semantic auto-judging."""
import json
from binding_compact_probe_v1 import OUT, SOURCE, ROOT, sha, dump, audit_answer


def main():
    for name, digest in json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))['artifact_hashes'].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in json.loads((OUT / 'backup_hashes.json').read_text(encoding='utf-8')).items():
        assert sha(OUT / 'backup' / name) == digest, name
    trial = OUT / 'backup/binding_compact_probe_v1_trial'
    completed = json.loads((trial / 'completed.json').read_text(encoding='utf-8'))
    assert completed['input_sha256'] == sha(OUT / 'inputs.json')
    assert completed['predictions_sha256'] == sha(trial / 'predictions.jsonl')
    records = [json.loads(line) for line in (trial / 'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    materials = json.loads((OUT / 'materials.json').read_text(encoding='utf-8'))['records']
    by_id = {r['id']: r for r in materials}
    assert len(records) == 6 and {r['id'] for r in records} == set(by_id)
    audit = []
    for row in records:
        expected = by_id[row['id']]
        assert row['prompt_sha256'] == expected['prompt_sha256']
        item = dict(id=row['id'], parse_valid=row['parse_valid'],
                    output_tokens=row['output_tokens'], at_output_limit=row['output_tokens'] == 384)
        if row['parse_valid']:
            try:
                item.update(audit_answer(row['parsed'], expected['input_payload'], expected['expected']))
                item['field_audit_pass'] = True
            except (AssertionError, KeyError, IndexError, TypeError, ValueError) as error:
                item.update(field_audit_pass=False, field_audit_error=str(error))
            item['label_matches_target'] = row['parsed']['judgement'] == expected['expected']['judgement']
        else:
            item.update(field_audit_pass=False, label_matches_target=None,
                        field_audit_error='Incomplete raw preserved; no repair or inferred final label.')
        audit.append(item)
    dump(OUT / 'structural_audit.json', dict(records=6, automatic_semantic_review=False, rows=audit))
    # Original and output are displayed together for manual review, never sent to the model.
    dump(OUT / 'review_snapshot.json', dict(units=[dict(id=r['id'], input_payload=by_id[r['id']]['input_payload'],
        expected=by_id[r['id']]['expected'], raw=r['raw'], structural=a) for r, a in zip(records, audit, strict=True)]))
    print(json.dumps(dict(records=6, parsed=sum(r['parse_valid'] for r in records),
        field_audits_pass=sum(r['field_audit_pass'] for r in audit),
        at_output_limit=sum(r['at_output_limit'] for r in audit)), ensure_ascii=False))


if __name__ == '__main__':
    main()
