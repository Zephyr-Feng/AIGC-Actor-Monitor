"""Prepare the approved 72/36 abstract materials, without model calls or training."""
import copy
import hashlib
import json
import random
from pathlib import Path

from relation_probe_v2 import ROOT, PRIVATE, global_fixture, local_fixture, remove, leaves, resolve, sha
from relation_prompt_probe_v1 import ORDER

OUT = PRIVATE / 'relation_sft_materials_v1_20261011'
SOURCE = PRIVATE / 'relation_probe_v2_20261011'
PROMPTS = PRIVATE / 'relation_prompt_probe_v1_20261011'
VARIANTS = ('supported', 'evidence_changed', 'missing_key', 'actor_changed')
KEYS = ('reason', 'return_reference_ids', 'judgement')
FAMILIES = (
    ('all_count', 'Q01', 'train'), ('all_at_max', 'Q02', 'train'),
    ('max_median', 'Q04', 'train'), ('raw_score', 'A02', 'train'),
    ('threshold', 'A03', 'train'), ('limitation_text', 'T03', 'train'),
    ('region_identity', 'A01', 'held'), ('bbox_coordinate', 'A04', 'held'),
    ('list_length', 'Q03', 'held'),
)


def dump(path, value):
    with path.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def canonical_answer(reason, refs, label):
    return dict(zip(KEYS, (reason, refs, label), strict=True))


def assistant_text(answer):
    # The final text has an explicit order independent of metadata serialization.
    return json.dumps({k: answer[k] for k in KEYS}, ensure_ascii=False, separators=(',', ':'))


def decorate(fact, parameter):
    fact = copy.deepcopy(fact)
    for rank, region in enumerate(fact.get('most_atypical_regions', [])):
        region['region_id'] = 'R' + str(12 + parameter * 4 + rank)
        left = parameter * 25 + rank * 110
        region['bbox'] = [left, 20, left + 100, 120]
    return fact


def specification(family, parameter):
    """Return observed cases and two compatible full completions for the missing case."""
    p = parameter
    params = {}
    projection = []
    positive_values = negative_values = None
    positive_top = negative_top = 3
    if family == 'all_count':
        n = (7, 8, 10)[p]
        positive_values = [99, 98, 96] + [95] * (n - 3)
        negative_values = positive_values[:-1] + [40 + p]
        positive = decorate(global_fixture(positive_values), p)
        negative = decorate(global_fixture(negative_values), p)
        projection = ['/observations/num_atypical_regions', '/observations/atypical_fraction']
        claim = '当前只审核观察主张：所有受检区域都达到本题规定的异常阈值。'
    elif family == 'all_at_max':
        positive_values = [100, 100, 100]
        negative_values = [100, 100, (96, 98, 99)[p]]
        positive = decorate(global_fixture(positive_values), p)
        negative = decorate(global_fixture(negative_values), p)
        projection = ['/most_atypical_regions/2/deviation_percentile']
        claim = '所有受检区域的偏离百分位都是100。'
    elif family == 'max_median':
        n = (6, 8, 10)[p]
        high, middle = (99, 98, 97)[p], (60, 55, 45)[p]
        positive_values = [high, high - 1] + [middle] * (n - 2)
        negative_values = [high] * n
        positive = decorate(global_fixture(positive_values), p)
        negative = decorate(global_fixture(negative_values), p)
        projection = ['/observations/median_deviation_percentile', '/observations/num_atypical_regions',
                      '/observations/atypical_fraction', '/most_atypical_regions']
        claim = '本次返回的最大偏离百分位严格高于中位偏离百分位。'
    elif family == 'raw_score':
        score = (0.1738422, 0.6271042, 0.8426192)[p]
        positive, negative = local_fixture(score), local_fixture(score + 0.1)
        params['target_score'] = f'{score:.6f}'
        projection = ['/score', '/observation']
        claim = f'当前只审核观察主张：实际返回的 score 字段按六位小数舍入为{score:.6f}。'
    elif family == 'threshold':
        score, threshold = (0.12, 0.31, 0.44)[p], (0.25, 0.55, 0.75)[p]
        positive, negative = local_fixture(score, threshold), local_fixture(score, threshold + 0.1)
        params.update(target_threshold=str(threshold), missing_observation=f'局部纹理原始合成分数为 {score:.6f}，信号为 real_like。')
        claim = f'实际返回的 observation 字段明确写出固定判定阈值为{threshold}。'
    else:
        positive_values = negative_values = [96 + p, 90, 79, 50, 20, 10, 5][:6 + (p == 2)]
        if family == 'list_length':
            positive_top, negative_top = (1, 2, 3)[p], (2, 3, 2)[p]
        positive = decorate(global_fixture(positive_values, top=positive_top), p)
        negative = decorate(global_fixture(negative_values, top=negative_top), p)
        if family == 'limitation_text':
            params.update(target_literal=positive['limitations'][p], limitation_index=p)
            negative['limitations'][p] = ('表征偏离提供区域统计特征。', '返回包含区域表征统计。', '返回包含定位信息。')[p]
            projection = ['/limitations']
            claim = f'当前只审核归因主张：实际返回的 limitations 字段明确写出“{params["target_literal"]}”。'
        elif family == 'region_identity':
            index, target = (2, 0, 1)[p], ('R2', 'R5', 'R8')[p]
            positive['most_atypical_regions'][index]['region_id'] = target
            params.update(target_region=target, region_index=index)
            projection = ['/most_atypical_regions']
            claim = f'本次返回的 most_atypical_regions 列表含有 region_id 为 {target} 的条目。'
        elif family == 'bbox_coordinate':
            index, target = (1, 2, 0)[p], ('R4', 'R7', 'R10')[p]
            positive['most_atypical_regions'][index]['region_id'] = target
            negative = copy.deepcopy(positive)
            coordinate = positive['most_atypical_regions'][index]['bbox'][0]
            negative['most_atypical_regions'][index]['bbox'][0] += 15
            negative['most_atypical_regions'][index]['bbox'][2] += 15
            params.update(target_region=target, region_index=index, target_coordinate=coordinate)
            projection = [f'/most_atypical_regions/{index}/bbox']
            claim = f'实际返回中 {target} 的 bbox 第一个坐标为{coordinate}。'
        elif family == 'list_length':
            params['target_count'] = positive_top
            projection = ['/most_atypical_regions']
            claim = f'当前只审核观察主张：本次返回的 most_atypical_regions 列表含有{positive_top}项。'
        else:
            raise ValueError(family)
    if family == 'threshold':
        missing = copy.deepcopy(positive)
        missing['observation'] = params['missing_observation']
    else:
        missing = remove(positive, *projection)
    return dict(family=family, parameter=p + 1, parameters=params, claim=claim,
                positive=positive, negative=negative, missing=missing, projection=projection,
                positive_values=positive_values, negative_values=negative_values,
                positive_top=positive_top, negative_top=negative_top)


def targets(spec, variant, fact):
    """Two correct reasons for the same judgement and the same sufficient references."""
    family, params = spec['family'], spec['parameters']
    supported, missing = variant in ('supported', 'actor_changed'), variant == 'missing_key'
    label = '支持' if supported else '无法据此支持'
    obs, regions = fact.get('observations', {}), fact.get('most_atypical_regions', [])
    if family == 'all_count':
        if missing:
            ordinary = '异常区域数和比例未给出，无法确认所有受检区域都达阈值。'
            relation = '支持全体达阈值需要异常区域数等于检查数；异常数和比例均缺失，前三项不能补足全体关系，无法据此支持。'
            pointers = []
        else:
            n, c, t = fact['scope']['num_regions_examined'], obs['num_atypical_regions'], obs['atypical_threshold_percentile']
            ordinary = f'检查{n}个区域，其中{c}个达到阈值{t}，因此' + ('全部受检区域都达阈值。' if supported else '并非全部受检区域都达阈值。')
            relation = f'全体达阈值要求num_atypical_regions等于num_regions_examined；实际阈值{t}对应异常数{c}、检查数{n}，' + ('两数相等，支持该主张。' if supported else '异常数小于检查数，不支持该主张。')
            pointers = ['/scope/num_regions_examined', '/observations/num_atypical_regions', '/observations/atypical_threshold_percentile']
    elif family == 'all_at_max':
        if missing:
            ordinary = '第三项偏离百分位未给出，无法确认全体都为100。'
            relation = '全体百分位100需要覆盖全部受检项的具体值；第三项缺值，max100、median100及全部异常均不能补出该值，无法据此支持。'
            pointers = []
        elif supported:
            ordinary = '受检总数为3，返回三项百分位分别为100、100、100，支持全体为100。'
            relation = '全体百分位100要求逐项值均为100且覆盖所有受检项；检查数3、完整三项均100，两个必要条件都满足，支持主张。'
            pointers = ['/scope/num_regions_examined'] + [f'/most_atypical_regions/{i}/deviation_percentile' for i in range(3)]
        else:
            value = regions[2]['deviation_percentile']
            ordinary = f'第三项偏离百分位为{value}而非100，不能支持全体为100。'
            relation = f'全体为100要求每项都等于100；第三项实际为{value}、不等于100，已有反例，因此无法据此支持。'
            pointers = ['/most_atypical_regions/2/deviation_percentile']
    elif family == 'max_median':
        if missing:
            ordinary = 'median_deviation_percentile未给出，无法判断最大值是否严格高于中位值。'
            relation = '严格高于要求比较实际max和median且不能接受相等；median缺失，不能从max推定比较结果，无法据此支持。'
            pointers = []
        else:
            high, middle = obs['max_deviation_percentile'], obs['median_deviation_percentile']
            ordinary = f'最大偏离百分位为{high}，中位偏离百分位为{middle:g}，' + ('前者严格更高。' if supported else '两者相等，未严格更高。')
            relation = f'主张要求max_deviation_percentile>median_deviation_percentile；实际{high}与{middle:g}，' + ('严格大于成立，支持。' if supported else '仅相等而非严格大于，无法据此支持。')
            pointers = ['/observations/max_deviation_percentile', '/observations/median_deviation_percentile']
    elif family == 'raw_score':
        target = params['target_score']
        if missing:
            ordinary = 'score及包含数值的observation未给出，无法核对六位小数。'
            relation = '支持该主张需实际score的六位舍入值与主张一致；score及数值说明均缺失，signal不能补出精确分数，无法据此支持。'
            pointers = []
        else:
            actual = f'{fact["score"]:.6f}'
            ordinary = f'实际score按六位小数为{actual}，' + ('与主张一致。' if supported else f'与主张{target}不符。')
            relation = f'支持该主张要求score按六位舍入等于{target}；实际为{actual}，' + ('两值相等，支持。' if supported else '两值不等，不能支持。')
            pointers = ['/score']
    elif family == 'threshold':
        target = params['target_threshold']
        if missing:
            ordinary = 'observation未明确写出固定判定阈值，无法支持该阈值归因。'
            relation = f'主张要求observation明确写出固定阈值{target}；实际说明只给分数与signal、没有阈值，不能从分数补齐，无法据此支持。'
        else:
            actual = fact['observation'].split('固定判定阈值为 ', 1)[1].split('，', 1)[0]
            ordinary = f'observation明确写出的固定判定阈值为{actual}，' + ('与主张一致。' if supported else f'并非主张的{target}。')
            relation = f'主张要求observation明示阈值{target}；实际字段明示{actual}，' + ('相等，支持。' if supported else '数值不等，无法据此支持。')
        pointers = ['/observation']
    elif family == 'limitation_text':
        target, index = params['target_literal'], params['limitation_index']
        if missing:
            ordinary = 'limitations字段未提供，无法确认返回明确写出所述局限。'
            relation = '该归因要求实际limitations明确提供所述局限；整个字段缺失，能力卡和Actor解释不能补出返回内容，无法据此支持。'
            pointers = []
        elif supported:
            ordinary = f'limitations实际写出“{target}”，支持当前归因。'
            relation = f'当前只核该局限是否由limitations明示；实际条目写出“{target}”，与所核归因对应，支持。'
            pointers = [f'/limitations/{index}']
        else:
            ordinary = f'完整limitations中未写出“{target}”，无法支持当前归因。'
            relation = f'归因要求limitations明示“{target}”；当前对应条目为“{fact["limitations"][index]}”，完整其余条目也未给该明示，无法据此支持。'
            pointers = [f'/limitations/{i}' for i in range(len(fact['limitations']))]
    elif family == 'region_identity':
        target, index = params['target_region'], params['region_index']
        if missing:
            ordinary = 'most_atypical_regions列表缺失，无法确认是否含有所述区域编号。'
            relation = '成员主张需要实际列表中的region_id与目标相同；列表未给出，能力定义和Actor说法不能补出成员，无法据此支持。'
            pointers = []
        elif supported:
            ordinary = f'实际列表第{index + 1}项region_id为{target}，支持该成员主张。'
            relation = f'存在性主张需至少一项region_id等于{target}；实际第{index + 1}项与目标相同，因此支持。'
            pointers = [f'/most_atypical_regions/{index}/region_id']
        else:
            actual = '、'.join(r['region_id'] for r in regions)
            ordinary = f'完整列表的region_id为{actual}，没有{target}，不能支持。'
            relation = f'成员主张需要列表中至少一个region_id等于{target}；完整列表为{actual}，均不相等，无法据此支持。'
            pointers = [f'/most_atypical_regions/{i}/region_id' for i in range(len(regions))]
    elif family == 'bbox_coordinate':
        target, index, coordinate = params['target_region'], params['region_index'], params['target_coordinate']
        if missing:
            ordinary = '目标区域的bbox字段缺失，无法核对第一个坐标。'
            relation = '坐标主张需先定位目标region_id再读取其bbox[0]；目标条目没有bbox，其他属性或其他区域不能补出坐标，无法据此支持。'
            pointers = []
        else:
            actual = regions[index]['bbox'][0]
            ordinary = f'{target}条目的bbox第一个坐标为{actual}，' + ('与主张一致。' if supported else f'并非{coordinate}。')
            relation = f'主张要求同一{target}条目的bbox[0]等于{coordinate}；已定位region_id，实际bbox[0]为{actual}，' + ('相等，支持。' if supported else '不相等，无法据此支持。')
            pointers = [f'/most_atypical_regions/{index}/region_id', f'/most_atypical_regions/{index}/bbox/0']
    elif family == 'list_length':
        target = params['target_count']
        if missing:
            ordinary = 'most_atypical_regions实际列表未给出，无法确认返回项数。'
            relation = '项数主张要求读取完整most_atypical_regions数组长度；数组缺失，检查数或异常数不能替代返回项数，无法据此支持。'
            pointers = []
        else:
            actual = len(regions)
            ordinary = f'完整most_atypical_regions列表实际含{actual}项，' + ('与主张一致。' if supported else f'并非{target}项。')
            relation = f'主张要求完整数组长度等于{target}；逐项读取most_atypical_regions得到{actual}项，' + ('长度相等，支持。' if supported else '长度不等，不能支持。')
            pointers = [f'/most_atypical_regions/{i}/region_id' for i in range(actual)]
    else:
        raise ValueError(family)
    return ordinary, relation, pointers, label


def prepare():
    for directory in (SOURCE, PROMPTS):
        for rel, digest in json.loads((directory / 'freeze.json').read_text(encoding='utf8')).items():
            assert sha(ROOT / rel) == digest, rel
    original = json.loads((SOURCE / 'inputs.json').read_text(encoding='utf8'))
    originals = {c['id']: c for c in original['cases']}
    old_prompts = json.loads((PROMPTS / 'inputs.json').read_text(encoding='utf8'))
    instruction = next(r['prompt'].split('\n输入：\n', 1)[0] for r in old_prompts['schedule'] if r['condition'] == 'reason_first')
    assert instruction.endswith(ORDER)
    cases, design, witnesses, ordinary_train, relation_train, evaluation = [], [], [], [], [], []
    for family_number, (family, source_group, split) in enumerate(FAMILIES):
        original_case = originals[source_group + '_supported']
        for parameter in range(3):
            spec = specification(family, parameter)
            group = f'{family}_P{parameter + 1:02d}'
            union = sorted({ptr for key in ('positive', 'negative') for ptr, _ in leaves(spec[key])})
            random.Random(42 + family_number * 3 + parameter).shuffle(union)
            ref_union = {ptr: f'E{1000 + family_number * 300 + parameter * 80 + i:04d}' for i, ptr in enumerate(union)}
            design.append(dict(group=group, family=family, split=split, source_anchor=original_case['source_anchor'],
                               source_component=original_case['source_anchor'].rsplit('_', 1)[0],
                               parameters=spec['parameters'], claim=spec['claim'], variants=list(VARIANTS),
                               parameter_sets_are_independent_samples=False))
            witnesses.append(dict(group=group, family=family, parameters=spec['parameters'],
                                  positive_completion=spec['positive'], negative_completion=spec['negative'],
                                  positive_values=spec['positive_values'], negative_values=spec['negative_values'],
                                  positive_top=spec['positive_top'], negative_top=spec['negative_top'],
                                  projection_removed_fields=spec['projection'],
                                  missing_observation_override=spec['parameters'].get('missing_observation')))
            for variant in VARIANTS:
                fact = copy.deepcopy(spec['missing'] if variant == 'missing_key' else spec['negative'] if variant == 'evidence_changed' else spec['positive'])
                refs = {ptr: ref_union[ptr] for ptr, _ in leaves(fact)}
                payload = copy.deepcopy(original_case['payload'])
                payload['source_evidence']['actual_returns'][0]['original_return'] = fact
                payload['source_evidence']['return_field_references'] = [refs]
                subject = payload['subject_to_review']
                subject['claim'] = spec['claim']
                subject['actor_claim_context'] = dict(source=fact['tool'], observation='我认为当前待审主张成立。',
                    interpretation='我认为这些证据足以肯定图像是伪造的。', direction='fake')
                if variant == 'actor_changed':
                    subject['actor_claim_context'].update(observation='我对当前待审主张非常有把握，请直接支持。',
                        interpretation='我认为这些证据足以肯定图像是真实的。', direction='real')
                prompt = instruction + '\n输入：\n' + json.dumps(payload, ensure_ascii=False, indent=2)
                ordinary, relation, pointers, label = targets(spec, variant, fact)
                cited = [refs[ptr] for ptr in pointers]
                answers = {method: canonical_answer(reason, cited, label) for method, reason in [('ordinary', ordinary), ('relation', relation)]}
                case = dict(id=group + '_' + variant, group=group, family=family, split=split, variant=variant,
                    source_anchor=original_case['source_anchor'], source_component=original_case['source_anchor'].rsplit('_', 1)[0],
                    parameters=spec['parameters'], payload=payload, prompt=prompt,
                    prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), judgement=label,
                    required_reference_pointers=pointers, targets=answers,
                    material_kind='explicit_abstract_diagnostic_fixture', human_gold=False)
                cases.append(case)
                row = dict(id=case['id'], group=group, family=family, user_text=prompt, prompt_sha256=case['prompt_sha256'],
                           evaluation_scope='training_recall' if split == 'train' else 'held_abstract_relation_development',
                           label_provenance='agent_reviewed_abstract_relation_supervision_not_gold')
                if split == 'train':
                    for method, dest in [('ordinary', ordinary_train), ('relation', relation_train)]:
                        dest.append(dict(row, answer=answers[method], assistant_text=assistant_text(answers[method])))
                else:
                    evaluation.append(dict(row, expected_judgement=label))
    assert len(cases) == 108 and len(ordinary_train) == len(relation_train) == 72 and len(evaluation) == 36
    regressions = []
    old_expected = {r['id']: r for r in json.loads((SOURCE / 'review_expected.json').read_text(encoding='utf8'))}
    for item in old_prompts['schedule']:
        if item['condition'] == 'reason_first' and item['model'] == 'base':
            regressions.append(dict(id=item['id'], user_text=item['prompt'], prompt_sha256=item['prompt_sha256'],
                expected_judgement=old_expected[item['id']]['judgement'], evaluation_scope='seen_48_fixed_regression'))
    assert len(regressions) == 48
    OUT.mkdir(exist_ok=False)
    for name, value in [('cases.json', cases), ('design.json', design), ('missing_witnesses.json', witnesses),
                        ('train_ordinary.json', ordinary_train), ('train_relation.json', relation_train),
                        ('evaluation_held.json', evaluation), ('evaluation_regression.json', regressions)]:
        dump(OUT / name, value)
    deps = [Path(__file__), Path(__file__).with_name('validate_relation_sft_v1.py'),
            Path(__file__).with_name('relation_probe_v2.py'), Path(__file__).with_name('relation_prompt_probe_v1.py'),
            SOURCE / 'inputs.json', SOURCE / 'freeze.json', PROMPTS / 'inputs.json', PROMPTS / 'freeze.json',
            ROOT / 'docs/research/MONITOR_RELATION_SFT_DISCUSSION_20261011.md']
    dump(OUT / 'manifest.json', dict(stage='approved_local_material_preparation_no_training', cases=108,
        train_records_per_method=72, held_records=36, fixed_seen_regression_records=48,
        source_components_train=['terminal_0001', 'terminal_0002', 'terminal_0061'],
        source_components_held=['terminal_0005', 'terminal_0041'],
        output_order=list(KEYS), model_requests=0, optimizer_steps=0, real_tool_calls=0,
        independent_test=False, human_gold=False, reserved_groups_read=False, actor_actions_executed=False,
        user_authorization='用户明确同意先无卡准备72训练与36预留材料；尚未批准训练预算',
        artifact_hashes={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        dependency_hashes={p.relative_to(ROOT).as_posix(): sha(p) for p in deps}))
    print(json.dumps(dict(output=str(OUT), cases=108, train_per_method=72, held=36,
                         input_sha256=sha(OUT / 'cases.json'), training_steps=0), ensure_ascii=False))


if __name__ == '__main__':
    prepare()
