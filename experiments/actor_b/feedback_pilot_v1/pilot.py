"""One frozen Actor case, three independent feedback branches; CPU prepare first."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ACTOR = ROOT / 'experiments/actor_b'
sys.path.insert(0, str(ACTOR))
from actor_b_protocol import parse_action
from contract_replay import reconstruct_stop_context
from run_b0 import canonical_hash, sha256

PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private/actor_feedback_pilot_v1_20261011'
SOURCE = ACTOR / 'actor_b0_d/audit_assist/work/full/trajectories.jsonl'
SUFFIX = '上一条是尚未执行的动作提议。请依据当前已有信息，输出下一步的一个完整 Actor-B JSON 动作。工具可用性与剩余额度沿用原状态；尚未调用的工具没有新返回，不得编造。可以维持或修正提议；若停止，真假标签仍只使用 real 或 fake。解释使用中文。'
GENERAL = '外部审核提醒：请让当前提议中的观察、解释和综合理由忠实对应已有工具返回与工具能力限制，区分观察与推断，保留有依据的判断与尚未解决的不确定性，并据此更新下一步提议。'
TARGETED = '外部审核反馈：你在上一条 action_reason 中，将全局表征高偏离解释为“强烈暗示图像非真实拍摄”，并在全局证据条目中写“极可能为AI生成图像”；evidence_gap 又把元数据缺失、局部纹理合成倾向和全局表征偏离合称“结论高度一致”。全局工具的实际返回明确说明：偏离不构成图像来源证明，罕见真实内容或后处理也可能产生高值；来源工具返回的是无法判断，缺少元数据不能作为伪造证据。请修正这些证据的用途及依赖它们的一致支持表述。局部纹理的合成倾向是真实返回，应保留，同时保留其可能误报、强度未校准的限制。请据此重新说明当前判断依据和证据缺口，再决定下一步。此反馈没有提供新的检测结果，也不指定图像应判真实或伪造。'
FEEDBACK = {'R': SUFFIX, 'G': GENERAL + '\n\n' + SUFFIX, 'T': TARGETED + '\n\n' + SUFFIX}
EXPECTED = {
    'source': 'aede0ace6b158be188b98b8f70d1ec2e30cb5cbd2c34b0a105ad60f5b90eae20',
    'cards': '4bea66b6aad42ff93ed7a4ff128b5094550e81fb72f1b8452fdfb464a98867fb',
    'config': '5cd452860dc1e9c29dd71cc3cef7f39b338b7a40793f7a260655c2d3568f3661',
}
DEPENDENCIES = [
    'experiments/actor_b/actor_b_protocol.py', 'experiments/actor_b/contract_replay.py',
    'experiments/actor_b/run_b0.py', 'experiments/actor_b/prompts/system_prompt.txt',
    'experiments/actor_b/schemas/actor_b_action.schema.json',
    'experiments/actor_b/config/generation_config.json', 'experiments/actor_b/config/model_config.json',
    'experiments/mini_faithbench_v0/config/tool_cards.json',
]


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def no_evaluation_fields(value):
    forbidden = {'gt', 'ground_truth', 'generator', 'source_group', 'label', 'labels',
                 'identity_map', 'silver', 'expected_answer', 'targets'}
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in forbidden or 'correct' in key.lower() or 'accuracy' in key.lower():
                raise ValueError(f'evaluation field in model input: {key}')
            no_evaluation_fields(item)
    elif isinstance(value, list):
        for item in value:
            no_evaluation_fields(item)


def prepare():
    if PRIVATE.exists():
        raise FileExistsError(f'Preparation already exists; inspect it: {PRIVATE}')
    cards_path = ROOT / DEPENDENCIES[-1]
    assert sha256(SOURCE) == EXPECTED['source']
    assert sha256(cards_path) == EXPECTED['cards']
    matches = [json.loads(line) for line in SOURCE.read_text(encoding='utf-8').splitlines()
               if json.loads(line).get('sample_id') == 'blind_003']
    assert len(matches) == 1
    row = matches[0]
    assert row['condition'] == 'FULL' and row['raw_parse_valid'] and len(row['steps']) == 4
    assert row['tool_calls'] == ['provenance_inspector', 'local_texture_analyzer', 'global_forensic_analyzer']
    assert all(len(step['attempts']) == 1 and step['parse_error'] is None for step in row['steps'])
    fingerprint = json.loads((ACTOR / 'actor_b0_d/audit_assist/input_fingerprint.json').read_text(encoding='utf-8'))
    paths = [Path(row['image_path']), *map(Path, row['observed_crop_paths'])]
    assert len(paths) == 4
    for path in paths:
        expected = (fingerprint['image_hashes'] if path.stem == 'blind_003' else fingerprint['crop_hashes'])[path.stem]
        assert sha256(path) == expected, path.name
    prompt = (ACTOR / 'prompts/system_prompt.txt').read_text(encoding='utf-8').strip()
    schema = json.loads((ACTOR / 'schemas/actor_b_action.schema.json').read_text(encoding='utf-8'))
    cards = json.loads(cards_path.read_text(encoding='utf-8'))
    generation = json.loads((ACTOR / 'config/generation_config.json').read_text(encoding='utf-8'))
    spec = json.loads((ACTOR / 'config/model_config.json').read_text(encoding='utf-8'))
    pre_stop, raw = reconstruct_stop_context(row, row['image_path'], prompt, cards, schema,
                                             lambda path: path, generation['max_tool_calls'])
    assert parse_action(raw, set(row['tool_calls'])) == row['steps'][-1]['actor_output']
    prefix = pre_stop + [{'role': 'assistant', 'content': raw}]
    branches = {arm: copy.deepcopy(prefix) + [{'role': 'user', 'content': text}]
                for arm, text in FEEDBACK.items()}
    assert all(canonical_hash(messages[:-1]) == canonical_hash(prefix) for messages in branches.values())
    assert len({canonical_hash(messages) for messages in branches.values()}) == 3
    for messages in branches.values():
        no_evaluation_fields(messages)
        images = [p['image'] for m in messages if isinstance(m['content'], list)
                  for p in m['content'] if p.get('type') == 'image']
        assert images == [str(path).replace('\\', '/') for path in paths]
    # Actual shared dependency is deliberately mutated in this smoke check.
    probe = copy.deepcopy(branches)
    probe['R'][0]['content'] = 'CPU isolation probe'
    assert probe['G'] == branches['G'] and probe['T'] == branches['T']
    original = parse_action(raw, set(row['tool_calls']))
    call = copy.deepcopy(original)
    call.update(next_action='CALL_TOOL', selected_tool='complementary_forensic_analyzer',
                final_verdict=None, final_confidence=None)
    parse_action(json.dumps(call, ensure_ascii=False), set(row['tool_calls']))
    bad = copy.deepcopy(call)
    bad['selected_tool'] = row['tool_calls'][0]
    try:
        parse_action(json.dumps(bad), set(row['tool_calls']))
    except ValueError:
        pass
    else:
        raise AssertionError('parser accepted repeated CALL')
    order = list(FEEDBACK)
    random.Random(20261011).shuffle(order)
    asset_index = {str(path).replace('\\', '/'): {'file': 'assets/' + path.name, 'sha256': sha256(path)}
                   for path in paths}
    package = {'case_id': 'blind_003', 'condition': 'FULL', 'messages': branches,
               'pre_stop_messages': pre_stop, 'prefix_sha256': canonical_hash(prefix),
               'used_tools': row['tool_calls'], 'remaining_tool_calls': 1, 'assets': asset_index,
               'order': order, 'model_spec': spec,
               'generation': {**generation, 'max_format_repairs_per_step': 0},
               'request_limit': 3, 'training_steps': 0, 'execute_tools': False,
               'dependencies': {name: sha256(ROOT / name) for name in DEPENDENCIES}}
    no_evaluation_fields(package)
    PRIVATE.mkdir()
    (PRIVATE / 'assets').mkdir()
    for path in paths:
        shutil.copyfile(path, PRIVATE / 'assets' / path.name)
    dump(PRIVATE / 'case.json', row)
    dump(PRIVATE / 'inputs.json', package)
    dump(PRIVATE / 'feedback.json', FEEDBACK)
    criteria = {'reviewer_type': None, 'review_is_blind': None, 'criteria': [
        '目标证据角色误用及依赖综合修复，字段一致', '局部真实合成倾向与局限保留',
        '无新增事实、对象、数值或工具结果错误', '原parser与预算可执行'],
        'complete_local_repair_requires_all': True, 'classification_accuracy_evaluated': False,
        'arms': {arm: {'review_status': 'pending', 'quotes': [], 'criteria_results': None} for arm in FEEDBACK}}
    dump(PRIVATE / 'review_template.json', criteria)
    checks = {'source_hash_verified': True, 'asset_fingerprint_matches': 4, 'prefix_identical': True,
              'branches_isolated': True, 'model_input_evaluation_fields_absent': True,
              'image_parts_per_arm': 4, 'original_stop_parses': True,
              'synthetic_unused_call_parses': True, 'synthetic_repeated_call_rejected': True,
              'historical_attempts_per_step': [1, 1, 1, 1], 'remaining_calls': 1,
              'historical_input_tokens': 4121, 'model_requests': 0, 'processor_check_pending': True}
    dump(PRIVATE / 'structural_checks.json', checks)
    files = [p for p in PRIVATE.rglob('*') if p.is_file()]
    freeze = {'files': {p.relative_to(PRIVATE).as_posix(): sha256(p) for p in files},
              'dependencies': package['dependencies'],
              'scripts': {Path(__file__).relative_to(ROOT).as_posix(): sha256(Path(__file__)),
                         'experiments/actor_b/feedback_pilot_v1/control.py': sha256(Path(__file__).with_name('control.py'))},
              'plan_sha256': sha256(ROOT / 'docs/research/ACTOR_CORRECT_FEEDBACK_PILOT_PLAN_20261011.md')}
    dump(PRIVATE / 'freeze.json', freeze)
    print(json.dumps({'prepared': True, 'order': order, 'structural_checks': checks}, ensure_ascii=False))


def verify(package_dir):
    freeze = json.loads((package_dir / 'freeze.json').read_text(encoding='utf-8'))
    for name, digest in freeze['files'].items():
        assert sha256(package_dir / name) == digest, name
    for name, digest in {**freeze['dependencies'], **freeze['scripts']}.items():
        assert sha256(ROOT / name) == digest, name
    return json.loads((package_dir / 'inputs.json').read_text(encoding='utf-8'))


def cpu_check(package, model_dir, load_asset):
    import transformers
    from PIL import Image
    import io
    config = json.loads((model_dir / 'config.json').read_text())
    assert sha256(model_dir / 'config.json') == package['model_spec']['model_config_sha256']
    assert package['model_spec']['model_revision'] in model_dir.parts
    processor = transformers.AutoProcessor.from_pretrained(model_dir, local_files_only=True)
    def encode(messages):
        hydrated = copy.deepcopy(messages)
        images = []
        for message in hydrated:
            if isinstance(message['content'], list):
                for part in message['content']:
                    if part.get('type') == 'image':
                        raw = load_asset(part['image'])
                        assert hashlib.sha256(raw).hexdigest() == package['assets'][part['image']]['sha256']
                        with Image.open(io.BytesIO(raw)) as source:
                            image = source.convert('RGB')
                        part['image'] = image
                        images.append(image)
        rendered = processor.apply_chat_template(hydrated, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[rendered], images=images, return_tensors='pt', truncation=False)
        assert len(images) == 4 and len(inputs['image_grid_thw']) == 4
        return inputs
    historical = encode(package['pre_stop_messages'])
    rows = []
    for arm in package['order']:
        inputs = encode(package['messages'][arm])
        n = int(inputs['input_ids'].shape[1])
        assert n + package['generation']['max_new_tokens'] <= config['text_config']['max_position_embeddings']
        rows.append({'arm': arm, 'input_tokens': n, 'image_grids': inputs['image_grid_thw'].tolist(),
                     'images': 4, 'max_new_tokens': 768, 'truncated': False})
    report = {'model_loaded': False, 'model_requests': 0, 'optimizer_steps': 0,
              'transformers': transformers.__version__, 'historical_reference_tokens': 4121,
              'blinded_pre_stop_tokens': int(historical['input_ids'].shape[1]),
              'exact_original_token_reproduction_claimed': False,
              'max_position_embeddings': config['text_config']['max_position_embeddings'], 'branches': rows,
              'processor_assets': {p.name: sha256(p) for p in model_dir.iterdir()
                                   if p.is_file() and p.suffix in ('.json', '.txt', '.jinja')},
              'input_ids_sha256': {arm: hashlib.sha256(encode(package['messages'][arm])['input_ids'].numpy().tobytes()).hexdigest()
                                   for arm in package['order']}}
    return report, processor, encode


def execute(package_dir, model_dir, output):
    import torch
    import transformers
    package = verify(package_dir)
    assert package['request_limit'] == 3 and set(package['order']) == {'R', 'G', 'T'}
    output.mkdir(exist_ok=False)
    report, processor, encode = cpu_check(package, model_dir,
        lambda key: (package_dir / package['assets'][key]['file']).read_bytes())
    dump(output / 'preflight.json', report)
    torch.manual_seed(20261006)
    torch.cuda.manual_seed_all(20261006)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        model_dir, dtype=torch.bfloat16, device_map='cuda', local_files_only=True).eval()
    try:
        for arm in package['order']:
            inputs = {k: v.to('cuda') for k, v in encode(package['messages'][arm]).items()}
            n = int(inputs['input_ids'].shape[1])
            torch.cuda.synchronize()
            start = time.perf_counter()
            with torch.inference_mode():
                generated = model.generate(**inputs, max_new_tokens=768, do_sample=False, repetition_penalty=1.05)
            torch.cuda.synchronize()
            tokens = generated[0][n:]
            raw = processor.decode(tokens, skip_special_tokens=True)
            try:
                parsed, error = parse_action(raw, set(package['used_tools'])), None
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                parsed, error = None, str(exc)
            result = {'arm': arm, 'raw': raw, 'parsed': parsed, 'parse_error': error,
                      'input_tokens': n, 'output_tokens': len(tokens), 'at_token_limit': len(tokens) >= 768,
                      'seconds': time.perf_counter() - start, 'actual_tool_calls': 0}
            dump(output / f'{arm}.json', result)
            print(json.dumps({'arm': arm, 'generated': True, 'parse_valid': parsed is not None}), flush=True)
        dump(output / 'completed.json', {'requests': 3, 'training_steps': 0, 'actual_tool_calls': 0,
              'torch': torch.__version__, 'transformers': transformers.__version__,
              'model_revision': package['model_spec']['model_revision'], 'dtype': 'bfloat16',
              'inputs_sha256': sha256(package_dir / 'inputs.json')})
    finally:
        del model
        torch.cuda.empty_cache()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'verify', 'cpu', 'run'])
    parser.add_argument('--package', type=Path, default=PRIVATE)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
    elif args.mode == 'verify':
        verify(args.package)
        print('freeze verified')
    elif args.mode == 'cpu':
        import os
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        package = verify(args.package)
        report, _, _ = cpu_check(package, args.base,
            lambda key: (args.package / package['assets'][key]['file']).read_bytes())
        dump(args.output, report)
        print(json.dumps(report))
    else:
        execute(args.package, args.base, args.output)
