"""Structural assembly and compact evidence display; semantic judgements remain manual."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
HERE = PRIVATE / 'relation_sft_comparison_20261011'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def pointer(value, path):
    for part in path.strip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def case_map():
    package = read(HERE / 'inputs.json')
    held = {row['id']: row for row in read(PRIVATE / 'relation_sft_materials_v2_20261011/cases.json') if row['split'] == 'held'}
    historical = read(PRIVATE / 'relation_prompt_probe_v1_20261011/inputs.json')['cases']
    rows = {row['id']: row for row in package['regression']}
    cases = dict(held)
    for row in historical:
        cases[row['id']] = row | {'scope': 'seen_48_fixed_regression', 'judgement': rows[row['id']]['expected_judgement'], 'family': row['relation_cluster']}
    return cases


def display(predictions):
    cases = case_map()
    for row in predictions:
        case = cases[row['id']]
        payload = case['payload']
        returned = payload['source_evidence']['actual_returns'][0]['original_return']
        refs = payload['source_evidence']['return_field_references'][0]
        inverse = {value: key for key, value in refs.items()}
        parsed = row.get('parsed', {})
        selected = {value: {'pointer': inverse[value], 'value': pointer(returned, inverse[value])} if value in inverse else {'invalid': True} for value in parsed.get('return_reference_ids', [])}
        print(json.dumps({'id': row['id'], 'model': row['model'], 'claim': payload['subject_to_review']['claim'], 'target': case['judgement'], 'result': parsed or row['raw'], 'cited': selected}, ensure_ascii=False))


def assemble():
    package = read(HERE / 'inputs.json')
    backup = HERE / 'backup/relation_sft_comparison_v1_trial'
    completed = read(backup / 'completed.json')
    raw = backup / 'predictions.jsonl'
    assert sha(raw) == completed['predictions_sha256'] and completed['optimizer_steps'] == 432
    new = [json.loads(line) for line in raw.read_text(encoding='utf8').splitlines()]
    assert len(new) == 204 and len({(row['model'], row['id']) for row in new}) == 204
    for method in ['ordinary', 'relation']:
        train = [json.loads(line) for line in (backup / method / 'training.jsonl').read_text().splitlines()]
        assert [row['id'] for row in train] == package['schedule'] and [row['step'] for row in train] == list(range(1, 217))
    old = [row | {'scope': 'seen_48_fixed_regression', 'reused_historical_raw': True} for row in package['reused_base_regression']]
    combined = new + old
    assert len(combined) == 252
    dump(HERE / 'combined_predictions.json', combined)
    summary = {'new_requests': 204, 'reused_requests': 48, 'logical_conditions': 252, 'optimizer_steps': 432, 'exact_exposure_verified': True, 'format_valid': sum(row['parse_valid'] for row in combined), 'new_budget_exhaustions': sum(row['output_tokens'] >= 384 for row in new), 'new_input_range': [min(row['input_tokens'] for row in new), max(row['input_tokens'] for row in new)], 'new_output_range': [min(row['output_tokens'] for row in new), max(row['output_tokens'] for row in new)], 'new_generation_seconds': sum(row['seconds'] for row in new), 'raw_sha256': sha(raw), 'combined_sha256': sha(HERE / 'combined_predictions.json'), 'human_gold': False, 'actor_actions_executed': False}
    dump(HERE / 'structural_audit.json', summary)
    print(json.dumps(summary))


if __name__ == '__main__':
    assemble()
