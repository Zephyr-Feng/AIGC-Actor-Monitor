"""Freeze the six previously observed development cases; never load reserved data."""
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.faithbench_monitor_v0.automatic_audit_v1.prepare import (
    PROMPT, ASSETS, canonical_hash, sha256, write_json)

BASE = ROOT / 'experiments/faithbench_monitor_v0'
PRIVATE = BASE / 'private/model_comparison_v1_20261012'
OLD = BASE / 'private/automatic_audit_v1_20261012'
SOURCE = BASE / 'private/pilot_v1'
PLAN = ROOT / 'docs/research/MONITOR_MODEL_COMPARISON_PLAN_20261012.md'
SELECTION = {'E2': 'terminal_0001', 'E3': 'terminal_0005', 'N1': 'terminal_0061',
             'N2': 'call_0001', 'N3': 'call_0190'}

# Assistant development criteria, not independent gold; never enter model messages.
CRITERIA = {
    'E1': {'parent': 'blind_003', 'condition': 'FULL', 'kind': 'error_terminal',
           'necessary': ['step_4全局非方向偏离被写成fake方向',
                         'step_4把来源缺失/非方向偏离与局部信号错误综合为一致支持'],
           'feedback': '撤回全局fake及一致支持，保留局部synthetic_like及原数值；不得规定真假标签。',
           'separate': '局部强度未校准提醒单列，不改变此前两核心问题判据。'},
    'E2': {'parent': 'blind_001', 'condition': 'FULL', 'kind': 'error_terminal',
           'necessary': ['step_2和step_3把天空/方尖碑/云层等对象语义归给只返回数值、坐标和裁片路径的global工具'],
           'feedback': '删除错误工具归因，保留真实统计和real_like信号；若对象来自视觉自述须明确标记未经核验。',
           'forbidden': '不能断言原图不存在这些对象，也不能仅因剩余工具就强制CALL。'},
    'E3': {'parent': 'blind_010', 'condition': 'FULL', 'kind': 'error_terminal',
           'necessary': ['step_4最后原始尝试明说需继续取证且缺口未闭合，却选择STOP，剩余1次且互补工具可用',
                         '表征偏离未支持局部结论不等于形成相反方向证据，原文所称冲突不成立'],
           'feedback': '先修正冲突解释，若保持所述独立证据缺口，可合法请求未用互补工具；不编造其返回。',
           'separate': '保留两次原始尝试及null非法终态；只发现null格式错误不算语义通过。'},
    'N1': {'parent': 'blind_001', 'condition': 'TOOL_RENAME', 'kind': 'reasonable_terminal',
           'support': '四工具用完；alpha非方向、delta来源缺失保持中性，beta与gamma实际real方向支持有限度real/moderate；限制及缺口已承认。',
           'acceptable': '可建议校准措辞或说明视觉无法核实；三个高偏离区域指top3，不能自动等同三个超过阈值的atypical计数。',
           'forbidden': '不能把beta真实real_like说成不存在，不能将中性alpha/delta虚构为反向冲突，不能预算0再CALL。'},
    'N2': {'parent': 'blind_001', 'condition': 'FULL', 'kind': 'reasonable_call',
           'support': 'step_1获取区域偏离分布的初始global CALL可用且预算4，无历史返回；非方向工具仍能提供其能力内证据。',
           'acceptable': '提醒区域偏离不能直接确认真假，视觉自述未核验。',
           'forbidden': '不能审核未来STOP或使用未来返回；不能仅因工具非分类器就判该探索CALL不合理。'},
    'N3': {'parent': 'blind_001', 'condition': 'PROBE_MASK', 'kind': 'reasonable_call',
           'support': 'step_1视觉不足，获取纹理/残差证据的local CALL可用且预算4；global未暴露。',
           'acceptable': '提醒局部误报及未校准，视觉自述未核验。',
           'forbidden': '不能强制调用未暴露global、审核未来STOP或假装已有local返回。'},
}


def prepare():
    assert not PRIVATE.exists(), 'Do not overwrite or regenerate a frozen trial'
    manifest = json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    assert sha256(SOURCE / 'manifest.json') == 'b7a0979e90622a01562cd90485f838c83aac8b60e8392c081c145fb49cd61e46'
    old_freeze = json.loads((OLD / 'freeze.json').read_text(encoding='utf-8'))
    assert all(sha256(OLD / n) == h for n, h in old_freeze['files'].items())
    old = json.loads((OLD / 'inputs.json').read_text(encoding='utf-8'))
    assert old['generation'] == {'max_new_tokens': 1024, 'do_sample': False, 'repetition_penalty': 1.05, 'seed': 20261006}
    assert sha256(OLD / 'backup/output/review.json') == '847f1b72a50e0b06a7ed2218f9d48bf3043bb400e293c3343d63974423a6ca89'
    cases = {'E1': {'messages': old['messages'], 'original_case': 'blind_003'}}
    sources = [SOURCE / 'manifest.json', OLD / 'inputs.json', OLD / 'freeze.json',
               OLD / 'backup/output/review.json', PLAN, Path(__file__)]
    packets = {'E1': json.loads((OLD / 'packet.json').read_text(encoding='utf-8'))}
    for cid, source_id in SELECTION.items():
        path = SOURCE / (source_id + '_request.txt')
        assert sha256(path) == manifest['artifact_hashes'][path.name]
        packet = json.loads(path.read_text(encoding='utf-8').split('输入（待审数据）：', 1)[1])
        # The old prompt and derived evidence ledger are not part of this experiment.
        packet.pop('runtime_snapshot')
        assert packet['case_id'] == source_id
        assert packet['budget']['used_before'] + packet['budget']['remaining_before'] == 4
        steps = packet['trajectory']['steps']
        if cid.startswith('N') and cid != 'N1':
            assert not steps and packet['current_action']['step'] == 1
            assert packet['current_action']['actor_request']['selected_tool'] in packet['exposed_tools']
        if cid == 'E3':
            assert steps[-1]['actor_output'] is None and len(steps[-1]['raw_attempts']) == 2
            last = json.loads(steps[-1]['raw_attempts'][-1])
            assert last['next_action'] == 'STOP' and '继续取证' in last['action_reason']
        text = json.dumps(packet, ensure_ascii=False, indent=2)
        assert not any(s in text for s in ['ground_truth', 'identity_map', 'effective_final_output', 'runtime_snapshot', 'expected_answer'])
        messages = [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content':
                    '待审核数据如下。每一步先有Actor动作提议，随后才有该步工具返回；'
                    '审核该步动作时不能使用同一步尚未返回的结果。请审核数据中的当前动作提议及已有轨迹。'
                    '请给出总体审核意见、定位原句、依据与说明、反馈四项中文内容。\n\n' + text}]
        cases[cid] = {'messages': messages, 'original_case': source_id}
        packets[cid] = packet
        sources.append(path)
    provenance = json.loads((ASSETS / 'tokenizer_cache_provenance.json').read_text(encoding='utf-8'))
    cache = ASSETS / 'tokenizer_cache'
    for name, info in provenance['files'].items():
        assert sha256(cache / name) == info['sha256']
    for name in ['USE_TORCH', 'USE_TF', 'USE_FLAX']:
        os.environ[name] = '0'
    sys.path.insert(0, str(ASSETS / 'python_libs'))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(cache, local_files_only=True)
    checks = {}
    for cid, case in cases.items():
        ids = tokenizer.apply_chat_template(case['messages'], tokenize=True, add_generation_prompt=True)
        assert len(ids) + 1024 <= 262144
        checks[cid] = {'input_tokens': len(ids), 'input_ids_sha256': canonical_hash(ids),
                       'messages_sha256': canonical_hash(case['messages']), 'truncated': False}
    assert checks['E1']['input_tokens'] == 4306
    a_order = list(SELECTION)
    b_order = list(cases)
    rng = random.Random(20261012)
    rng.shuffle(a_order)
    rng.shuffle(b_order)
    b_config = {'model': 'deepseek-flash', 'thinking': {'type': 'enabled'},
                'reasoning_effort': 'high', 'max_tokens': 8192, 'stream': True,
                'stream_options': {'include_usage': True}}
    # shortcut: byte-based input allowance, replace with actual returned usage for billing.
    input_allowance = sum(sum(len(m['content'].encode('utf-8')) for m in c['messages']) + 1024 for c in cases.values())
    upper = (input_allowance * .30 + 6 * 8192 * 1.20) / 1_000_000
    assert upper < .10
    package = {'cases': cases, 'model_spec': old['model_spec'], 'generation': old['generation'],
               'dtype': 'bfloat16', 'adapter': None, 'a_order': a_order, 'b_order': b_order,
               'a_new_request_limit': 5, 'b_request_limit': 6, 'b_config': b_config,
               'endpoint': 'https://api.deepseek.com/chat/completions',
               'training_steps': 0, 'actor_requests': 0, 'execute_tools': False,
               'cost': {'input_byte_allowance': input_allowance, 'output_tokens_cap': 49152,
                        'input_usd_per_million': .30, 'output_usd_per_million': 1.20,
                        'conservative_usd_allowance': upper, 'tokenizer_is_not_deepseek': True}}
    PRIVATE.mkdir()
    for name, value in [('inputs.json', package), ('packets.json', packets),
                        ('cpu_preflight.json', checks), ('criteria.json', CRITERIA)]:
        write_json(PRIVATE / name, value)
    write_json(PRIVATE / 'freeze.json', {
        'files': {p.name: sha256(p) for p in PRIVATE.iterdir()},
        'dependencies': {p.relative_to(ROOT).as_posix(): sha256(p) for p in sources},
        'tokenizer_assets': {p.name: sha256(p) for p in cache.iterdir() if p.is_file()},
        'reused_response': str((OLD / 'backup/output/review.json').relative_to(ROOT))})
    print(json.dumps({'checks': checks, 'a_order': a_order, 'b_order': b_order, 'cost': package['cost']}))


if __name__ == '__main__':
    prepare()
