"""Compact six frozen drafts and prepare the authorized six-request base preflight."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
SOURCE = PRIVATE / 'evidence_binding_drafts_v1_20261011'
OUT = PRIVATE / 'binding_compact_probe_v1_20261011'
ORDER = ('bindings', 'checks', 'reason', 'return_reference_ids', 'judgement')
INSTRUCTION = '''这是明确标识的抽象关系诊断fixture，不是真实图像或新的工具/Actor事件。
审核subject_to_review.claim在本次实际返回下是否有依据。只以actual_returns中的original_return为事实；能力卡和Actor解释不能补全返回的缺失内容，不改成图像真假判定。
先绑定所需对象和字段，再核验关系，最后写理由和判断。只输出紧凑JSON，字段及顺序为bindings、checks、reason、return_reference_ids、judgement。
bindings为数组。已给出字段用{"ref":"原实际叶子E编号","value":"该叶子的实际值"}，value保持原JSON类型；涉及区域数值时另加entity，值为同一条目region_id的实际叶子E编号。E编号须通过return_field_references对应到字段，不能因编号存在就认为它支持主张。
缺失字段用{"object":"original_return内父对象JSON Pointer","field":"缺失字段名","missing":true}；区域字段另加entity指向该条目的region_id。缺失绑定不写ref或value，不借邻近编号，不猜缺失值。object只是定位，不是新增证据编号。
checks为数组，每项恰有condition和result，写出当前主张需要的条件；result只能为满足、不满足或无法核验。不要把已知字段写成缺失，不把部分值、最大值、中位数或其他属性代替缺失的目标字段。
reason为简短中文理由，忠于绑定的实际事实与必要条件；return_reference_ids为绑定中用到的实际叶子E编号去重数组，包含entity，不能引用能力卡。无法据此支持不等于证明图像真实或Actor全部错误。
只有全部必要条件满足，judgement才为支持；条件不满足或无法核验时为无法据此支持。区别证据反驳与证据不足。总输出预算384 token，请勿重复抄写整个主张、工具来源或原输入。
输入：
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def resolve(value, pointer):
    if not pointer:
        return value
    for part in pointer.split('/')[1:]:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def compact(draft):
    target = draft['draft_target']
    bindings = []
    for b in target['evidence_bindings']:
        if b['availability'] == '已给出':
            row = dict(ref=b['return_reference_ids'][0], value=b['actual_value'])
        else:
            row = dict(object=b['absence_scope_pointer'], field=b['field_pointer'].rsplit('/', 1)[1], missing=True)
        if 'identity' in b:
            row['entity'] = b['identity']['return_reference_id']
        bindings.append(row)
    checks = [dict(condition=c['condition'], result=c['result']) for c in target['relation_checks']]
    return dict(bindings=bindings, checks=checks, reason=target['reason'],
                return_reference_ids=target['return_reference_ids'], judgement=target['judgement'])


def audit_answer(answer, payload, expected):
    """Structural/field audit only; semantic conditions and prose need separate review."""
    assert isinstance(answer, dict) and set(answer) == set(ORDER), 'output keys'
    assert isinstance(answer['bindings'], list) and isinstance(answer['checks'], list), 'arrays'
    assert isinstance(answer['reason'], str) and answer['reason'], 'reason'
    assert answer['judgement'] in ('支持', '无法据此支持'), 'judgement'
    evidence = payload['source_evidence']
    fact = evidence['actual_returns'][0]['original_return']
    refs = evidence['return_field_references'][0]
    pointers = {ref: pointer for pointer, ref in refs.items()}
    cited, covered = [], set()
    for b in answer['bindings']:
        assert isinstance(b, dict), 'binding type'
        if 'ref' in b:
            assert set(b) in ({'ref', 'value'}, {'ref', 'value', 'entity'}), 'present binding keys'
            pointer = pointers[b['ref']]
            assert b['value'] == resolve(fact, pointer), 'bound value differs from return'
            cited.append(b['ref'])
        else:
            assert set(b) in ({'object', 'field', 'missing'}, {'object', 'field', 'missing', 'entity'}), 'missing binding keys'
            assert b['missing'] is True and isinstance(b['object'], str) and isinstance(b['field'], str)
            obj = resolve(fact, b['object'])
            assert isinstance(obj, dict) and b['field'] not in obj, 'field is not absent'
            pointer = b['object'] + '/' + b['field'].replace('~', '~0').replace('/', '~1')
            assert pointer not in refs, 'missing field has a leaf'
        covered.add(pointer)
        if 'entity' in b:
            identity_pointer = pointers[b['entity']]
            assert identity_pointer.endswith('/region_id'), 'entity is not region_id'
            assert identity_pointer.rsplit('/', 1)[0] == pointer.rsplit('/', 1)[0], 'entity/value from different objects'
            cited.append(b['entity'])
        elif pointer.startswith('/most_atypical_regions/') and not pointer.endswith('/region_id'):
            raise AssertionError('region binding needs same-object identity')
    actual_citations = answer['return_reference_ids']
    assert isinstance(actual_citations, list) and all(isinstance(x, str) for x in actual_citations)
    assert len(actual_citations) == len(set(actual_citations))
    assert set(actual_citations) == set(cited), 'citations differ from bindings'
    assert set(cited).isdisjoint(payload['source_capability_definitions'])
    for c in answer['checks']:
        assert isinstance(c, dict) and set(c) == {'condition', 'result'}
        assert isinstance(c['condition'], str) and c['condition']
        assert c['result'] in ('满足', '不满足', '无法核验')
    assert answer['checks'], 'checks empty'
    relation_label = '支持' if all(c['result'] == '满足' for c in answer['checks']) else '无法据此支持'
    assert answer['judgement'] == relation_label, 'check/judgement contradiction'
    required = set()
    for b in expected['bindings']:
        required.add(pointers[b['ref']] if 'ref' in b else b['object'] + '/' + b['field'])
    return dict(field_bindings_true=True, required_binding_coverage=required <= covered,
                output_order_correct=list(answer) == list(ORDER), citations_true_and_cover_bindings=True)


def prepare():
    source_freeze = json.loads((SOURCE / 'freeze.json').read_text(encoding='utf-8'))
    for name, digest in source_freeze['artifact_hashes'].items():
        assert sha(ROOT / name) == digest, name
    drafts = json.loads((SOURCE / 'drafts.json').read_text(encoding='utf-8'))['records']
    assert len(drafts) == 6
    assets = PRIVATE / 'relation_sft_materials_v1_20261011'
    provenance = json.loads((assets / 'tokenizer_cache_provenance.json').read_text(encoding='utf-8'))
    for name, v in provenance['files'].items():
        assert sha(assets / 'tokenizer_cache' / name) == v['sha256']
    os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1')
    sys.path.insert(0, str(assets / 'python_libs'))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(assets / 'tokenizer_cache', local_files_only=True)
    records, lengths = [], []
    for draft in drafts:
        answer = compact(draft)
        checked = audit_answer(answer, draft['input_payload'], answer)
        assert checked['required_binding_coverage'] and checked['output_order_correct']
        body = json.dumps(answer, ensure_ascii=False, separators=(',', ':'))
        prompt = INSTRUCTION + json.dumps(draft['input_payload'], ensure_ascii=False, indent=2)
        messages = [{'role': 'user', 'content': prompt}]
        prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        full = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': body}], tokenize=True, add_generation_prompt=False)
        assert full[:len(prefix)] == prefix
        supervised = len(full) - len(prefix)
        assert supervised <= 384 and len(prefix) + 384 <= 4096, draft['source_case_id']
        assert json.loads(prompt.split('输入：\n', 1)[1]) == draft['input_payload']
        records.append(dict(id=draft['source_case_id'], prompt=prompt,
                            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                            input_payload=draft['input_payload'], expected=answer,
                            assistant_text=body, source_prompt_sha256=draft['source_prompt_sha256']))
        lengths.append(dict(id=draft['source_case_id'], prefix_tokens=len(prefix),
                            assistant_including_chat_end_tokens=supervised, full_tokens=len(full)))
    OUT.mkdir(exist_ok=False)
    dump(OUT / 'materials.json', dict(records=records, model_requests=0, optimizer_steps=0,
                                     user_authorization='确认。已经开卡，你可以跑模型', source_sha256=sha(SOURCE / 'drafts.json')))
    dump(OUT / 'cpu_preflight.json', dict(rows=lengths, records=6, same_complete_payload=True,
                                         original_labels_preserved=True, model_loaded=False,
                                         torch_disabled=True, mask_prefix_match=True, truncated=False))
    print(json.dumps(dict(rows=lengths, records=6, output=str(OUT)), ensure_ascii=False))


if __name__ == '__main__':
    prepare()
