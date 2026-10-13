"""Freeze two approved prompt interventions on the same 48 diagnostic payloads."""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
BASELINE = PRIVATE / 'relation_probe_v2_20261011'
OUT = PRIVATE / 'relation_prompt_probe_v1_20261011'
ORDER = 'JSON键的生成顺序固定为 reason、return_reference_ids、judgement；先写理由和引用，最后写judgement。字段和判断规则不变。'
RELATION = ('只审核 subject_to_review.claim，禁止替换成Actor上下文中的另一个主张。'
            '写reason时用实际字段名称和值对照主张中的属性、数值、比较或范围，说明必要关系成立、不成立或关键条件未给出。'
            '不同属性不得相互代替；当主张涉及全体，应核查证据覆盖范围；已给反证必须纳入；'
            '缺失内容不得从能力定义或邻近字段补齐。'
            '最后的judgement必须与该关系结论一致：只有主张及必要条件被实际返回支持才输出支持，其余输出无法据此支持。')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def prepare():
    for name, digest in json.loads((BASELINE / 'freeze.json').read_text(encoding='utf8')).items():
        assert sha(ROOT / name) == digest, name
    old = json.loads((BASELINE / 'inputs.json').read_text(encoding='utf8'))
    raw = BASELINE / 'backup/relation_probe_v2_trial/predictions.jsonl'
    completed = json.loads((BASELINE / 'backup/relation_probe_v2_trial/completed.json').read_text(encoding='utf8'))
    assert sha(raw) == completed['predictions_sha256'] and completed['predictions'] == 96
    requests = []
    for item in old['schedule']:
        instruction, payload_text = item['prompt'].split('\n输入：\n', 1)
        for condition, addition in [('reason_first', ORDER), ('relation_first', ORDER + '\n' + RELATION)]:
            prompt = instruction + '\n' + addition + '\n输入：\n' + payload_text
            assert json.loads(payload_text) == next(c['payload'] for c in old['cases'] if c['id'] == item['id'])
            requests.append({'id': item['id'], 'condition': condition, 'model': item['model'],
                             'prompt': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()})
    rng = random.Random(42)
    groups = sorted({c['group'] for c in old['cases']})
    rng.shuffle(groups)
    schedule = []
    for group in groups:
        block = [x for x in requests if x['id'].startswith(group + '_')]
        rng.shuffle(block)
        schedule.extend(block)
    assert len(schedule) == len({(x['id'], x['condition'], x['model']) for x in schedule}) == 192
    assert len({x['prompt_sha256'] for x in schedule}) == 96
    OUT.mkdir(exist_ok=False)
    runner = Path(__file__).parent / 'run_relation_prompt_probe_v1.py'
    with runner.open('x', encoding='utf8') as stream:
        stream.write((Path(__file__).parent / 'run_relation_probe_v2.py').read_text(encoding='utf8').replace(
            'Approved abstract relation pretest; frozen runtime, no training.',
            'Approved relation prompt comparison; frozen runtime, no training.'))
    package = copy.deepcopy(old)
    package.update(schedule=schedule, model_requests=192, logical_conditions=192, reused=[],
                   runner_sha256=sha(runner), baseline_input_sha256=sha(BASELINE / 'inputs.json'),
                   baseline_raw_sha256=sha(raw), interventions={'reason_first': ORDER, 'relation_first': ORDER + '\n' + RELATION},
                   historical_baseline_requests=96, output_order_requested=['reason', 'return_reference_ids', 'judgement'])
    dump(OUT / 'inputs.json', package)
    dump(OUT / 'review_expected.json', json.loads((BASELINE / 'review_expected.json').read_text(encoding='utf8')))
    manager = (BASELINE / 'remote_control_clone_14601.py').read_text(encoding='utf8')
    manager = manager.replace('relation_probe_v2_20261011', 'relation_prompt_probe_v1_20261011').replace('relation_probe_v2', 'relation_prompt_probe_v1')
    with (OUT / 'remote_control.py').open('x', encoding='utf8') as stream:
        stream.write(manager)
    files = [Path(__file__), runner, OUT / 'inputs.json', OUT / 'review_expected.json', OUT / 'remote_control.py',
             BASELINE / 'inputs.json', raw, BASELINE / 'first_review_locked.json', BASELINE / 'rereview_locked.json']
    dump(OUT / 'freeze.json', {p.relative_to(ROOT).as_posix(): sha(p) for p in files})
    dump(OUT / 'local_preflight.json', {'cases': 48, 'new_requests': 192, 'old_baseline_requests': 96,
         'same_payloads': True, 'independent_source_test': False, 'input_sha256': sha(OUT / 'inputs.json'),
         'reason_first_changes': 'output order only', 'relation_first_changes': 'output order plus bundled generic relation guidance',
         'model_loaded': False, 'training_steps': 0})
    print(json.dumps({'new_requests': 192, 'cases': 48, 'input_sha256': sha(OUT / 'inputs.json')}, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
