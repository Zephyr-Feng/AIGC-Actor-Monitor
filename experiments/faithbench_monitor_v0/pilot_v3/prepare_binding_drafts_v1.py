"""Six local discussion drafts from frozen training rows; no model or trainer use."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'experiments/faithbench_monitor_v0/private/relation_sft_materials_v2_20261011'
OUT = ROOT / 'experiments/faithbench_monitor_v0/private/evidence_binding_drafts_v1_20261011'
IDS = (
    'all_at_max_P01_supported', 'all_at_max_P01_missing_key',
    'all_count_P01_missing_key', 'max_median_P01_evidence_changed',
    'raw_score_P01_evidence_changed', 'threshold_P01_supported',
)
EXPECTED = {
    'manifest.json': 'c1a8786e9ac0b297b637fdf17c783b24c5aadc1a7d5eacbb1d1360f8a5e00b03',
    'train_relation.json': '864b96af8dd5856f4b0e7e4de04190b059694a4f0daa382bfca06610d2ebda64',
    'train_ordinary.json': 'fa8f1fc332daa139a4e887ad22fdf8e10df5504b37e1d8af0be5340a7d5cc1c4',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def resolve(value, pointer):
    if not pointer:
        return value
    for part in pointer.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def binding(fact, refs, pointer, subject, key, identity_pointer=None):
    parent, field = pointer.rsplit('/', 1)
    obj = resolve(fact, parent)
    present = field in obj
    result = dict(binding_id=key, subject=subject, object_pointer=parent,
                  field_pointer=pointer, availability='已给出' if present else '字段缺失')
    if identity_pointer:
        result['identity'] = dict(field_pointer=identity_pointer,
                                  actual_value=resolve(fact, identity_pointer),
                                  return_reference_id=refs[identity_pointer])
    if present:
        result.update(actual_value=resolve(fact, pointer), return_reference_ids=[refs[pointer]])
    else:
        result.update(return_reference_ids=[], absence_scope_pointer=parent,
                      observed_object_keys=list(obj))
    return result


def check(name, inputs, result, detail):
    return dict(condition=name, binding_ids=inputs, result=result, detail=detail)


def target(row, payload):
    evidence = payload['source_evidence']
    fact = evidence['actual_returns'][0]['original_return']
    refs = evidence['return_field_references'][0]
    family = row['family']
    bindings, checks = [], []

    def add(pointer, subject, key, identity_pointer=None):
        b = binding(fact, refs, pointer, subject, key, identity_pointer)
        bindings.append(b)
        return b

    if family == 'all_at_max':
        n = add('/scope/num_regions_examined', '本次全部受检区域', 'N')['actual_value']
        known = []
        for i, region in enumerate(fact['most_atypical_regions']):
            b = add(f'/most_atypical_regions/{i}/deviation_percentile',
                    '区域' + region['region_id'], f'V{i}', f'/most_atypical_regions/{i}/region_id')
            known.append(b)
        identities = [b['identity']['actual_value'] for b in known]
        assert len(set(identities)) == len(known) == n
        checks.append(check('返回条目覆盖本题全部受检项', ['N', 'V0', 'V1', 'V2'], '满足',
                            f'检查数{n}，三个不同区域条目属于本次受检集合；覆盖条目不等于每个数值都已给出。'))
        missing = any(b['availability'] == '字段缺失' for b in known)
        checks.append(check('所有受检项的偏离百分位均等于100', ['V0', 'V1', 'V2'],
                            '无法核验' if missing else '满足',
                            'R12与R13均为100，R14对应字段缺失，不能确定R14是否为100。' if missing
                            else 'R12、R13、R14各自对应的偏离百分位均为100。'))
        reason = ('检查数3，R12与R13的偏离百分位为100，但R14的对应字段缺失，无法支持全部受检区域均为100。'
                  if missing else '检查数3，三个不同受检区域R12、R13、R14的偏离百分位均为100，支持该观察主张。')
    elif family == 'all_count':
        add('/scope/num_regions_examined', '本次全部受检区域', 'N')
        add('/observations/atypical_threshold_percentile', '本次异常统计的阈值', 'T')
        add('/observations/num_atypical_regions', '本次达到阈值的区域数', 'C')
        add('/observations/atypical_fraction', '本次达到阈值的区域比例', 'F')
        checks.append(check('达到本题阈值的区域数等于全部受检区域数', ['N', 'T', 'C', 'F'],
                            '无法核验', '检查数7、阈值95已给出；异常区域数与比例缺失，无法核验异常数是否等于7。'))
        reason = '检查数7与阈值95已给出，异常区域数和比例缺失，无法确认所有受检区域都达到该阈值。'
    elif family == 'max_median':
        left = add('/observations/max_deviation_percentile', '本次最大偏离百分位', 'MAX')
        right = add('/observations/median_deviation_percentile', '本次中位偏离百分位', 'MED')
        assert left['actual_value'] == right['actual_value'] == 99
        checks.append(check('最大偏离百分位严格大于中位偏离百分位', ['MAX', 'MED'],
                            '不满足', '99与99.0数值相等，严格大于关系不成立。'))
        reason = '实际最大偏离百分位99、中位偏离百分位99.0，二者相等，不支持严格高于的主张。'
    elif family == 'raw_score':
        b = add('/score', '本次原始score', 'SCORE')
        rounded = format(Decimal(str(b['actual_value'])).quantize(Decimal('0.000001'), rounding=ROUND_HALF_EVEN), 'f')
        assert rounded == '0.273842'
        checks.append(check('score按六位小数舍入等于主张中的0.173842', ['SCORE'],
                            '不满足', f'绑定原始score后舍入得到{rounded}，与0.173842不同。'))
        reason = '实际score按六位小数舍入为0.273842，与主张0.173842不符，无法据此支持。'
    else:
        assert family == 'threshold'
        b = add('/observation', '本次observation文本', 'OBS')
        assert '固定判定阈值为 0.25' in b['actual_value']
        checks.append(check('observation明确写出主张中的固定阈值0.25', ['OBS'],
                            '满足', '原字段文本含“固定判定阈值为 0.25”，符合当前文本归因主张。'))
        reason = '实际observation字段明确写出固定判定阈值为0.25，支持该文本归因主张。'

    cited = []
    for b in bindings:
        if 'identity' in b:
            cited.append(b['identity']['return_reference_id'])
        cited.extend(b['return_reference_ids'])
    return dict(claim=payload['subject_to_review']['claim'],
                return_scope=dict(return_index=0, source=evidence['actual_returns'][0]['source'],
                                  returned_after_step=evidence['actual_returns'][0]['returned_after_step'],
                                  input_pointer='/source_evidence/actual_returns/0/original_return'),
                evidence_bindings=bindings, relation_checks=checks, reason=reason,
                return_reference_ids=list(dict.fromkeys(cited)), judgement=row['answer']['judgement'])


def validate_record(draft):
    payload, answer = draft['input_payload'], draft['draft_target']
    evidence = payload['source_evidence']
    fact, refs = evidence['actual_returns'][0]['original_return'], evidence['return_field_references'][0]
    assert answer['claim'] == payload['subject_to_review']['claim']
    ids = {b['binding_id'] for b in answer['evidence_bindings']}
    cited = []
    for b in answer['evidence_bindings']:
        pointer = b['field_pointer']
        if b['availability'] == '已给出':
            assert b['actual_value'] == resolve(fact, pointer)
            assert b['return_reference_ids'] == [refs[pointer]]
        else:
            obj = resolve(fact, b['absence_scope_pointer'])
            assert pointer.rsplit('/', 1)[1] not in obj and pointer not in refs
            assert 'actual_value' not in b and b['return_reference_ids'] == []
            assert b['observed_object_keys'] == list(obj)
        if 'identity' in b:
            identity = b['identity']
            assert identity['field_pointer'].rsplit('/', 1)[0] == b['object_pointer']
            assert identity['actual_value'] == resolve(fact, identity['field_pointer'])
            assert identity['return_reference_id'] == refs[identity['field_pointer']]
            cited.append(identity['return_reference_id'])
        cited.extend(b['return_reference_ids'])
    for c in answer['relation_checks']:
        assert set(c['binding_ids']) <= ids
    assert answer['return_reference_ids'] == list(dict.fromkeys(cited))
    assert set(cited) <= set(refs.values())
    assert set(cited).isdisjoint(payload['source_capability_definitions'])
    results = [c['result'] for c in answer['relation_checks']]
    assert answer['judgement'] == ('支持' if all(x == '满足' for x in results) else '无法据此支持')


def main():
    for name, digest in EXPECTED.items():
        assert sha(SOURCE / name) == digest, name
    rows = json.loads((SOURCE / 'train_relation.json').read_text(encoding='utf-8'))
    ordinary = json.loads((SOURCE / 'train_ordinary.json').read_text(encoding='utf-8'))
    assert len(rows) == len(ordinary) == 72
    by_id, ordinary_by_id = {r['id']: r for r in rows}, {r['id']: r for r in ordinary}
    drafts = []
    for case_id in IDS:
        row = by_id[case_id]
        assert row['evaluation_scope'] == 'training_recall'
        assert row['user_text'] == ordinary_by_id[case_id]['user_text']
        assert row['prompt_sha256'] == hashlib.sha256(row['user_text'].encode()).hexdigest()
        payload = json.loads(row['user_text'].rsplit('输入：\n', 1)[1])
        assert payload['source_evidence']['fixture_provenance']['real_tool_call'] is False
        d = dict(source_case_id=case_id, family=row['family'], group=row['group'],
                 source_prompt_sha256=row['prompt_sha256'], input_payload=payload,
                 original_relation_target=row['answer'], draft_target=target(row, payload))
        assert d['draft_target']['judgement'] == row['answer']['judgement']
        validate_record(d)
        drafts.append(d)
    first, second = drafts[:2]
    f1 = first['input_payload']['source_evidence']['actual_returns'][0]['original_return']
    f2 = second['input_payload']['source_evidence']['actual_returns'][0]['original_return']
    restored = json.loads(json.dumps(f2))
    restored['most_atypical_regions'][2]['deviation_percentile'] = 100
    assert restored == f1
    assert first['draft_target']['claim'] == second['draft_target']['claim']
    assert first['input_payload']['subject_to_review'] == second['input_payload']['subject_to_review']
    OUT.mkdir(exist_ok=False)
    dump(OUT / 'drafts.json', dict(stage='six_discussion_drafts_not_executable_training_data',
                                 human_gold=False, independent_examples=False, records=drafts))
    dump(OUT / 'validation.json', dict(records=6, present_bindings=sum(
        b['availability'] == '已给出' for d in drafts for b in d['draft_target']['evidence_bindings']),
        missing_bindings=sum(b['availability'] == '字段缺失' for d in drafts
                             for b in d['draft_target']['evidence_bindings']),
        claim_preserved=True, original_labels_preserved=True,
        same_object_identity_and_value=True, field_values_and_leaf_ids_match=True,
        missing_fields_scoped_and_uncited=True, decisive_pair_single_return_field_removed=True,
        model_requests=0, optimizer_steps=0, held_records_read=0, reserved_real_groups_read=0,
        remote_calls=0, source_hashes=EXPECTED, semantic_review='pending separate local reread; not independent gold'))
    # The human-readable report is added separately and reviewed before freezing.
    print(json.dumps(dict(output=str(OUT), count=len(drafts), source_files_unchanged=all(
        sha(SOURCE / name) == digest for name, digest in EXPECTED.items())), ensure_ascii=False))


if __name__ == '__main__':
    main()
