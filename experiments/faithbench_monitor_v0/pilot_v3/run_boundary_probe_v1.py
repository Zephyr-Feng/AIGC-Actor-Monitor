"""Boundary probe runner derived from minimal_screen_v1; 22 new requests."""
import argparse
import contextlib
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def run(args):
    sys.path.insert(0, str(ROOT / 'experiments/faithbench_monitor_v0/sft_smoke_v1'))
    from train_smoke import frozen_snapshot
    from transformers import AutoTokenizer
    package = json.loads(args.inputs.read_text(encoding='utf8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    assert sha(args.manifest) == package['manifest_sha256']
    assert sha(Path(__file__)) == package['runner_sha256']
    for name, digest in manifest['protocol_hashes'].items():
        assert sha(ROOT / name) == digest, name
    schedule = package['schedule']
    assert len(schedule) == 22 and len({(r['id'], r['condition'], r['model']) for r in schedule}) == 22
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    packed = [(r, tokenizer.apply_chat_template([{'role': 'user', 'content': r['prompt']}], tokenize=True, add_generation_prompt=True)) for r in schedule]
    assert all(len(ids) + 384 <= 4096 for _, ids in packed), 'no truncation allowed'
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output / 'preflight.json', {'model_loaded': False, 'truncated': False, 'lengths': [{k: r[k] for k in ['id', 'condition', 'model']} | {'tokens': len(ids)} for r, ids in packed]})
    if args.preflight_only:
        return
    import torch
    from transformers import Qwen3VLForConditionalGeneration, BitsAndBytesConfig
    from peft import PeftModel, prepare_model_for_kbit_training
    before = frozen_snapshot(args.base)
    assert before == json.loads(args.expected_protection.read_text(encoding='utf8'))
    adapter_before = {p.name: sha(p) for p in args.adapter.iterdir() if p.is_file()}
    expected_adapter = json.loads(args.expected_adapter.read_text(encoding='utf8'))
    assert adapter_before['adapter_model.safetensors'] == expected_adapter['sha256']
    assert adapter_before['adapter_config.json'] == expected_adapter['config_sha256']
    dump(args.output / 'frozen_before.json', {'protected': before, 'adapter': adapter_before})
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    base = Qwen3VLForConditionalGeneration.from_pretrained(args.base, local_files_only=True, torch_dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False})
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False, local_files_only=True)
    model.eval()
    model.config.use_cache = True
    assert not any(p.requires_grad for p in model.parameters())
    with (args.output / 'predictions.jsonl').open('x', encoding='utf8') as stream:
        for index, (item, ids) in enumerate(packed, 1):
            print(json.dumps({'event': 'start', 'index': index, 'id': item['id'], 'condition': item['condition'], 'model': item['model']}), flush=True)
            started = time.monotonic()
            tensor = torch.tensor([ids], device='cuda')
            context = model.disable_adapter() if item['model'] == 'base' else contextlib.nullcontext()
            with context, torch.inference_mode():
                generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor), do_sample=False, max_new_tokens=384, pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id, use_cache=True)
            raw = tokenizer.decode(generated[0, len(ids):], skip_special_tokens=True)
            record = {k: item[k] for k in ['id', 'condition', 'model', 'prompt_sha256']}
            record.update(raw=raw, input_tokens=len(ids), output_tokens=generated.shape[1] - len(ids), seconds=time.monotonic() - started)
            try:
                parsed = json.loads(raw)
                keys = {'judgement', 'reason'} | ({'return_reference_ids'} if item['condition'] != 'A' else set())
                assert isinstance(parsed, dict) and set(parsed) == keys
                assert parsed['judgement'] in ['支持', '无法据此支持'] and isinstance(parsed['reason'], str)
                if item['condition'] != 'A':
                    assert isinstance(parsed['return_reference_ids'], list) and all(isinstance(x, str) for x in parsed['return_reference_ids'])
                record.update(parsed=parsed, parse_valid=True)
            except (ValueError, AssertionError, TypeError):
                record['parse_valid'] = False
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            stream.flush()
            print(json.dumps({'event': 'end', 'index': index, 'seconds': record['seconds']}), flush=True)
            del tensor, generated
    del model, base
    torch.cuda.empty_cache()
    after = frozen_snapshot(args.base)
    adapter_after = {p.name: sha(p) for p in args.adapter.iterdir() if p.is_file()}
    assert before == after and adapter_before == adapter_after
    dump(args.output / 'completed.json', {'predictions': 22, 'optimizer_steps': 0, 'protected_unchanged': True, 'adapter_unchanged': True, 'actor_actions_executed': False, 'input_sha256': sha(args.inputs), 'predictions_sha256': sha(args.output / 'predictions.jsonl')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['inputs', 'manifest', 'base', 'adapter', 'output', 'expected-protection', 'expected-adapter']:
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    run(args)
