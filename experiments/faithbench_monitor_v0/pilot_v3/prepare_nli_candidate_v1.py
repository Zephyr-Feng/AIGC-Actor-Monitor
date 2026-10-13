"""Candidate input projection only: no inference, labels or subject restoration."""
import argparse
import hashlib
import json
from pathlib import Path


def build_inputs(book, source_sha256):
    inputs, provenance = [], []
    cases = {case['id']: case for case in book['cases']}
    for extraction in book['unique_selected_extractions']:
        fields = sorted(extraction['fields'], key=lambda field: field['pointer'])
        premise = '\n\n'.join(
            '字段位置：' + field['pointer'] + '\n返回原文：' + field['quote']
            for field in fields
        )
        inputs.append({'id': extraction['id'], 'premise': premise,
                       'hypothesis': extraction['claim_text']})
        provenance.append({
            'id': extraction['id'], 'audit_target': extraction['audit_target'],
            'fields': fields, 'origins': extraction['origins'],
            'scope_caveats': list(dict.fromkeys(
                caveat for origin in extraction['origins']
                for caveat in cases[origin['id']]['scope_caveats'])),
        })
    return {
        'source_casebook_sha256': source_sha256,
        'candidate_serialization': 'original_pointer_and_quote_v1',
        'inference_fields': ['premise', 'hypothesis'], 'inputs': inputs,
        'provenance_not_for_model': provenance,
        'counts': {'cases': len(cases), 'unique_inputs': len(inputs),
                   'selection_origins': sum(len(p['origins']) for p in provenance)},
        'limits': [
            'Original fragments are preserved without subject restoration.',
            'Selected fields cannot prove full-source absence or list exhaustiveness.',
            'No status, reason, assessment or NLI label is an inference input.',
            'Public-model choice and execution remain pending user confirmation.',
        ],
        'model_requests': 0, 'new_labels': 0, 'training_records_added': 0,
    }


def prepare(book_path, output_path):
    raw = book_path.read_bytes()
    result = build_inputs(json.loads(raw), hashlib.sha256(raw).hexdigest())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('x', encoding='utf8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')
    return {'sha256': hashlib.sha256(output_path.read_bytes()).hexdigest(),
            **result['counts'], 'model_requests': 0, 'new_labels': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('casebook', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.casebook, args.output)))
