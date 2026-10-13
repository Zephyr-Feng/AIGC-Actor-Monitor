"""Approved paired relation SFT: two fresh adapters, 432 updates, 204 generations."""
import argparse
import contextlib
import gc
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KEYS = ['reason', 'return_reference_ids', 'judgement']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def event(name, **fields):
    print(json.dumps({'event': name, 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **fields}, ensure_ascii=False), flush=True)


def pack(tokenizer, row):
    messages = [{'role': 'user', 'content': row['user_text']}]
    prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    assert list(json.loads(row['assistant_text'])) == KEYS
    assert json.loads(row['assistant_text']) == row['answer']
    full = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': row['assistant_text']}], tokenize=True, add_generation_prompt=False)
    assert full[:len(prefix)] == prefix and len(prefix) < len(full) <= 4096
    return {'id': row['id'], 'input_ids': full, 'labels': [-100] * len(prefix) + full[len(prefix):], 'assistant_tokens': len(full) - len(prefix)}


def preflight(args):
    from transformers import AutoTokenizer
    package = json.loads(args.inputs.read_text(encoding='utf8'))
    assert sha(Path(__file__)) == package['runner_sha256']
    for name, digest in package['frozen_dependencies'].items():
        assert sha(ROOT / name) == digest, name
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    packed = {method: [pack(tokenizer, row) for row in package['train'][method]] for method in ['ordinary', 'relation']}
    ids = [row['id'] for row in package['train']['ordinary']]
    assert len(ids) == len(set(ids)) == 72
    for a, b in zip(package['train']['ordinary'], package['train']['relation']):
        assert a['id'] == b['id'] and a['user_text'] == b['user_text']
        assert a['answer']['judgement'] == b['answer']['judgement']
        assert a['answer']['return_reference_ids'] == b['answer']['return_reference_ids']
    assert len(package['schedule']) == 216 and all(package['schedule'].count(i) == 3 for i in ids)
    lengths = {}
    for row in package['held'] + package['regression']:
        text = row['user_text']
        assert hashlib.sha256(text.encode()).hexdigest() == row['prompt_sha256']
        prefix = tokenizer.apply_chat_template([{'role': 'user', 'content': text}], tokenize=True, add_generation_prompt=True)
        assert len(prefix) + 384 <= 4096
        lengths[row['id']] = len(prefix)
    assert len(package['held']) == 36 and len(package['regression']) == 48
    old = {row['id']: row for row in package['reused_base_regression']}
    assert len(old) == 48
    for row in package['regression']:
        assert old[row['id']]['prompt_sha256'] == row['prompt_sha256']
        assert old[row['id']]['input_tokens'] == lengths[row['id']]
    totals = {method: sum(row['assistant_tokens'] for row in rows) for method, rows in packed.items()}
    assert totals == {'ordinary': 3404, 'relation': 4366}, totals
    report = {'model_loaded': False, 'truncated': False, 'mask_verified': True, 'assistant_order': KEYS, 'updates_per_method': 216, 'new_requests': 204, 'reused_requests': 48, 'assistant_tokens_per_pass': totals, 'evaluation_lengths': lengths, 'input_sha256': sha(args.inputs)}
    return package, tokenizer, packed, report


def evaluate(model, tokenizer, rows, name, stream):
    import torch
    model.eval()
    model.config.use_cache = True
    for index, row in enumerate(rows, 1):
        event('evaluation_start', model=name, index=index, id=row['id'])
        started = time.monotonic()
        ids = tokenizer.apply_chat_template([{'role': 'user', 'content': row['user_text']}], tokenize=True, add_generation_prompt=True)
        tensor = torch.tensor([ids], device='cuda')
        with torch.inference_mode():
            generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor), do_sample=False, max_new_tokens=384, pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id, use_cache=True)
        raw = tokenizer.decode(generated[0, len(ids):], skip_special_tokens=True)
        record = {'id': row['id'], 'model': name, 'scope': row['evaluation_scope'], 'prompt_sha256': row['prompt_sha256'], 'raw': raw, 'input_tokens': len(ids), 'output_tokens': generated.shape[1] - len(ids), 'seconds': round(time.monotonic() - started, 4)}
        try:
            parsed = json.loads(raw)
            assert isinstance(parsed, dict) and set(parsed) == set(KEYS)
            assert parsed['judgement'] in ['支持', '无法据此支持']
            assert isinstance(parsed['reason'], str) and parsed['reason'].strip()
            assert isinstance(parsed['return_reference_ids'], list) and all(isinstance(x, str) for x in parsed['return_reference_ids'])
            payload = json.loads(row['user_text'].split('\n输入：\n', 1)[1])
            actual = {ref for mapping in payload['source_evidence']['return_field_references'] for ref in mapping.values()}
            record.update(parsed=parsed, parse_valid=True, actual_reference_ids_valid=set(parsed['return_reference_ids']) <= actual, reason_first=list(parsed) == KEYS, label_correct=parsed['judgement'] == row['expected_judgement'])
        except (ValueError, AssertionError, TypeError, KeyError):
            record['parse_valid'] = False
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        stream.flush()
        event('evaluation_end', model=name, index=index, valid=record['parse_valid'], seconds=record['seconds'])
        del tensor, generated


def trial(method, package, tokenizer, packed, args, stream):
    import torch
    from transformers import Qwen3VLForConditionalGeneration, BitsAndBytesConfig
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    destination = args.output / method
    destination.mkdir()
    random.seed(42)
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    event('load_start', method=method)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3VLForConditionalGeneration.from_pretrained(args.base, local_files_only=True, torch_dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False})
    model = get_peft_model(model, LoraConfig(task_type='CAUSAL_LM', r=8, lora_alpha=16, lora_dropout=0.05, target_modules=['q_proj', 'v_proj']))
    trainable = [(name, parameter) for name, parameter in model.named_parameters() if parameter.requires_grad]
    assert trainable and all('lora_' in name and 'language_model' in name for name, parameter in trainable)
    dump(destination / 'trainable_parameters.json', {'parameters': [{'name': name, 'shape': list(parameter.shape), 'numel': parameter.numel()} for name, parameter in trainable], 'total': sum(parameter.numel() for name, parameter in trainable)})
    event('load_end', method=method, trainable_parameters=sum(parameter.numel() for name, parameter in trainable))
    if method == 'ordinary':
        with model.disable_adapter():
            evaluate(model, tokenizer, package['held'], 'base', stream)
    # Base generation does not consume sampling RNG, but reset for paired dropout/init conditions.
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    model.train()
    model.config.use_cache = False
    optimizer = torch.optim.AdamW([parameter for name, parameter in trainable], lr=2e-4)
    by_id = {row['id']: row for row in packed[method]}
    with (destination / 'training.jsonl').open('x', encoding='utf8') as log:
        for step, sample_id in enumerate(package['schedule'], 1):
            row = by_id[sample_id]
            event('training_start', method=method, step=step, id=sample_id)
            start = time.monotonic()
            tensor = torch.tensor([row['input_ids']], device='cuda')
            labels = torch.tensor([row['labels']], device='cuda')
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                result = model(input_ids=tensor, attention_mask=torch.ones_like(tensor), labels=labels, use_cache=False)
                loss = result.loss
            assert torch.isfinite(loss)
            loss.backward()
            grad = torch.nn.utils.clip_grad_norm_([parameter for name, parameter in trainable], 1.0)
            assert torch.isfinite(grad)
            assert not any(parameter.grad is not None for parameter in model.parameters() if not parameter.requires_grad)
            optimizer.step()
            record = {'step': step, 'epoch': (step - 1) // 72 + 1, 'id': sample_id, 'loss': float(loss.detach()), 'grad_norm': float(grad), 'assistant_tokens': row['assistant_tokens'], 'seconds': round(time.monotonic() - start, 4)}
            log.write(json.dumps(record) + '\n')
            log.flush()
            event('training_end', method=method, **record)
            del tensor, labels, result, loss, grad
    model.save_pretrained(destination / 'adapter', safe_serialization=True)
    event('adapter_saved', method=method)
    evaluate(model, tokenizer, package['held'] + package['regression'], method, stream)
    dump(destination / 'runtime.json', {'steps': 216, 'seconds': time.monotonic() - started, 'peak_allocated_bytes': torch.cuda.max_memory_allocated(), 'peak_reserved_bytes': torch.cuda.max_memory_reserved()})
    del optimizer, trainable, model
    gc.collect()
    torch.cuda.empty_cache()


def run(args):
    package, tokenizer, packed, report = preflight(args)
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output / 'preflight.json', report)
    if args.preflight_only:
        event('cpu_preflight', updates=432, new_requests=204, mask_verified=True)
        return
    sys.path.insert(0, str(ROOT / 'experiments/faithbench_monitor_v0/sft_smoke_v1'))
    from train_smoke import frozen_snapshot
    before = frozen_snapshot(args.base)
    assert before == json.loads(args.expected_protection.read_text(encoding='utf8'))
    old_adapter = {p.name: sha(p) for p in args.old_adapter.iterdir() if p.is_file()}
    assert old_adapter == package['expected_old_adapter']
    dump(args.output / 'frozen_before.json', {'protected': before, 'old_adapter': old_adapter})
    dump(args.output / 'runtime.json', {'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'base': str(args.base), 'seed': 42, 'quantization': 'NF4_double_bf16', 'attention': 'sdpa', 'learning_rate': 2e-4, 'lora_r': 8, 'lora_alpha': 16, 'lora_dropout': 0.05, 'target_modules': ['q_proj', 'v_proj'], 'updates_per_method': 216, 'new_requests': 204, 'max_new_tokens': 384, 'batch_size': 1, 'gradient_accumulation': 1, 'actor_actions_executed': False})
    with (args.output / 'predictions.jsonl').open('x', encoding='utf8') as stream:
        for method in ['ordinary', 'relation']:
            trial(method, package, tokenizer, packed, args, stream)
    after = frozen_snapshot(args.base)
    adapter_after = {p.name: sha(p) for p in args.old_adapter.iterdir() if p.is_file()}
    assert before == after and old_adapter == adapter_after
    # Recheck code/data freezes after GPU work.
    for name, digest in package['frozen_dependencies'].items():
        assert sha(ROOT / name) == digest, name
    dump(args.output / 'frozen_after.json', {'protected': after, 'old_adapter': adapter_after})
    assert len((args.output / 'predictions.jsonl').read_text(encoding='utf8').splitlines()) == 204
    dump(args.output / 'completed.json', {'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'optimizer_steps': 432, 'predictions': 204, 'protected_unchanged': True, 'old_adapter_unchanged': True, 'actor_actions_executed': False, 'input_sha256': sha(args.inputs), 'predictions_sha256': sha(args.output / 'predictions.jsonl')})
    event('completed', optimizer_steps=432, predictions=204)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['inputs', 'base', 'output', 'expected-protection', 'old-adapter']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    run(parser.parse_args())
