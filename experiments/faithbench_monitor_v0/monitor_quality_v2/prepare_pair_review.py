"""Prepare saved before/after feedback for source-based review; never call a model."""
import argparse
import json
from pathlib import Path

from assemble_feedback import assemble
from prepare_review import rows


def inspect_output(output, material):
    if output is None:
        return {'output_present': False, 'json_parsed': None, 'contract_and_anchors_valid': None}
    parsed = False
    try:
        payload = json.loads(output['raw'])
        parsed = True
        checked = assemble(material['待核回答'], material['证据卡'], payload)
        assert checked['semantic_verified'] is False
        valid, error = True, None
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        valid, error = False, str(exc)
    assert valid == output['source_anchors_valid'], output['id']
    return {'output_present': True, 'json_parsed': parsed, 'contract_and_anchors_valid': valid,
        'validation_failure': error, 'hit_token_cap': output['hit_token_cap'], 'semantic_verified': False}


def run(pack, saved, before_reviews, output):
    inputs = rows(pack / 'proposed_development.inputs.jsonl')
    references = rows(pack / 'proposed_development.references.jsonl')
    before = rows(saved / 'before.jsonl')
    after = rows(saved / 'after.jsonl') if (saved / 'after.jsonl').exists() else []
    reviews = rows(before_reviews)
    ids = [r['id'] for r in inputs]
    assert len(ids) == len(set(ids)) == 80
    assert [r['id'] for r in references] == [r['id'] for r in before] == [r['id'] for r in reviews] == ids
    assert len(after) <= 80 and [r['id'] for r in after] == ids[:len(after)], 'after must be the original ordered prefix'
    assert all(r['raw_modified'] is False and r['human_gold'] is False for r in reviews)
    packets = []
    for index, (inp, ref, old, review) in enumerate(zip(inputs, references, before, reviews)):
        material = json.loads(inp['messages'][-1]['content'])
        new = after[index] if index < len(after) else None
        packets.append({'id': inp['id'], 'group': inp['group'], 'source_and_answer': material,
            'reference_preserved': ref, 'before': old, 'after': new,
            'before_interface': inspect_output(old, material), 'after_interface': inspect_output(new, material),
            'before_review_nonblind': review, 'after_review_status': 'not_reviewed' if new else 'pending_output',
            'after_content_review': None, 'paired_content_assessment': None,
            'human_gold': False, 'independent_validation': False})
    summary = {'expected_rows': 80, 'before_rows': len(before), 'after_rows': len(after),
        'missing_after_rows': 80 - len(after), 'paired_content_reviews_completed': 0,
        'review_ready': len(after) == 80, 'new_model_calls': 0, 'raw_modified': False,
        'quality_improvement_proven': False, 'independent_validation': False,
        'note': 'Missing outputs and unreviewed content stay pending; interface validity never proves semantics.'}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'review_packets.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in packets), encoding='utf8')
    (output / 'preparation.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    parser.add_argument('--before-reviews', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.pack, args.saved, args.before_reviews, args.output), ensure_ascii=False))
