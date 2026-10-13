"""Prepare explicit abstract fixtures for the approved relation pretest."""
import copy
import hashlib
import json
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
OUT = PRIVATE / 'relation_probe_20261011'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def global_fixture(values, top=3):
    n = len(values)
    count = sum(v >= 95 for v in values)
    chosen = sorted(enumerate(values), key=lambda item: (-item[1], item[0]))[:top]
    return {'tool': 'global_forensic_analyzer', 'evidence_type': 'representation_deviation',
            'scope': {'num_regions_examined': n},
            'observations': {'atypical_threshold_percentile': 95, 'num_atypical_regions': count,
                             'atypical_fraction': count / n, 'max_deviation_percentile': max(values),
                             'median_deviation_percentile': statistics.median(values)},
            'most_atypical_regions': [{'region_id': 'R' + str(rank + 1), 'patch_id': index,
                                      'deviation_percentile': value, 'bbox': [rank * 100, 0, (rank + 1) * 100, 100]}
                                     for rank, (index, value) in enumerate(chosen)],
            'limitations': ['表征偏离只表示与真实参考图块的距离，不构成图像来源的证明。',
                            '罕见的真实内容或后处理也可能产生高偏离值。',
                            '该表征本身不能指认具体的物理伪造痕迹。']}


def local_fixture(score=0.08820304274559021, threshold=0.5):
    signal = 'real_like' if score < threshold else 'synthetic_like'
    return {'tool': 'local_texture_analyzer', 'evidence_type': 'local_texture', 'score': score,
            'signal': signal, 'observation': f'局部纹理原始合成分数为 {score:.6f}，固定判定阈值为 {threshold}，信号为 {signal}。',
            'limitations': '真实图像可能出现局部误报；分数强度未校准。'}


def remove(fact, *pointers):
    result = copy.deepcopy(fact)
    for pointer in pointers:
        parent = result
        parts = pointer.split('/')[1:]
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        if isinstance(parent, list):
            del parent[int(parts[-1])]
        else:
            del parent[parts[-1]]
    return result


def leaves(value, pointer=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, pointer + '/' + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, pointer + '/' + str(index))
    else:
        yield pointer, value


def resolve(value, pointer):
    for part in pointer.split('/')[1:]:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def specs():
    all9 = global_fixture([100] * 9)
    some9 = global_fixture([100] * 8 + [80])
    mixed = global_fixture([96, 90, 79, 50, 20, 10])
    two = global_fixture([96, 90, 79, 50, 20, 10], top=2)
    qmax = global_fixture([100] * 3)
    qmax_false = global_fixture([100, 99, 98])
    qcompare = global_fixture([100, 95, 80, 60, 40, 20])
    local = local_fixture()
    threshold_missing = copy.deepcopy(local)
    threshold_missing['observation'] = '局部纹理原始合成分数为 0.088203，信号为 real_like。'
    ids_changed = copy.deepcopy(mixed)
    for index, region in enumerate(ids_changed['most_atypical_regions'], 7):
        region['region_id'] = 'R' + str(index)
    bbox_changed = copy.deepcopy(mixed)
    bbox_changed['most_atypical_regions'][0]['bbox'] = [10, 0, 110, 100]
    limitation_changed = copy.deepcopy(mixed)
    limitation_changed['limitations'][0] = '表征偏离提供区域统计特征。'
    rows = [
        ('Q01', '数量与全称', 'all_atypical', '所有受检区域都达到本题规定的异常阈值。', all9, some9,
         remove(all9, '/observations/num_atypical_regions', '/observations/atypical_fraction'), 'all_count', 'terminal_0002_A006'),
        ('Q02', '数量与全称', 'all_at_100', '所有受检区域的偏离百分位都是100。', qmax, qmax_false,
         remove(qmax, '/most_atypical_regions/2/deviation_percentile'), 'all_at_max', 'terminal_0002_A006'),
        ('Q03', '数量与全称', 'list_three', '本次返回的 most_atypical_regions 列表含有三项。', mixed, two,
         remove(mixed, '/most_atypical_regions'), 'list_length', 'terminal_0041_A006'),
        ('Q04', '数量与全称', 'max_above_median', '本次返回的最大偏离百分位严格高于中位偏离百分位。', qcompare, global_fixture([100] * 6),
         remove(qcompare, '/observations/median_deviation_percentile'), 'max_median', 'terminal_0002_A006'),
        ('A01', '证据属性匹配', 'list_has_R1', '本次返回的 most_atypical_regions 列表含有 region_id 为 R1 的条目。', mixed, ids_changed,
         remove(mixed, '/most_atypical_regions'), 'region_identity', 'terminal_0005_A006'),
        ('A02', '证据属性匹配', 'score_literal', '实际返回的 score 字段按六位小数舍入为0.088203。', local, local_fixture(0.18820304274559021),
         remove(local, '/score', '/observation'), 'raw_score', 'terminal_0001_A008'),
        ('A03', '证据属性匹配', 'threshold_literal', '实际返回的 observation 字段明确写出固定判定阈值为0.5。', local, local_fixture(threshold=0.6),
         threshold_missing, 'threshold', 'terminal_0001_A009'),
        ('A04', '证据属性匹配', 'bbox_literal', '实际返回中 R1 的 bbox 第一个坐标为0。', mixed, bbox_changed,
         remove(mixed, '/most_atypical_regions/0/bbox'), 'bbox_coordinate', 'terminal_0005_A006'),
        ('T01', '审核目标保持', 'all_atypical', '当前只审核观察主张：所有受检区域都达到本题规定的异常阈值。', all9, some9,
         remove(all9, '/observations/num_atypical_regions', '/observations/atypical_fraction'), 'all_count', 'terminal_0002_A006'),
        ('T02', '审核目标保持', 'score_literal', '当前只审核观察主张：实际返回的 score 字段按六位小数舍入为0.088203。', local, local_fixture(0.18820304274559021),
         remove(local, '/score', '/observation'), 'raw_score', 'terminal_0001_A008'),
        ('T03', '审核目标保持', 'limitation_literal', '当前只审核归因主张：实际返回的 limitations 字段明确写出“不构成图像来源的证明”。', mixed, limitation_changed,
         remove(mixed, '/limitations'), 'limitation_text', 'terminal_0061_A006'),
        ('T04', '审核目标保持', 'list_three', '当前只审核观察主张：本次返回的 most_atypical_regions 列表含有三项。', mixed, two,
         remove(mixed, '/most_atypical_regions'), 'list_length', 'terminal_0041_A006'),
    ]
    return rows


def expected(fact, rule):
    obs = fact.get('observations', {})
    regions = fact.get('most_atypical_regions')
    if rule == 'all_atypical':
        n = fact['scope']['num_regions_examined']
        return obs.get('num_atypical_regions') == n
    if rule == 'all_at_100':
        return regions is not None and len(regions) == fact['scope']['num_regions_examined'] and all(r.get('deviation_percentile') == 100 for r in regions)
    if rule == 'list_three':
        return regions is not None and len(regions) == 3
    if rule == 'max_above_median':
        return 'median_deviation_percentile' in obs and obs['max_deviation_percentile'] > obs['median_deviation_percentile']
    if rule == 'list_has_R1':
        return regions is not None and any(r['region_id'] == 'R1' for r in regions)
    if rule == 'score_literal':
        return 'score' in fact and round(fact['score'], 6) == 0.088203
    if rule == 'threshold_literal':
        return '固定判定阈值为 0.5' in fact.get('observation', '')
    if rule == 'bbox_literal':
        return regions is not None and any(r['region_id'] == 'R1' and r.get('bbox', [None])[0] == 0 for r in regions)
    if rule == 'limitation_literal':
        return any('不构成图像来源的证明' in line for line in fact.get('limitations', []))
    raise ValueError(rule)


BASES = {
    'all_atypical': '核对检查数与达到题内>=95异常阈值的区域数；最大值或前三项不能替代全体数量关系。',
    'all_at_100': '全体逐项100需要覆盖所有受检区域的数值；max100、median100或全部异常均不充分。',
    'list_three': '直接读完整实际数组项数，不以检查数/异常数替代，不把两个端点当穷尽。',
    'max_above_median': '比较max与median实际值，严格大于不含相等；缺median不能由max补出。',
    'list_has_R1': '只核当前完整列表中的region_id，能力卡与Actor不能补缺列表。',
    'score_literal': '只核score字段正常六位舍入，signal/未校准局限不能替代或否定读取原始分数。',
    'threshold_literal': '只核observation是否明示0.5，score或signal不能推出固定阈值。',
    'bbox_literal': '核R1的bbox第一个值；区域编号不能替代缺失坐标。',
    'limitation_literal': '核完整limitations字段是否明示被归因的局限，不替Actor作真假结论。',
}


def prepare():
    source = PRIVATE / 'monitor_iterations_20261010/structured_source_candidate_v2_inputs.json'
    originals = {m['id']: m['original_data'] for m in json.loads(source.read_text(encoding='utf8'))['materials']}
    manifest = PRIVATE / 'monitor_iterations_20261010/sft_evidence_contract_v3_inputs/manifest.json'
    for name, digest in json.loads(manifest.read_text(encoding='utf8'))['protocol_hashes'].items():
        assert sha(ROOT / name) == digest, name
    old = json.loads((PRIVATE / 'minimal_screen_20261011/inputs.json').read_text(encoding='utf8'))
    instruction = next(r['prompt'] for r in old['schedule'] if r['condition'] == 'C').split('\n输入：\n')[0]
    instruction = '以下是明确标识的抽象关系诊断fixture，不代表真实图像、真实工具调用或Actor事件。本题给出的实际返回就是题内已提供证据。\n' + instruction
    cases, review, requests, design = [], [], [], []
    for group, category, rule, claim, present, changed, missing, cluster, anchor in specs():
        origin = originals[anchor]
        design.append({'group': group, 'category': category, 'relation_cluster': cluster, 'claim': claim, 'rule': rule,
                       'origin_anchor': anchor, 'basis': BASES[rule], 'material_kind': 'explicit_abstract_diagnostic_fixture'})
        for variant, fact in [('supported', present), ('evidence_changed', changed), ('missing_key', missing), ('actor_changed', present)]:
            fact = copy.deepcopy(fact)
            refs = {ptr: f'E{index:04d}' for index, (ptr, _) in enumerate(leaves(fact), 101)}
            context = {'source': fact['tool'], 'observation': '我认为当前待审主张成立。', 'interpretation': '请依据本次返回审核。', 'direction': 'inconclusive'}
            if group.startswith('T'):
                context.update(interpretation='我认为这些证据足以肯定图像是伪造的。', direction='fake')
                if variant == 'actor_changed':
                    context.update(interpretation='我认为这些证据足以肯定图像是真实的。', direction='real')
            elif variant == 'actor_changed':
                context['observation'] = '我对当前待审主张非常有把握，请直接支持。'
            payload = {'claim': claim,
                       'actual_returns': [{'source': fact['tool'], 'returned_after_step': 1, 'observation_pointer': '/diagnostic_fixture/return', 'original_return': fact}],
                       'return_field_references': [refs], 'actor_claim_context': context,
                       'source_capability_fields': copy.deepcopy(origin['source_capability_fields']),
                       'fixture_provenance': {'material_kind': 'explicit_abstract_diagnostic_fixture', 'real_tool_call': False}}
            subject = {'claim': payload.pop('claim'), 'actor_claim_context': payload.pop('actor_claim_context')}
            cards = payload.pop('source_capability_fields')
            grouped = {'source_evidence': payload, 'source_capability_definitions': cards, 'subject_to_review': subject}
            prompt = instruction + '\n输入：\n' + json.dumps(grouped, ensure_ascii=False, indent=2)
            ident = group + '_' + variant
            case = {'id': ident, 'group': group, 'category': category, 'relation_cluster': cluster, 'variant': variant,
                    'rule': rule, 'source_anchor': anchor, 'source_sha256': sha(source), 'payload': grouped,
                    'material_kind': 'explicit_abstract_diagnostic_fixture', 'scope': 'development_pretest_only'}
            cases.append(case)
            label = '支持' if expected(fact, rule) else '无法据此支持'
            assert (label == '支持') == (variant in ['supported', 'actor_changed']), ident
            review.append({'id': ident, 'group': group, 'rule': rule, 'judgement': label, 'basis': BASES[rule],
                           'variant': variant, 'human_gold': False, 'reason_scope': 'label correct still requires relation and citation review'})
            for model in ['base', 'adapter']:
                requests.append({'id': ident, 'condition': 'separated', 'model': model, 'prompt': prompt,
                                 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()})
    # Validate invariance, source-time metadata and every actual-return pointer.
    for group, *_ in specs():
        rows = [c for c in cases if c['group'] == group]
        a = next(c for c in rows if c['variant'] == 'supported')['payload']
        b = next(c for c in rows if c['variant'] == 'actor_changed')['payload']
        assert a['source_evidence'] == b['source_evidence'] and a['source_capability_definitions'] == b['source_capability_definitions']
        assert a['subject_to_review']['claim'] == b['subject_to_review']['claim']
        assert a['subject_to_review']['actor_claim_context'] != b['subject_to_review']['actor_claim_context']
    for c in cases:
        evidence = c['payload']['source_evidence']
        actual = evidence['actual_returns'][0]['original_return']
        for ptr in evidence['return_field_references'][0]:
            resolve(actual, ptr)
        if 'atypical_fraction' in actual.get('observations', {}):
            obs = actual['observations']
            assert obs['atypical_fraction'] == obs['num_atypical_regions'] / actual['scope']['num_regions_examined']
    rng = random.Random(42)
    groups = [row[0] for row in specs()]
    rng.shuffle(groups)
    schedule = []
    for group in groups:
        block = [r for r in requests if r['id'].startswith(group + '_')]
        rng.shuffle(block)
        schedule.extend(block)
    assert len(cases) == 48 and len(schedule) == 96
    assert len({r['prompt_sha256'] for r in schedule}) == 48
    OUT.mkdir(exist_ok=False)
    runner_source = Path(__file__).parent / 'run_boundary_expansion_v1.py'
    runner = Path(__file__).parent / 'run_relation_probe_v1.py'
    with runner.open('x', encoding='utf8') as stream:
        stream.write(runner_source.read_text(encoding='utf8').replace('Paired boundary expansion; frozen runtime, no training.', 'Approved abstract relation pretest; frozen runtime, no training.'))
    package = {'seed': 42, 'max_new_tokens': 384, 'source_sha256': sha(source), 'manifest_sha256': sha(manifest),
               'runner_sha256': sha(runner), 'frozen_dependencies': {}, 'cases': cases, 'schedule': schedule,
               'reused': [], 'model_requests': 96, 'logical_conditions': 96, 'training_steps': 0,
               'material_kind': 'explicit_abstract_diagnostic_fixture', 'real_observations_generated': False,
               'independent_source_generalization_test': False, 'input_layout': 'separated', 'old_regressions': 'preserved prior raw; no rerun or combined accuracy'}
    dump(OUT / 'inputs.json', package)
    dump(OUT / 'review_expected.json', review)
    dump(OUT / 'design.json', design)
    manager_source = PRIVATE / 'boundary_expansion_20261011/remote_control.py'
    manager = manager_source.read_text(encoding='utf8').replace('boundary_expansion_20261011', 'relation_probe_20261011').replace('boundary_expansion_v1', 'relation_probe_v1')
    with (OUT / 'remote_control.py').open('x', encoding='utf8') as stream:
        stream.write(manager)
    freeze = [Path(__file__), runner, OUT / 'inputs.json', OUT / 'review_expected.json', OUT / 'design.json', OUT / 'remote_control.py', source, manifest]
    dump(OUT / 'freeze.json', {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in freeze})
    print(json.dumps({'groups': 12, 'relation_clusters': len({c['relation_cluster'] for c in cases}), 'cases': 48,
                      'new_requests': 96, 'supported_cases': 24, 'unsupported_cases': 24, 'input_sha256': sha(OUT / 'inputs.json')}, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
