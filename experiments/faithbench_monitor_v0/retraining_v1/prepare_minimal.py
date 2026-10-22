"""Prepare six explicit projections from already exposed v3 material; no model execution."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
SOURCE = PRIVATE / 'retraining_a0_20261016'
OUT = PRIVATE / 'retraining_minimal_20261016'
MARKER = '\n待审核数据：\n'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def project_return(item, pointers):
    if pointers is None:
        return copy.deepcopy(item)
    reduced = copy.deepcopy(item)
    reduced['original_return'] = {}
    selected = {}
    for pointer in pointers:
        parts = pointer.strip('/').split('/')
        source = item['original_return']
        for part in parts:
            source = source[int(part)] if isinstance(source, list) else source[part]
        cursor = reduced['original_return']
        for index, part in enumerate(parts[:-1]):
            following_is_index = parts[index + 1].isdigit()
            if isinstance(cursor, list):
                position = int(part)
                while len(cursor) <= position:
                    cursor.append({})
                cursor = cursor[position]
            else:
                cursor = cursor.setdefault(part, [] if following_is_index else {})
        if isinstance(cursor, list):
            raise ValueError('Leaf-list projection is not needed for these cases')
        cursor[parts[-1]] = copy.deepcopy(source)
        selected[pointer] = item['field_references'][pointer]
    reduced['field_references'] = selected
    return reduced


def main():
    if OUT.exists():
        raise FileExistsError('Never overwrite a prepared diagnostic')
    originals = {row['id']: row for row in read(SOURCE / 'historical_v3.json') if row['model'] == 'base'}
    # The negative/unknown cases preserve complete same-source returns.
    selections = {
        'terminal_0005_A006': ('R1 区域', ['/most_atypical_regions/0/region_id']),
        'terminal_0005_A007': ('R1 区域（门牌号附近）', None),
        'terminal_0001_A007': ('R3为云层。', None),
        'terminal_0001_A009': ('固定判定阈值为 0.5', ['/observation']),
        'terminal_0002_A006': ('所有9个检查区域均高度偏离真实参考分布',
            ['/scope/num_regions_examined', '/observations/num_atypical_regions',
             '/observations/atypical_fraction', '/observations/max_deviation_percentile',
             '/observations/median_deviation_percentile']),
        'terminal_0041_A006_missing_list': ('检测到3个区域', None),
    }
    requests, provenance = [], []
    for case_id, (observation, pointers) in selections.items():
        original = originals[case_id]
        prefix, encoded = original['user_text'].split(MARKER, 1)
        data = json.loads(encoded)
        compact = copy.deepcopy(data)
        compact['actor_claim_context'] = {'source': data['actor_claim_context']['source'], 'observation': observation}
        compact['source_capability_fields'] = {}
        compact['prior_source_returns'] = [project_return(item, pointers) for item in data['prior_source_returns']]
        selected_ids = {ref for item in compact['prior_source_returns'] for ref in item['field_references'].values()}
        compact['claim_reference_ids'] = [ref for ref in data['claim_reference_ids'] if ref in selected_ids]
        compact['material_scope'] = {'kind': 'human_selected_existing_development_projection',
            'complete_same_source_returns_preserved': pointers is None,
            'new_tool_call': False, 'not_an_independent_test': True}
        if pointers is None:
            assert compact['prior_source_returns'] == data['prior_source_returns']
        assert compact['text'] == data['text'] and compact['audit_target'] == data['audit_target']
        prompt = prefix + MARKER + json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        for model in ('base', 'v3_adapter'):
            requests.append({'id': case_id, 'model': model, 'view': 'selected_minimal_evidence', 'user_text': prompt})
        provenance.append({'id': case_id, 'selected_pointers': pointers,
            'complete_return_preserved': pointers is None, 'source_component': data['case_id'],
            'actor_observation_excerpt': observation, 'selection_is_human_assisted': True})
    assert len(requests) == 12
    OUT.mkdir()
    for name, value in [('requests.json', requests), ('provenance.json', provenance),
        ('parameters.json', {'seed': 42, 'max_new_tokens': 384, 'new_generations_limit': 12,
            'quantization': 'NF4_double_bf16', 'attention': 'sdpa',
            'training_updates': 0, 'teacher_api_calls': 0, 'expected_gpu_minutes': [3, 5],
            'hard_wall_minutes': 10, 'source_scope': 'six_existing_exposed_v3_items',
            'purpose': 'conditional basic verification with manually selected evidence',
            'gold': False, 'independent_test': False})]:
        with (OUT / name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'prepared_requests': 12, 'complete_return_negative_unknown_cases': 3,
        'known_field_positive_projections': 3, 'new_generations': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
