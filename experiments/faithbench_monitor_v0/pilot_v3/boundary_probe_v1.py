"""Input-boundary and local citation-role probe, using approved existing controls."""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
OUT = PRIVATE / 'boundary_probe_20261011'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    with path.open('x', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def local_gate(row, payload, requirement):
    """Only validates this declared attribute family; not a general semantic judge."""
    if row['condition'] == 'A':
        return 'not_applicable_no_reference_contract'
    if not row.get('parse_valid'):
        return 'blocked_invalid_format'
    parsed = row['parsed']
    if parsed['judgement'] != '支持':
        return 'negative_output_no_positive_gate'
    refs = parsed.get('return_reference_ids', [])
    catalog = {}
    for group, mapping in zip(payload['actual_returns'], payload['return_field_references'], strict=True):
        for pointer, eid in mapping.items():
            value = group['original_return']
            for part in pointer.split('/')[1:]:
                value = value[int(part)] if isinstance(value, list) else value[part]
            catalog[eid] = (pointer, value)
    if not refs or any(e not in catalog for e in refs):
        return 'blocked_missing_or_invalid_return_reference'
    if requirement == 'region_id_R1':
        return 'eligible_local_identity' if any(catalog[e][0].endswith('/region_id') and catalog[e][1] == 'R1' for e in refs) else 'blocked_attribute_mismatch'
    if requirement == 'threshold_literal':
        return 'eligible_local_literal' if any(catalog[e][0] == '/observation' and '固定判定阈值为 0.5' in str(catalog[e][1]) for e in refs) else 'blocked_attribute_mismatch'
    if requirement == 'object_content':
        # Existing schema: numbers, geometry, IDs, paths and reference metadata.
        def is_nonsemantic(pointer):
            known_leaf = {'crop_path', 'deviation_percentile', 'grid_col', 'grid_row', 'patch_id', 'region_id'}
            region_structural = pointer.startswith('/most_atypical_regions/') and ('/bbox/' in pointer or pointer.rsplit('/', 1)[-1] in known_leaf)
            return region_structural or pointer.startswith(('/observations/', '/reference/', '/scope/')) or pointer in ['/tool', '/sample_id', '/evidence_type']
        if all(is_nonsemantic(catalog[e][0]) for e in refs):
            return 'blocked_attribute_mismatch'
        return 'unverified_semantic_support'
    return 'unverified_requirement'


def prepare():
    OUT.mkdir(exist_ok=False)
    prior_dir = PRIVATE / 'minimal_screen_20261011'
    prior = json.loads((prior_dir / 'inputs.json').read_text(encoding='utf8'))
    old_rows = [json.loads(s) for s in (prior_dir / 'backup/minimal_screen_v1_trial/predictions.jsonl').read_text(encoding='utf8').splitlines()]
    old_source = PRIVATE / 'monitor_iterations_20261010/structured_source_candidate_v2_inputs.json'
    source = json.loads(old_source.read_text(encoding='utf8'))
    originals = {r['id']: r['original_data'] for r in source['materials']}
    cloud = originals['terminal_0001_A007']
    template = next(r['prompt'] for r in prior['schedule'] if r['id'] == 'terminal_0001_A007' and r['condition'] == 'C')
    instruction, body = template.split('\n输入：\n')
    original_payload = json.loads(body)
    missing = originals['terminal_0041_A006_missing_list']['prior_source_returns'][0]
    full_return = cloud['prior_source_returns'][0]['original_return']
    assert {k: v for k, v in full_return.items() if k != 'most_atypical_regions'} == missing['original_return']
    requests, reuse, cases = [], [], []
    for context in ['original', 'certain', 'tentative', 'card_only']:
        payload = copy.deepcopy(original_payload)
        if context == 'certain':
            payload['actor_claim_context']['observation'] = payload['actor_claim_context']['observation'].replace('R3为云层', 'R3肯定为云层')
        elif context == 'tentative':
            payload['actor_claim_context']['observation'] = payload['actor_claim_context']['observation'].replace('R3为云层', 'R3可能为云层')
        elif context == 'card_only':
            payload.pop('actor_claim_context')
        cases.append({'id': 'cloud_' + context, 'payload': payload, 'requirement': 'object_content', 'expected': '无法据此支持', 'origin': 'terminal_0001_A007; only declared Actor wording changes/removal'})
    for state in ['present', 'missing']:
        payload = copy.deepcopy(original_payload)
        payload['claim'] = '该工具的实际返回包含编号为 R1 的区域。'
        payload['actor_claim_context'] = {'source': 'global_forensic_analyzer', 'observation': '我肯定该工具的实际返回包含编号为 R1 的区域。', 'interpretation': 'R1是这次返回中的区域编号。', 'direction': 'inconclusive'}
        if state == 'missing':
            payload['actual_returns'][0]['original_return'] = copy.deepcopy(missing['original_return'])
            removed = '/most_atypical_regions/'
            payload['return_field_references'][0] = {k: v for k, v in payload['return_field_references'][0].items() if not k.startswith(removed)}
        cases.append({'id': 'r1_list_' + state, 'payload': payload, 'requirement': 'region_id_R1', 'expected': '支持' if state == 'present' else '无法据此支持', 'origin': 'derived diagnostic projection using existing blind_001 list deletion control; not a new real Actor event'})
    for case in cases:
        for condition in ['plain', 'separated']:
            payload = copy.deepcopy(case['payload'])
            if condition == 'separated':
                subject = {'claim': payload.pop('claim')}
                if 'actor_claim_context' in payload:
                    subject['actor_claim_context'] = payload.pop('actor_claim_context')
                cards = payload.pop('source_capability_fields')
                payload = {'source_evidence': payload, 'source_capability_definitions': cards, 'subject_to_review': subject}
            prompt = instruction + '\n输入：\n' + json.dumps(payload, ensure_ascii=False, indent=2)
            digest = hashlib.sha256(prompt.encode()).hexdigest()
            for model in ['base', 'adapter']:
                item = {'id': case['id'], 'condition': condition, 'model': model, 'prompt': prompt, 'prompt_sha256': digest}
                old = next((r for r in old_rows if r['prompt_sha256'] == digest and r['model'] == model), None)
                if old is not None:
                    reuse.append(item | {'old_record': old})
                else:
                    requests.append(item)
    rng = random.Random(42)
    case_ids = [c['id'] for c in cases]
    rng.shuffle(case_ids)
    schedule = []
    for ident in case_ids:
        block = [r for r in requests if r['id'] == ident]
        rng.shuffle(block)
        schedule.extend(block)
    assert len(schedule) == 22 and len(reuse) == 2
    runner = Path(__file__).parent / 'run_boundary_probe_v1.py'
    old_code = (Path(__file__).parent / 'minimal_screen_v1.py').read_text(encoding='utf8')
    code = old_code[:old_code.index('def prepare():')] + old_code[old_code.index('def run(args):'):]
    code = code.replace('len(schedule) == 24', 'len(schedule) == 22').replace('}) == 24', '}) == 22').replace("'predictions': 24", "'predictions': 22")
    code = code.replace("    parser.add_argument('--prepare', action='store_true')\n", '').replace('    prepare() if args.prepare else run(args)', '    run(args)')
    code = code.replace('"""Bounded coverage diagnostic; no training or Actor actions."""', '"""Boundary probe runner derived from minimal_screen_v1; 22 new requests."""')
    with runner.open('x', encoding='utf8') as f:
        f.write(code)
    package = {'seed': 42, 'max_new_tokens': 384, 'source_sha256': sha(old_source), 'manifest_sha256': prior['manifest_sha256'], 'runner_sha256': sha(runner), 'schedule': schedule, 'reused': reuse, 'cases': cases, 'model_requests': 22, 'logical_conditions': 24, 'training_steps': 0}
    dump(OUT / 'inputs.json', package)
    # Backtest a frozen, narrow role gate; no answers are changed or fed back.
    backtest = []
    for row in old_rows:
        data = originals[row['id']]
        payload = {'actual_returns': data['prior_source_returns'], 'return_field_references': [r['field_references'] for r in data['prior_source_returns']]}
        kind = {'terminal_0005_A006': 'region_id_R1', 'terminal_0001_A009': 'threshold_literal', 'terminal_0001_A007': 'object_content'}.get(row['id'], 'unverified_requirement')
        backtest.append({k: row[k] for k in ['id', 'condition', 'model']} | {'gate': local_gate(row, payload, kind)})
    dump(OUT / 'old_output_gate_backtest.json', backtest)
    print(json.dumps({'new_requests': len(schedule), 'reused': len(reuse), 'input_sha256': sha(OUT / 'inputs.json')}, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
