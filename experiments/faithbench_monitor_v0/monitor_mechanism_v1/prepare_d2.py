"""Prepare only the approved four-case D2; old runs and scores stay frozen."""
import copy
import json
import random
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'experiments/actor_b'))
from contract_replay import reconstruct_stop_context
from run_b0 import canonical_hash, sha256
from experiments.actor_b.feedback_pilot_v1.pilot import dump, no_evaluation_fields
from experiments.actor_b.deepseek_monitor_pilot_v1.prepare import GENERAL, load

PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
OUT = PRIVATE / 'mechanism_d2_20261013'
NATURAL = PRIVATE / 'natural_actor_monitor_20261013'
D1 = PRIVATE / 'mechanism_d1_20261013'
D1B = PRIVATE / 'mechanism_d1b_20261013'
PLAN = Path(__file__).with_name('PLAN_D2_DEVELOPMENT_CLOSED_LOOP_20261013.md')
CASES = ('case_005', 'case_016', 'case_017', 'case_028')
ARMS = ('S', 'G', 'M')
SUFFIX = ('上一条是尚未执行的动作提议。请依据已有信息输出下一步的一个完整Actor-B JSON动作。'
          '可以维持或修正；工具可用性与剩余额度沿用原状态，未调用工具没有新返回，不得编造。'
          '成功工具不能重复调用。STOP的final_verdict只允许real/fake，final_confidence只允许low/moderate/high；'
          'current_evidence.direction按原schema，none合法。解释使用中文。')
DEPLOY_CODE = [
    'experiments/faithbench_monitor_v0/monitor_mechanism_v1/prepare_d2.py',
    'experiments/faithbench_monitor_v0/monitor_mechanism_v1/worker_d2.py',
    'experiments/actor_b/deepseek_monitor_pilot_v1/gpu_worker.py',
    'experiments/actor_b/deepseek_monitor_pilot_v1/prepare.py',
    'experiments/actor_b/feedback_pilot_v1/pilot.py',
    'experiments/faithbench_monitor_v0/monitor_protocol.py',
    'experiments/actor_b/contract_replay.py',
    'experiments/actor_b/actor_b_protocol.py',
    'experiments/actor_b/run_b0.py',
]


def messages(package, delivery, cid, arm):
    feedback = package['general'] if arm == 'S' else '外部审核反馈：' + delivery[cid][arm]['content']
    return copy.deepcopy(package['cases'][cid]['prefix']) + [
        {'role': 'user', 'content': feedback + '\n\n共同审核契约：\n'
         + json.dumps(package['review_contract'], ensure_ascii=False, sort_keys=True)
         + '\n\n' + package['suffix']}]


def prepare():
    assert not OUT.exists(), 'exclusive preparation; do not overwrite or restart'
    frozen, previous = load(NATURAL / 'actor_freeze.json'), load(D1B / 'freeze.json')
    protected = {**frozen['files'], **previous['files'], **previous['original_sources_sha256']}
    protected.update(load(PRIVATE / 'mechanism_d2_readiness_20261013/context_check.json')['sources_sha256'])
    for name, digest in protected.items():
        assert sha256(ROOT / name) == digest, name
    d1, d1b = load(D1 / 'monitor_inputs.json'), load(D1B / 'monitor_inputs.json')
    packets = load(D1B / 'monitor_packets.json')['M2']
    prompt = (ROOT / 'experiments/actor_b/prompts/system_prompt.txt').read_text(encoding='utf8').strip()
    schema = load(ROOT / 'experiments/actor_b/schemas/actor_b_action.schema.json')
    cards = load(NATURAL / 'tool_cards.json')
    generation = load(ROOT / 'experiments/actor_b/config/generation_config.json')
    cases, cache = {}, {}
    for line in (NATURAL / 'tool_results.jsonl').read_text(encoding='utf8').splitlines():
        match = re.search(r'"sample_id"\s*:\s*"(case_\d+)"', line)
        if match and match[1] in CASES:
            row = json.loads(line)
            cache[row['sample_id']] = {t['tool']: t for t in row['tools']}
    assets = {}
    locations = load(PRIVATE / 'mechanism_d2_readiness_20261013/local_asset_lookup.json')['matches']
    for cid in CASES:
        row = load(NATURAL / f'actor_backup/output/records/{cid}.json')
        prefix, raw = reconstruct_stop_context(row, row['relative_path'], prompt, cards, schema, lambda p: p, 4)
        assert raw == packets[cid]['current_raw_action'] == row['raw_terminal_text']
        expected = load(PRIVATE / 'mechanism_d2_readiness_20261013/context_check.json')['cases'][cid]
        assert canonical_hash(prefix + [{'role': 'assistant', 'content': raw}]) == expected['prefix_sha256']
        used = row['tool_calls']
        for step in row['steps'][:-1]:
            assert step['tool_observation'] == cache[cid][step['tool_observation']['tool']]
        prefix.append({'role': 'assistant', 'content': raw})
        cases[cid] = dict(prefix=prefix, original_raw=raw, used_tools=used, remaining=4-len(used),
                          original_parse_valid=row['raw_parse_valid'], original_input_tokens=expected['original_stop_input_tokens'],
                          original_image_grids=expected['original_stop_image_grids'])
        for path in frozen['assets']:
            if Path(path).stem == cid or Path(path).stem.startswith(cid + '_region_'):
                assert len(locations[path]) == 1 and sha256(ROOT / locations[path][0]) == frozen['assets'][path]
                assets[path] = {'file': path, 'sha256': frozen['assets'][path]}
        no_evaluation_fields(prefix)
        no_evaluation_fields(cache[cid])
        no_evaluation_fields(packets[cid])
    assert len(cases) == len(cache) == 4 and len(assets) == 16
    assert 3 * sum(c['remaining'] + 1 for c in cases.values()) == 18
    assert 3 * sum(c['remaining'] for c in cases.values()) == 6
    assert all(packets[c]['review_contract'] == packets[CASES[0]]['review_contract'] for c in CASES)
    rng = random.Random(20261016)
    order = list(CASES)
    rng.shuffle(order)
    arms, api_order, requests, index = {}, [], {}, {}
    for cid in order:
        arms[cid] = list(ARMS)
        rng.shuffle(arms[cid])
        pair = ['G', 'M']
        rng.shuffle(pair)
        for arm in pair:
            rid = cid + '_' + arm
            system = d1['messages'][cid + '_M0'][0] if arm == 'G' else d1b['messages'][cid + '_M2'][0]
            requests[rid] = [copy.deepcopy(system), copy.deepcopy(d1b['messages'][cid + '_M2'][1])]
            api_order.append(rid)
            index[rid] = {'case_id': cid, 'condition': arm}
        assert requests[cid+'_G'][1] == requests[cid+'_M'][1]
    allowance = sum(len(json.dumps(m, ensure_ascii=False).encode('utf8')) + 4096 for m in requests.values())
    upper_cost = (0.30 * allowance + 1.20 * 8 * 16384) / 1e6
    assert upper_cost <= 0.30
    package = dict(cases=cases, assets=assets, order=order, arm_order=arms, general=GENERAL, suffix=SUFFIX,
        review_contract=packets[CASES[0]]['review_contract'], model_spec={k: frozen[k] for k in ('model_revision','model_config_sha256')},
        generation={**generation, 'max_format_repairs_per_step': 0}, request_limit=18, cache_call_limit=6,
        adapter=None, dtype='bfloat16', training_steps=0)
    no_evaluation_fields(package)
    OUT.mkdir()
    for key, spec in assets.items():
        target = OUT / spec['file']
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / locations[key][0], target)
        assert sha256(target) == spec['sha256']
    dump(OUT/'approval.json', {'date':'2026-10-13', 'user_answer':'同意该范围、门槛和预算，先做准备',
        'plan_sha256':sha256(PLAN),'new_api_requests':8,'usd_cap':0.30,'actor_generations_max':18,
        'cache_returns_max':6,'new_format_retries':0,'verdict_projection':False,'gt_read':False,
        'reserved_groups_used':0,'gpu_run_requires_explicit_card_confirmation':True})
    dump(OUT/'inputs.json', package)
    dump(OUT/'dispatcher_cache.json', cache)
    dump(OUT/'expected_protection.json', frozen['expected_protection'])
    dump(OUT/'protected_sources.json', protected)
    shutil.copyfile(D1/'reference.json', OUT/'reference.json')
    dump(OUT/'monitor_inputs.json', dict(request_limit=8,usd_cap=0.30,endpoint=d1b['endpoint'],config=d1b['config'],
        order=api_order,request_index=index,messages=requests,input_token_byte_bound=allowance,
        peak_usd_cost_bound=upper_cost,seed=20261016,same_case_adjacent=True,retries=0))
    code = DEPLOY_CODE + ['experiments/faithbench_monitor_v0/monitor_mechanism_v1/run_d2.py',
        'experiments/faithbench_monitor_v0/monitor_mechanism_v1/run_d1.py',
        'experiments/actor_b/deepseek_monitor_pilot_v1/api_runner.py']
    files = {p.relative_to(ROOT).as_posix():sha256(p) for p in OUT.rglob('*') if p.is_file()}
    files.update({name:sha256(ROOT/name) for name in code})
    dump(OUT/'freeze.json', dict(files=files,request_limit=8,usd_cap=0.30,plan_sha256=sha256(PLAN),outputs_seen=False))
    print(json.dumps({'cases':4,'assets':16,'api_requests':8,'actor_generations_max':18,'cache_returns_max':6,
                      'input_byte_bound':allowance,'peak_usd_cost_bound':upper_cost,'gt_read':False,'model_requests':0}))


if __name__ == '__main__':
    prepare()
