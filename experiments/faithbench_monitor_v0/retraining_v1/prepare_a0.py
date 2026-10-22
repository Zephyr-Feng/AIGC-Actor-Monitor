"""Index exposed development results and prepare a bounded diagnostic, without model calls."""
import argparse
import copy
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
MARKER = '\n待审核数据：\n'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def reduced_prompt(original):
    """Remove Actor interpretation/direction, preserving the claim, observations and evidence."""
    instruction, encoded = original.split(MARKER, 1)
    payload = json.loads(encoded)
    reduced = copy.deepcopy(payload)
    context = reduced['actor_claim_context']
    for key in ('interpretation', 'direction'):
        context.pop(key, None)
    assert context == {k: v for k, v in payload['actor_claim_context'].items()
                       if k not in ('interpretation', 'direction')}
    assert {k: v for k, v in reduced.items() if k != 'actor_claim_context'} == {
        k: v for k, v in payload.items() if k != 'actor_claim_context'}
    return instruction + MARKER + json.dumps(reduced, ensure_ascii=False, sort_keys=True)


def index_relation():
    directory = PRIVATE / 'relation_sft_comparison_20261011'
    package = read(directory / 'inputs.json')
    prompts = {row['id']: row['user_text'] for row in package['held'] + package['regression']}
    expected = {row['id']: row['expected_judgement'] for row in package['held'] + package['regression']}
    reviews = {(row['model'], row['id']): row for row in read(directory / 'first_review_locked.json')['rows']}
    outputs = read(directory / 'combined_predictions.json')
    runtime = read(directory / 'backup/relation_sft_comparison_v1_trial/runtime.json')
    rows = []
    for offset, output in enumerate(outputs):
        review = reviews[(output['model'], output['id'])]
        rows.append({
            'experiment': 'relation_sft_comparison_20261011', 'id': output['id'],
            'model': output['model'], 'group': review['group'], 'family': review['family'],
            'variant': review['variant'], 'scope': output['scope'],
            'input_pointer': f'inputs.json:held_or_regression:{output["id"]}',
            'output_pointer': f'combined_predictions.json:{offset}',
            'input_characters': len(prompts[output['id']]),
            'expected_judgement': expected[output['id']],
            'parse_valid': output.get('parse_valid', False),
            'historical_joint_pass': all(review.get(key, False) for key in
                ('label_correct', 'reason_correct', 'citation_sufficient', 'label_reason_consistent')),
            'historical_failure_type': review.get('failure_type'),
            'output_tokens': output['output_tokens'], 'seconds': output['seconds'],
        })
    assert len(rows) == 252 and len(prompts) == 84
    assert Counter(row['model'] for row in rows) == {'base': 84, 'ordinary': 84, 'relation': 84}
    metadata = {key: runtime[key] for key in ('seed', 'quantization', 'attention', 'max_new_tokens')}
    return rows, metadata


def prepare(destination):
    if destination.exists():
        raise FileExistsError('Use a new preparation directory; never overwrite an existing run.')
    if not destination.resolve().is_relative_to(PRIVATE.resolve()):
        raise ValueError('Preparation output must stay in the private development directory.')
    iterations = PRIVATE / 'monitor_iterations_20261010'
    source = iterations / 'sft_evidence_contract_v3_inputs'
    backup = iterations / 'sft_evidence_contract_v3_backup/evidence_contract_v3_trial'
    evaluations = read(source / 'evaluation.json')
    source_train_ids = {row['id'] for row in read(source / 'train.json')}
    before, after = read_lines(backup / 'before.jsonl'), read_lines(backup / 'after.jsonl')
    assert len(evaluations) == len(before) == len(after) == 13
    expected_ids = {row['id'] for row in evaluations}
    assert {row['id'] for row in before} == {row['id'] for row in after} == expected_ids
    before_by_id = {row['id']: row for row in before}
    after_by_id = {row['id']: row for row in after}
    requests, references, historical = [], [], []
    for row in evaluations:
        payload = json.loads(row['user_text'].split(MARKER, 1)[1])
        reduced = reduced_prompt(row['user_text'])
        assert reduced != row['user_text']
        for model in ('base', 'v3_adapter'):
            requests.append({'id': row['id'], 'model': model, 'view': 'without_actor_interpretation',
                             'user_text': reduced})
        references.append({'id': row['id'], 'source_component': payload['case_id'],
            'audit_target': payload['audit_target'], 'claim': payload['text'],
            'old_training_recall': row['id'] in source_train_ids,
            'provisional_target': row['answer'],
            'reference_status': 'inherited_assistant_reviewed_development_reference_not_human_gold',
            'prior_source_returns': payload['prior_source_returns'],
            'source_capability_fields': payload['source_capability_fields']})
        for model, output in [('base', before_by_id[row['id']]), ('v3_adapter', after_by_id[row['id']])]:
            historical.append({'id': row['id'], 'model': model, 'view': 'original_full_audit_packet',
                'user_text': row['user_text'], 'raw': output['raw'],
                'seconds': output['seconds'], 'input_tokens': output['input_tokens'],
                'output_tokens': output['output_tokens'], 'max_new_tokens': output['max_new_tokens'],
                'parse_valid': output.get('parse_valid', False),
                'status_matches_old_target': output.get('status_matches_provisional_target', False)})
    relation_rows, relation_runtime = index_relation()
    runtime = read(backup / 'runtime.json')
    seed = runtime['seed']
    assert seed == 42 and runtime['max_evaluation_new_tokens'] == 384
    # Two fixed anchors per model check compatibility with old in-memory outputs first.
    anchor_ids = ('terminal_0005_A006', 'terminal_0041_A006_missing_list')
    anchors = [dict(row, view='reload_anchor') for row in historical if row['id'] in anchor_ids]
    assert len(anchors) == 4
    parameters = {'seed': seed, 'quantization': runtime['quantization'], 'attention': 'sdpa',
        'max_new_tokens': 384, 'do_sample': False,
        'adapter': '/root/autodl-tmp/monitor-sft-smoke-20261010/evidence_contract_v3_trial/adapter',
        'base_cache': '/root/autodl-tmp/mini-faithbench-v0/model-cache/models--Qwen--Qwen3-VL-8B-Instruct',
        'new_generations_limit': 30, 'reload_anchors': 4, 'reduced_generations': 26,
        'reused_full_generations': 26, 'training_updates': 0,
        'expected_gpu_minutes': [5, 10], 'hard_wall_minutes': 15,
        'stop_on_anchor_mismatch': True, 'human_gold': False, 'independent_test': False,
        'source_scope': '13_previously_exposed_v3_development_items_only',
        'not_a_complete_trajectory_test': True,
        'view_definition': 'remove interpretation and direction only; preserve Actor observation, source, all original returns/cards/IDs',
        'historical_generation_seconds': sum(row['seconds'] for row in historical)}
    summary = {'existing_relation_outputs': len(relation_rows), 'existing_relation_inputs': 84,
        'existing_v3_outputs': len(historical), 'existing_v3_inputs': len(evaluations),
        'v3_source_components': sorted({row['source_component'] for row in references}),
        'v3_training_recall_items': len(source_train_ids),
        'relation_joint_pass_by_model': {model: sum(row['historical_joint_pass'] for row in relation_rows
            if row['model'] == model) for model in ('base', 'ordinary', 'relation')},
        'relation_runtime': relation_runtime, 'proposed_new_generations': 30,
        'prepared_reduced_requests': len(requests), 'executed_new_generations': 0,
        'reserved_sources_read': False, 'ground_truth_read': False, 'teacher_api_calls': 0,
        'historical_reviews_are_not_independent_gold': True,
        'interpretation': 'The reduced view isolates Actor interpretation/direction interference; it is not a fully minimized evidence packet.'}
    destination.mkdir(parents=True)
    write(destination / 'existing_result_index.json', relation_rows)
    write(destination / 'historical_v3.json', historical)
    write(destination / 'reference_cards.json', references)
    write(destination / 'requests.json', requests)
    write(destination / 'anchors.json', anchors)
    write(destination / 'parameters.json', parameters)
    write(destination / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output)
