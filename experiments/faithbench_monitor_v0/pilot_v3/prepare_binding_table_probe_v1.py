"""Prepare the approved paired diagnostic, without loading model weights."""
import hashlib
import json
import os
import random
import sys
from pathlib import Path
from binding_compact_probe_v1 import ROOT, PRIVATE, SOURCE, INSTRUCTION, compact, audit_answer, resolve, sha, dump

OUT = PRIVATE / 'binding_table_probe_v1_20261011'
OLD = PRIVATE / 'binding_compact_probe_v1_20261011'
MAX_NEW = 1024


def factual_table(draft):
    evidence = draft['input_payload']['source_evidence']
    fact = evidence['actual_returns'][0]['original_return']
    refs = evidence['return_field_references'][0]
    rows = []
    for b in draft['draft_target']['evidence_bindings']:
        row = dict(object_pointer=b['object_pointer'], field_pointer=b['field_pointer'],
                   availability=b['availability'])
        if b['availability'] == '已给出':
            assert resolve(fact, b['field_pointer']) == b['actual_value']
            assert refs[b['field_pointer']] == b['return_reference_ids'][0]
            row.update(value=b['actual_value'], ref=refs[b['field_pointer']])
        else:
            assert b['field_pointer'].rsplit('/', 1)[0] == b['object_pointer']
            assert b['field_pointer'].rsplit('/', 1)[1] not in resolve(fact, b['object_pointer'])
            assert b['field_pointer'] not in refs
        if 'identity' in b:
            identity = b['identity']
            assert identity['field_pointer'].rsplit('/', 1)[0] == b['object_pointer']
            assert resolve(fact, identity['field_pointer']) == identity['actual_value']
            assert refs[identity['field_pointer']] == identity['return_reference_id']
            row['identity'] = dict(field_pointer=identity['field_pointer'], value=identity['actual_value'],
                                   ref=identity['return_reference_id'])
        rows.append(row)
    return rows


def prepare():
    for directory, filename in [(SOURCE, 'freeze.json'), (OLD, 'final_stage_audit.json')]:
        for name, digest in json.loads((directory / filename).read_text(encoding='utf-8'))['artifact_hashes'].items():
            assert sha(ROOT / name) == digest, name
    assets = PRIVATE / 'relation_sft_materials_v1_20261011'
    for name, row in json.loads((assets / 'tokenizer_cache_provenance.json').read_text(encoding='utf-8'))['files'].items():
        assert sha(assets / 'tokenizer_cache' / name) == row['sha256']
    os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1')
    sys.path.insert(0, str(assets / 'python_libs'))
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(assets / 'tokenizer_cache', local_files_only=True)
    drafts = json.loads((SOURCE / 'drafts.json').read_text(encoding='utf-8'))['records']
    assert len(drafts) == 6
    prefix = INSTRUCTION.rsplit('输入：\n', 1)[0].replace('总输出预算384 token', '总输出预算1024 token')
    prefix += '若提供核验事实表，它仅帮助定位原返回；关系、理由和判断仍须自行核验。不要展开与当前主张无关的字段。\n'
    materials, records, lengths = [], [], []
    rng = random.Random(42)
    order = list(range(6))
    rng.shuffle(order)
    for index in order:
        draft = drafts[index]
        table = factual_table(draft)
        expected = compact(draft)
        assert audit_answer(expected, draft['input_payload'], expected)['required_binding_coverage']
        conditions = ['original', 'fact_table']
        rng.shuffle(conditions)
        for condition in conditions:
            extra = '' if condition == 'original' else '核验事实表（原返回中的字段定位，无关系判断）：\n' + json.dumps(table, ensure_ascii=False, separators=(',', ':')) + '\n'
            prompt = prefix + extra + '输入：\n' + json.dumps(draft['input_payload'], ensure_ascii=False, indent=2)
            assert json.loads(prompt.split('输入：\n', 1)[1]) == draft['input_payload']
            body = json.dumps(expected, ensure_ascii=False, separators=(',', ':'))
            messages = [{'role': 'user', 'content': prompt}]
            ids = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
            full = tok.apply_chat_template(messages + [{'role': 'assistant', 'content': body}], tokenize=True, add_generation_prompt=False)
            assert full[:len(ids)] == ids
            assert len(ids) + MAX_NEW <= 4096 and len(full) - len(ids) <= MAX_NEW
            rid = draft['source_case_id'] + '__' + condition
            record = dict(id=rid, case_id=draft['source_case_id'], condition=condition, prompt=prompt,
                          prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), local_input_tokens=len(ids))
            records.append(record)
            materials.append(dict(**record, input_payload=draft['input_payload'], expected=expected,
                                  factual_table=table if condition == 'fact_table' else None))
            lengths.append(dict(id=rid, input_tokens=len(ids), target_tokens=len(full)-len(ids)))
    assert len(records) == len({r['id'] for r in records}) == 12
    old_inputs = json.loads((OLD / 'inputs.json').read_text(encoding='utf-8'))
    dependencies = dict(old_inputs['frozen_dependencies'])
    for filename in ['prepare_binding_table_probe_v1.py', 'run_binding_table_probe_v1.py',
                     'control_binding_table_probe_v1.py', 'PLAN_BINDING_TABLE_PROBE_V1_20261011.md']:
        path = Path(__file__).parent / filename
        dependencies[path.relative_to(ROOT).as_posix()] = sha(path)
    for name, digest in dependencies.items():
        assert sha(ROOT / name) == digest, name
    OUT.mkdir(exist_ok=False)
    dump(OUT / 'materials.json', dict(records=materials, authorization='可以，按照这个方案来实验试试吧',
                                     source_sha256=sha(SOURCE / 'drafts.json'), independent_gold=False))
    dump(OUT / 'cpu_preflight.json', dict(rows=lengths, records=12, max_new_tokens=MAX_NEW,
        context_limit=4096, model_loaded=False, truncated=False, mask_prefix_match=True,
        same_complete_payload_per_pair=True, checked_factual_fields=16, checked_identity_fields=6))
    dump(OUT / 'inputs.json', dict(records=records, model_requests=12, max_new_tokens=MAX_NEW,
        runner_sha256=sha(Path(__file__).parent / 'run_binding_table_probe_v1.py'),
        old_adapter_hashes=old_inputs['old_adapter_hashes'], frozen_dependencies=dependencies))
    with (OUT / 'expected_protection.json').open('xb') as stream:
        stream.write((OLD / 'expected_protection.json').read_bytes())
    names = ['materials.json', 'cpu_preflight.json', 'inputs.json', 'expected_protection.json']
    hashes = {(OUT / name).relative_to(ROOT).as_posix(): sha(OUT / name) for name in names}
    hashes.update({name: dependencies[name] for name in dependencies if 'binding_table_probe_v1' in name.upper().lower()})
    dump(OUT / 'freeze.json', dict(artifact_hashes=hashes, model_requests=12, optimizer_steps=0))
    print(json.dumps(dict(rows=lengths, dependencies=len(dependencies), frozen_files=len(hashes)), ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    prepare()
