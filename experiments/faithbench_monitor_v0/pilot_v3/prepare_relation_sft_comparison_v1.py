"""Freeze the approved paired training execution without changing material v2."""
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'
OUT = PRIVATE / 'relation_sft_comparison_20261011'
MATERIAL = PRIVATE / 'relation_sft_materials_v2_20261011'
PROMPT = PRIVATE / 'relation_prompt_probe_v1_20261011'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def prepare():
    audit = read(MATERIAL / 'stage_audit.json')
    dependencies = dict(audit['artifact_hashes'])
    dependencies.update(read(MATERIAL / 'manifest.json')['dependency_hashes'])
    protocol = read(PRIVATE / 'monitor_iterations_20261010/sft_evidence_contract_v3_inputs/manifest.json')['protocol_hashes']
    dependencies.update(protocol)
    dependencies.update(read(PROMPT / 'freeze.json'))
    for name, digest in dependencies.items():
        assert sha(ROOT / name) == digest, name
    raw_path = PROMPT / 'backup/relation_prompt_probe_v1_trial/predictions.jsonl'
    assert sha(raw_path) == 'd7e6ff6fa8ad13c646325678872810b0fb8b3be0a2c88dcb0be4d9961ef240d4'
    old_package = read(PROMPT / 'inputs.json')
    assert old_package['seed'] == 42 and old_package['max_new_tokens'] == 384
    # Historical runner was frozen and explicitly used the same NF4/BF16/SDPA,
    # prepare_model_for_kbit_training and disabled-adapter base path.
    runner_old = ROOT / 'experiments/faithbench_monitor_v0/pilot_v3/run_relation_prompt_probe_v1.py'
    assert sha(runner_old) == old_package['runner_sha256']
    source = runner_old.read_text(encoding='utf8')
    for needle in ["bnb_4bit_quant_type='nf4'", "bnb_4bit_use_double_quant=True", "attn_implementation='sdpa'", 'use_reentrant', 'model.disable_adapter()', 'max_new_tokens=384', 'do_sample=False']:
        assert needle in source, needle
    reused = [row for line in raw_path.read_text(encoding='utf8').splitlines() if (row := json.loads(line))['model'] == 'base' and row['condition'] == 'reason_first']
    regression = read(MATERIAL / 'evaluation_regression.json')
    prompts = {row['id']: row['prompt'] for row in old_package['schedule'] if row['model'] == 'base' and row['condition'] == 'reason_first'}
    assert len(reused) == 48 and all(prompts[row['id']] == row['user_text'] for row in regression)
    train = {method: read(MATERIAL / ('train_' + method + '.json')) for method in ['ordinary', 'relation']}
    schedule = []
    rng = random.Random(42)
    for epoch in range(3):
        ids = [row['id'] for row in train['ordinary']]
        rng.shuffle(ids)
        schedule.extend(ids)
    dependencies[raw_path.relative_to(ROOT).as_posix()] = sha(raw_path)
    for path in [Path(__file__), Path(__file__).with_name('run_relation_sft_comparison_v1.py'), ROOT / 'docs/research/MONITOR_RELATION_SFT_EXECUTION_DISCUSSION_20261011.md']:
        dependencies[path.relative_to(ROOT).as_posix()] = sha(path)
    package = {'authorization': '用户明确回复可以：两组各216更新、204新推理、上传14601实例，约25–40分钟用卡', 'runner_sha256': sha(Path(__file__).with_name('run_relation_sft_comparison_v1.py')), 'frozen_dependencies': dependencies, 'train': train, 'schedule': schedule, 'held': read(MATERIAL / 'evaluation_held.json'), 'regression': regression, 'reused_base_regression': reused, 'expected_old_adapter': read(PROMPT / 'backup/relation_prompt_probe_v1_trial/frozen_before.json')['adapter'], 'new_requests': 204, 'optimizer_steps': 432, 'independent_test': False, 'human_gold': False, 'actor_actions_executed': False, 'token_difference_percent': 28.26086956521738}
    OUT.mkdir(exist_ok=False)
    dump(OUT / 'inputs.json', package)
    dump(OUT / 'expected_protection.json', read(PROMPT / 'backup/relation_prompt_probe_v1_trial/frozen_before.json')['protected'])
    dump(OUT / 'reuse_compatibility.json', {'historical_raw_sha256': sha(raw_path), 'reused_base_reason_first': 48, 'exact_prompt_matches': 48, 'runner_hash_verified': True, 'quantization': 'NF4_double_bf16', 'attention': 'sdpa', 'greedy': True, 'max_new_tokens': 384, 'disabled_adapter_base': True, 'seed': 42})
    dump(OUT / 'package_freeze.json', {p.relative_to(ROOT).as_posix(): sha(p) for p in OUT.glob('*.json')})
    print(json.dumps({'directory': str(OUT), 'inputs_sha256': sha(OUT / 'inputs.json'), 'new_requests': 204, 'updates': 432}))


if __name__ == '__main__':
    prepare()
