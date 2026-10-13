"""Read completed scalar bindings and count whitespace in existing raw prefixes."""
import json
import os
import sys
from pathlib import Path
from binding_compact_probe_v1 import OUT, ROOT, PRIVATE, sha, dump, resolve


def completed_binding_objects(raw):
    """Read intact objects only; never close, repair or reclassify the full output."""
    pos = raw.index('[', raw.index('"bindings"')) + 1
    decoder = json.JSONDecoder()
    values = []
    while pos < len(raw):
        while pos < len(raw) and raw[pos] in ' \r\n\t,':
            pos += 1
        if pos == len(raw) or raw[pos] == ']':
            break
        try:
            value, pos = decoder.raw_decode(raw, pos)
        except json.JSONDecodeError:
            break
        assert isinstance(value, dict)
        values.append(value)
    return values


def strip_outside_string_whitespace(raw):
    result, inside, escaped = [], False, False
    for char in raw:
        if inside:
            result.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                inside = False
        elif char == '"':
            result.append(char)
            inside = True
        elif not char.isspace():
            result.append(char)
    return ''.join(result)


def run():
    frozen = json.loads((OUT / 'final_stage_audit.json').read_text(encoding='utf-8'))
    for name, digest in frozen['artifact_hashes'].items():
        assert sha(ROOT / name) == digest, name
    assets = PRIVATE / 'relation_sft_materials_v1_20261011'
    provenance = json.loads((assets / 'tokenizer_cache_provenance.json').read_text(encoding='utf-8'))
    for name, v in provenance['files'].items():
        assert sha(assets / 'tokenizer_cache' / name) == v['sha256']
    os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1')
    sys.path.insert(0, str(assets / 'python_libs'))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(assets / 'tokenizer_cache', local_files_only=True)
    materials = {r['id']: r for r in json.loads((OUT / 'materials.json').read_text(encoding='utf-8'))['records']}
    raw_path = OUT / 'backup/binding_compact_probe_v1_trial/predictions.jsonl'
    rows = []
    for line in raw_path.read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        material = materials[record['id']]
        evidence = material['input_payload']['source_evidence']
        fact = evidence['actual_returns'][0]['original_return']
        pointers = {eid: pointer for pointer, eid in evidence['return_field_references'][0].items()}
        bindings = completed_binding_objects(record['raw'])
        present, covered, scalar_correct, entity_attached = [], set(), 0, 0
        for b in bindings:
            if 'ref' in b:
                pointer = pointers[b['ref']]
                scalar_correct += b['value'] == resolve(fact, pointer)
                present.append(b['ref'])
                covered.add(('present', pointer))
                entity_attached += 'entity' in b
            else:
                covered.add(('missing', b['object'] + '/' + b['field']))
        required = {('present', pointers[b['ref']]) if 'ref' in b else
                    ('missing', b['object'] + '/' + b['field']) for b in material['expected']['bindings']}
        compact_prefix = strip_outside_string_whitespace(record['raw'])
        if record['parse_valid']:
            assert json.loads(compact_prefix) == record['parsed']
        original_tokens = len(tokenizer.encode(record['raw'], add_special_tokens=False))
        compact_tokens = len(tokenizer.encode(compact_prefix, add_special_tokens=False))
        rows.append(dict(id=record['id'], full_output_parse_valid=record['parse_valid'],
            complete_binding_objects_observed=len(bindings), source_scalar_values_correct=scalar_correct,
            present_binding_count=len(present), duplicate_present_ref_count=len(present)-len(set(present)),
            expected_binding_records=len(material['expected']['bindings']),
            required_fields_observed=len(required & covered), required_fields_total=len(required),
            explicit_entity_attached_count=entity_attached,
            standalone_raw_prefix_tokens=original_tokens,
            same_observed_prefix_without_outside_string_whitespace_tokens=compact_tokens,
            token_difference_on_existing_prefix=original_tokens-compact_tokens,
            full_output_not_repaired=True, final_label_not_inferred=not record['parse_valid']))
    result = dict(stage='existing_raw_prefix_posthoc_only', new_model_requests=0, optimizer_steps=0,
                  new_supervision_targets=0, remote_calls=0, raw_sha256=sha(raw_path),
                  limits=['Intact bindings read from prefixes do not make incomplete JSON valid.',
                          'Correct scalar values do not prove entity association, required-field coverage or relations.',
                          'Whitespace counts are standalone tokenization of the already observed prefix, not full completed generation.',
                          'Removing whitespace does not reveal unseen final checks, reason or judgement.'], rows=rows)
    dump(OUT / 'posthoc_prefix_audit_v1.json', result)
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == '__main__':
    run()
