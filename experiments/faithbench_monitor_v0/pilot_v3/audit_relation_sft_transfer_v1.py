"""Posthoc trace of existing supervision and outputs; no new model requests or targets."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
RUN = PRIVATE / 'relation_sft_comparison_20261011'
MATERIAL = PRIVATE / 'relation_sft_materials_v2_20261011'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload(row):
    return json.loads(row['user_text'].split('\n输入：\n', 1)[1])


def projection(data, family):
    returned = data['source_evidence']['actual_returns'][0]['original_return']
    if family not in ['all_at_max', 'all_count']:
        return None
    # A descriptive projection for these numeric claims, not an input substitute.
    # Explicitly retain missingness; do not infer unreturned values.
    observations = returned.get('observations', {})
    return {'num_regions_examined': returned.get('scope', {}).get('num_regions_examined', 'MISSING'),
            'observations': {key: observations.get(key, 'MISSING') for key in ['atypical_threshold_percentile', 'num_atypical_regions', 'atypical_fraction', 'max_deviation_percentile', 'median_deviation_percentile']},
            'returned_percentiles': [row.get('deviation_percentile', 'MISSING') for row in returned.get('most_atypical_regions', [])] if 'most_atypical_regions' in returned else 'MISSING'}


def joint(row):
    return all(row[key] for key in ['label_correct', 'reason_correct', 'citation_sufficient', 'label_reason_consistent'])


def run():
    package = read(RUN / 'inputs.json')
    # Preserve authoritative pre/post checks and locked reviews.
    audit = read(RUN / 'final_stage_audit.json')
    for name, digest in audit['artifact_hashes'].items():
        assert sha(ROOT / name) == digest, name
    cases = read(MATERIAL / 'cases.json')
    train = package['train']['relation']
    families = sorted({row['family'] for row in train})
    reviews = read(RUN / 'first_review_locked.json')['rows']
    histories = read(PRIVATE / 'relation_prompt_probe_v1_20261011/inputs.json')['cases']
    by_case = {row['id']: row for row in cases + histories}
    summary = {}
    for model in ['base', 'ordinary', 'relation']:
        for scope in ['seen_48_fixed_regression', 'held_abstract_relation_development']:
            for covered in [True, False]:
                rows = [row for row in reviews if row['model'] == model and row['scope'] == scope and (row['family'] in families) == covered]
                summary[model + '/' + scope + '/' + ('family_in_train' if covered else 'family_not_in_train')] = {'n': len(rows), 'citation_joint': sum(joint(row) for row in rows)}
    logs = {}
    for method in ['ordinary', 'relation']:
        path = RUN / 'backup/relation_sft_comparison_v1_trial' / method / 'training.jsonl'
        logs[method] = [json.loads(line) for line in path.read_text().splitlines()]
        assert [row['id'] for row in logs[method]] == package['schedule']
    traced = []
    for row in reviews:
        if row['model'] == 'base' or joint(row):
            continue
        case = by_case[row['id']]
        family = row['family']
        candidates = [sample for sample in train if sample['family'] == family and sample['id'].endswith('_' + row['variant'])]
        traces = []
        for sample in candidates:
            data = payload(sample)
            updates = [item for item in logs[row['model']] if item['id'] == sample['id']]
            assert len(updates) == 3
            p = projection(data, family)
            traces.append({'training_id': sample['id'], 'target': sample['answer'], 'steps': [item['step'] for item in updates], 'third_exposure_loss_before_update': updates[-1]['loss'], 'claim_identical': data['subject_to_review']['claim'] == case['payload']['subject_to_review']['claim'], 'actor_context_identical': data['subject_to_review']['actor_claim_context'] == case['payload']['subject_to_review']['actor_claim_context'], 'numeric_projection_identical': p == projection(case['payload'], family) if p is not None else None})
        traced.append({'id': row['id'], 'model': row['model'], 'family': family, 'scope': row['scope'], 'failure_type': row['failure_type'], 'review_note': row['review_note'], 'family_in_train': family in families, 'same_variant_training_records': len(candidates), 'training_traces': traces, 'evaluation_projection': projection(case['payload'], family)})
    missing = {}
    for method in ['ordinary', 'relation']:
        missing[method] = {}
        mapping = {sample['id']: sample['family'] for sample in train}
        for family in families:
            selected = [row for row in logs[method] if row['epoch'] == 3 and row['id'].endswith('_missing_key') and mapping[row['id']] == family]
            missing[method][family] = {'records': len(selected), 'mean_loss_before_third_update': statistics.mean(row['loss'] for row in selected)}
    result = {'kind': 'posthoc_existing_material_and_log_trace_not_new_experiment', 'optimizer_steps': 0, 'model_requests': 0, 'actor_actions_executed': False,
              'training_families': families, 'coverage_counts': summary, 'new_adapter_joint_failures': len(traced), 'failure_traces': traced,
              'missing_training_loss': missing, 'training_direction_counts': dict(Counter(payload(row)['subject_to_review']['actor_claim_context']['direction'] for row in train)),
              'limits': ['Family coverage is not exact prompt equality or independent generalization.', 'Third-exposure loss was measured before that update, not on the final checkpoint.', 'Aggregate assistant loss does not locate label or evidence token errors; targets differ in length.', 'Projection removes IDs/coordinates but does not prove irrelevance of presentation or Actor context to model behavior.'],
              'source_hashes': {path.relative_to(ROOT).as_posix(): sha(path) for path in [RUN / 'inputs.json', RUN / 'first_review_locked.json', MATERIAL / 'cases.json', Path(__file__)]}}
    destination = RUN / 'posthoc_transfer_audit_v1.json'
    with destination.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'joint_failures_traced': len(traced), 'coverage_counts': summary, 'artifact_sha256': sha(destination)}, ensure_ascii=False))


if __name__ == '__main__':
    run()
