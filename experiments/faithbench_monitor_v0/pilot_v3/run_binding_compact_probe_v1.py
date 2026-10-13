"""Six authorized fresh-base generations; no adapter, optimizer or Actor action."""
import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ORDER = ('bindings', 'checks', 'reason', 'return_reference_ids', 'judgement')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def run(args):
    package = json.loads(args.inputs.read_text(encoding='utf-8'))
    assert sha(Path(__file__)) == package['runner_sha256']
    assert package['model_requests'] == len(package['records']) == 6
    assert len({r['id'] for r in package['records']}) == 6
    for name, digest in package['frozen_dependencies'].items():
        assert sha(ROOT / name) == digest, name
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    packed = []
    for row in package['records']:
        assert hashlib.sha256(row['prompt'].encode()).hexdigest() == row['prompt_sha256']
        ids = tokenizer.apply_chat_template([{'role': 'user', 'content': row['prompt']}], tokenize=True, add_generation_prompt=True)
        assert len(ids) + 384 <= 4096
        assert len(ids) == row['local_input_tokens']
        packed.append((row, ids))
    args.output.mkdir(exist_ok=False)
    dump(args.output / 'preflight.json', dict(model_loaded=False, truncated=False,
        rows=[dict(id=r['id'], input_tokens=len(ids)) for r, ids in packed]))
    if args.preflight_only:
        return
    sys.path.insert(0, str(ROOT / 'experiments/faithbench_monitor_v0/sft_smoke_v1'))
    from train_smoke import frozen_snapshot
    before = frozen_snapshot(args.base)
    assert before == json.loads(args.expected_protection.read_text(encoding='utf-8'))
    old_adapter_before = {name: sha(args.old_adapter / name) for name in package['old_adapter_hashes']}
    assert old_adapter_before == package['old_adapter_hashes']
    dump(args.output / 'frozen_before.json', dict(protected=before, old_adapter=old_adapter_before))
    import torch
    from transformers import Qwen3VLForConditionalGeneration, BitsAndBytesConfig
    from peft import prepare_model_for_kbit_training
    dump(args.output / 'runtime.json', dict(base=str(args.base), adapter_loaded=False,
        model_requests=6, optimizer_steps=0, seed=42, greedy=True, max_new_tokens=384,
        quantization='NF4_double_bf16', attention='sdpa', frozen_prepare_cast=True,
        versions={name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'peft', 'bitsandbytes')}))
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3VLForConditionalGeneration.from_pretrained(args.base, local_files_only=True,
        torch_dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False})
    assert not any(p.requires_grad for p in model.parameters())
    model.eval()
    model.config.use_cache = True
    with (args.output / 'predictions.jsonl').open('x', encoding='utf-8') as stream:
        for index, (row, ids) in enumerate(packed, 1):
            print(json.dumps(dict(event='start', index=index, id=row['id'])), flush=True)
            started = time.monotonic()
            tensor = torch.tensor([ids], device='cuda')
            with torch.inference_mode():
                generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                    do_sample=False, max_new_tokens=384, pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id, use_cache=True)
            raw = tokenizer.decode(generated[0, len(ids):], skip_special_tokens=True)
            record = dict(id=row['id'], model='fresh_frozen_base', prompt_sha256=row['prompt_sha256'],
                raw=raw, input_tokens=len(ids), output_tokens=generated.shape[1] - len(ids),
                max_new_tokens=384, seconds=time.monotonic() - started)
            try:
                parsed = json.loads(raw)
                assert isinstance(parsed, dict) and set(parsed) == set(ORDER)
                record.update(parsed=parsed, parse_valid=True, output_order_correct=list(parsed) == list(ORDER))
            except (ValueError, AssertionError, TypeError):
                record['parse_valid'] = False
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            stream.flush()
            print(json.dumps(dict(event='end', index=index, seconds=record['seconds'], output_tokens=record['output_tokens'])), flush=True)
            del tensor, generated
    del model
    torch.cuda.empty_cache()
    after = frozen_snapshot(args.base)
    old_adapter_after = {name: sha(args.old_adapter / name) for name in package['old_adapter_hashes']}
    assert before == after and old_adapter_before == old_adapter_after
    for name, digest in package['frozen_dependencies'].items():
        assert sha(ROOT / name) == digest, name
    dump(args.output / 'completed.json', dict(model_requests=6, optimizer_steps=0,
        protected_unchanged=True, old_adapter_unchanged=True, frozen_dependencies_unchanged=True,
        actor_actions_executed=False, input_sha256=sha(args.inputs),
        predictions_sha256=sha(args.output / 'predictions.jsonl'), finished_at=time.strftime('%Y-%m-%dT%H:%M:%S%z')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['inputs', 'base', 'output', 'expected-protection', 'old-adapter']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    run(parser.parse_args())
