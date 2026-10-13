"""Candidate inference only; requires an approved launch and frozen inputs."""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent.parent / 'sft_smoke_v1'))
from train_smoke import frozen_snapshot, sha
from structured_source_candidate_v2 import candidate_prompt
from experiments.faithbench_monitor_v0.sft_evidence_contract_v3 import contract


def dump(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def run(args):
    from transformers import AutoTokenizer
    package = json.loads(args.inputs.read_text(encoding='utf8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf8'))
    if sha(args.manifest) != package['source_manifest_sha256']:
        raise ValueError('source manifest mismatch')
    for name, expected in manifest['protocol_hashes'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('protocol changed: ' + name)
    for name, key in [('structured_source_candidate_v2.py', 'candidate_code_sha256'), ('region_field_contract.md', 'field_contract_sha256')]:
        if sha(Path(__file__).parent / name) != package[key]:
            raise ValueError('candidate dependency changed')
    rows = {row['id']: row for row in package['materials']}
    schedule = package['schedule_not_executed']
    if len(rows) != 13 or len(schedule) != 25:
        raise ValueError('unexpected scope')
    for row in rows.values():
        data = row['original_data']
        if row['baseline_prompt'] != contract.prompt(data) or row['schema'] != contract.schema(data):
            raise ValueError('original prompt/schema changed')
        if row['candidate_prompt'] != candidate_prompt(row['baseline_prompt'], data):
            raise ValueError('candidate mismatch')
    for protected in [args.base, args.adapter]:
        if args.output.resolve().is_relative_to(protected.resolve()) or protected.resolve().is_relative_to(args.output.resolve()):
            raise ValueError('output overlaps protected files')
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    packed = []
    for item in schedule:
        ids = tokenizer.apply_chat_template([{'role': 'user', 'content': rows[item['id']][item['condition'] + '_prompt']}], tokenize=True, add_generation_prompt=True)
        if len(ids) + 384 > 4096:
            raise ValueError('no truncation: ' + item['id'])
        packed.append((item, ids))
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output / 'tokenizer_preflight.json', {'rows': 25, 'max_input_tokens': max(len(ids) for _, ids in packed), 'truncated': False, 'model_loaded': False})
    if args.preflight_only:
        return
    import torch
    from transformers import Qwen3VLForConditionalGeneration, BitsAndBytesConfig
    from peft import PeftModel, prepare_model_for_kbit_training
    before = frozen_snapshot(args.base)
    if before != json.loads(args.expected_protection.read_text(encoding='utf8')):
        raise ValueError('Actor/base changed')
    adapter_before = {p.name: sha(p) for p in args.adapter.iterdir() if p.is_file()}
    expected_adapter = json.loads(args.expected_adapter.read_text(encoding='utf8'))
    if adapter_before.get('adapter_model.safetensors') != expected_adapter['sha256']:
        raise ValueError('adapter weight changed')
    if adapter_before.get('adapter_config.json') != expected_adapter['config_sha256']:
        raise ValueError('adapter configuration changed')
    dump(args.output / 'frozen_before.json', {'protected': before, 'adapter': adapter_before})
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    base = Qwen3VLForConditionalGeneration.from_pretrained(args.base, local_files_only=True, torch_dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False})
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False, local_files_only=True)
    model.eval()
    model.config.use_cache = True
    if any(p.requires_grad for p in model.parameters()):
        raise ValueError('unexpected trainable parameter')
    with (args.output / 'predictions.jsonl').open('x', encoding='utf8') as stream:
        for index, (item, ids) in enumerate(packed, 1):
            print(json.dumps({'event': 'start', 'index': index, **item}), flush=True)
            started = time.monotonic()
            tensor = torch.tensor([ids], device='cuda')
            with torch.inference_mode():
                generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor), do_sample=False, max_new_tokens=384, pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id, use_cache=True)
            raw = tokenizer.decode(generated[0, len(ids):], skip_special_tokens=True)
            record = {**item, 'raw': raw, 'input_tokens': len(ids), 'output_tokens': generated.shape[1] - len(ids), 'seconds': time.monotonic() - started}
            try:
                record.update(parsed=contract.parse(raw, rows[item['id']]['original_data']), parse_valid=True)
            except (ValueError, TypeError, KeyError) as error:
                record.update(parse_valid=False, parse_error=str(error))
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            stream.flush()
            print(json.dumps({'event': 'end', 'index': index, 'seconds': record['seconds']}), flush=True)
            del tensor, generated
    del model, base
    torch.cuda.empty_cache()
    after = frozen_snapshot(args.base)
    adapter_after = {p.name: sha(p) for p in args.adapter.iterdir() if p.is_file()}
    if before != after or adapter_before != adapter_after:
        raise ValueError('protected files changed')
    dump(args.output / 'completed.json', {'predictions': 25, 'optimizer_steps': 0, 'protected_unchanged': True, 'adapter_unchanged': True, 'actor_actions_executed': False, 'input_sha256': sha(args.inputs), 'predictions_sha256': sha(args.output / 'predictions.jsonl')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['inputs', 'manifest', 'base', 'adapter', 'output', 'expected-protection', 'expected-adapter']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    run(parser.parse_args())
