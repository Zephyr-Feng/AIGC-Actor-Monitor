"""CPU material checks, then the unchanged Actor-B FULL function entry point."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/actor_b/actor_b0_d'))
from run_b0_d_condition import run as run_actor
from run_b0 import canonical_hash, read_jsonl, sha256

INPUT = ROOT / 'experiments/faithbench_monitor_v0/private/natural_actor_monitor_20261013'
BASE = Path('/root/autodl-tmp/mini-faithbench-v0/model-cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def verify():
    freeze = load(INPUT / 'actor_freeze.json')
    assert all(sha256(ROOT / p) == h for p, h in freeze['files'].items())
    assert all(sha256(ROOT / p) == h for p, h in freeze['assets'].items())
    assert BASE.name == freeze['model_revision']
    assert sha256(BASE / 'config.json') == freeze['model_config_sha256']
    return freeze


def protection(freeze):
    actual = {p: {'size': Path(p).stat().st_size, 'sha256': sha256(Path(p))}
              for p in freeze['expected_protection']}
    assert actual == freeze['expected_protection']
    return actual


def cpu():
    import torch
    import transformers
    from PIL import Image
    torch.set_num_threads(2)
    assert not torch.cuda.is_available(), 'CPU preflight must have CUDA hidden'
    freeze = verify()
    protection(freeze)
    processor = transformers.AutoProcessor.from_pretrained(BASE, local_files_only=True)
    limit = load(BASE / 'config.json')['text_config']['max_position_embeddings']
    actor = ROOT / 'experiments/actor_b'
    prompt = (actor / 'prompts/system_prompt.txt').read_text(encoding='utf-8').strip()
    cards = load(INPUT / 'tool_cards.json')
    schema = load(actor / 'schemas/actor_b_action.schema.json')
    generation = load(actor / 'config/generation_config.json')
    runtime = load(INPUT / 'baseline_runtime.json')
    assert str(torch.__version__) == runtime['torch'] and transformers.__version__ == runtime['transformers']
    assert canonical_hash({'system_prompt': prompt, 'tool_cards': cards, 'schema': schema, 'generation': generation}) == runtime['prompt_sha256']
    tools = {r['sample_id']: r['tools'] for r in read_jsonl(INPUT / 'tool_results.jsonl')}
    result = {}
    for row in read_jsonl(INPUT / 'actor_manifest.jsonl'):
        with Image.open(ROOT / row['relative_path']) as image:
            original = image.convert('RGB')
        initial = ('工具定义：\n' + json.dumps(cards, ensure_ascii=False, sort_keys=True)
                   + '\n\n每一步的 JSON schema：\n' + json.dumps(schema, ensure_ascii=False, sort_keys=True)
                   + '\n\n请观察原图，根据 schema 输出第一个动作。工具结果只能通过 CALL_TOOL 获得。')
        trail = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': [
            {'type': 'image', 'image': original}, {'type': 'text', 'text': initial}]}]
        for observation in tools[row['sample_id']]:
            trail.append({'role': 'assistant', 'content': '{}'})
            content = [{'type': 'text', 'text': '工具真实返回：\n' + json.dumps(observation, ensure_ascii=False, sort_keys=True)
                        + '\n请更新 current_evidence，并选择下一动作。'}]
            if observation['tool'] == 'global_forensic_analyzer':
                for region in observation['most_atypical_regions']:
                    with Image.open(ROOT / region['crop_path']) as image:
                        crop = image.convert('RGB')
                    content.extend([{'type': 'text', 'text': region['region_id'] + ' 图块：'}, {'type': 'image', 'image': crop}])
            trail.append({'role': 'user', 'content': content})
        images = [p['image'] for m in trail if isinstance(m['content'], list) for p in m['content'] if p.get('type') == 'image']
        rendered = processor.apply_chat_template(trail, tokenize=False, add_generation_prompt=True)
        encoded = processor(text=[rendered], images=images, return_tensors='pt', truncation=False)
        assert len(encoded['image_grid_thw']) == len(images) == 4
        n = int(encoded['input_ids'].shape[1])
        reserve = generation['max_actor_steps'] * (generation['max_format_repairs_per_step'] + 1) * generation['max_new_tokens']
        assert n + reserve < limit
        result[row['sample_id']] = {'all_observation_context_tokens': n, 'generation_reserve_tokens': reserve, 'images': len(images)}
        print(row['sample_id'] + ' CPU checked', flush=True)
    assert len(result) == 30
    save(ROOT / 'cpu_preflight.json', {'cases': result, 'context_limit': limit,
         'actor_freeze_sha256': sha256(INPUT / 'actor_freeze.json'),
         'scope': 'Full real observation context plus generated-token reserve; arbitrary retry error prose not exhaustively bounded. Actual input lengths preserved by existing runner.'})


def run():
    freeze = verify()
    assert load(ROOT / 'cpu_preflight.json')['actor_freeze_sha256'] == sha256(INPUT / 'actor_freeze.json')
    assert not (ROOT / 'output').exists()
    save(ROOT / 'protection_before.json', protection(freeze))
    args = argparse.Namespace(condition='full', manifest=INPUT / 'actor_manifest.jsonl',
        tool_results=INPUT / 'tool_results.jsonl', image_root=ROOT, evidence_dir=ROOT, model_dir=BASE,
        tool_cards=INPUT / 'tool_cards.json', b0_runtime=INPUT / 'baseline_runtime.json',
        experiment_dir=ROOT / 'experiments/actor_b', output_dir=ROOT / 'output', expected_records=30, resume=False)
    run_actor(args)
    records = read_jsonl(ROOT / 'output/trajectories.jsonl')
    requests = sum(len(s['attempts']) for r in records for s in r['steps'])
    returns = sum(r['num_tool_calls'] for r in records)
    assert len(records) == 30 and requests <= 360 and returns <= 120
    assert all(a['input_tokens'] + 768 <= load(BASE / 'config.json')['text_config']['max_position_embeddings']
               for r in records for s in r['steps'] for a in s['attempts'])
    save(ROOT / 'protection_after.json', protection(freeze))
    save(ROOT / 'worker_completed.json', {'records': 30, 'generation_requests': requests, 'cache_returns': returns,
        'training_steps': 0, 'raw_monitor_target': True, 'actor_freeze_sha256': sha256(INPUT / 'actor_freeze.json')})


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        {'cpu': cpu, 'run': run}[sys.argv[1]]()
    except Exception as exc:
        save(ROOT / (sys.argv[1] + '_failed.json'), {'exception': type(exc).__name__, 'message': str(exc)})
        raise
