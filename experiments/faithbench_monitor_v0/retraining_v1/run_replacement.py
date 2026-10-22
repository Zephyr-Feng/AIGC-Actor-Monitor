"""Nineteen frozen requests for the single approved replacement base; inference only."""
import argparse
import json
import os
import random
import time
from pathlib import Path

from run_a1 import event, read, structural_review, write


def validate(rows):
    keys = [(row['view'], row['id']) for row in rows]
    assert len(rows) == len(set(keys)) == 19
    assert sum(row['view'] == 'original_full_audit_packet' for row in rows) == 13
    assert sum(row['view'] == 'selected_minimal_evidence' for row in rows) == 6
    assert all(row['model'] == 'qwen35_9b' for row in rows)
    assert all(set(row) == {'id', 'model', 'view', 'user_text'} for row in rows)


def run(args):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    rows = read(args.inputs)
    validate(rows)
    assert not args.output.exists(), 'Never overwrite results'
    output, base = args.output.resolve(), args.base.resolve()
    assert not output.is_relative_to(base) and not base.is_relative_to(output)
    from transformers import AutoConfig, AutoTokenizer
    config = AutoConfig.from_pretrained(base, local_files_only=True)
    assert config.model_type == 'qwen3_5'
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    schedule = []
    for row in rows:
        ids = tokenizer.apply_chat_template([{'role': 'user', 'content': row['user_text']}],
            tokenize=True, add_generation_prompt=True, enable_thinking=False, return_dict=False)
        assert isinstance(ids, list) and ids and all(isinstance(value, int) for value in ids)
        assert len(ids) + 384 <= 4096, 'No truncation allowed'
        schedule.append({'id': row['id'], 'view': row['view'], 'input_tokens': len(ids)})
    args.output.mkdir(parents=True)
    write(args.output / 'preflight.json', {'schedule': schedule, 'model_loaded': False,
        'enable_thinking': False, 'training_updates': 0})
    if args.preflight_only:
        event('cpu_preflight_complete', requests=19, longest=max(r['input_tokens'] for r in schedule))
        return
    import torch
    import transformers
    from transformers import BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    started = time.monotonic()
    random.seed(42)
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    write(args.output / 'runtime.json', {'pid': os.getpid(), 'base': str(base),
        'transformers': transformers.__version__, 'torch': torch.__version__,
        'seed': 42, 'quantization': 'NF4_double_bf16', 'attention': 'sdpa',
        'max_new_tokens': 384, 'enable_thinking': False, 'training_updates': 0,
        'request_limit': 19, 'hard_wall_minutes': 15})
    event('model_load_start', pid=os.getpid())
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(base, local_files_only=True,
        dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    model.requires_grad_(False)
    model.eval()
    event('model_load_complete', memory_bytes=torch.cuda.memory_allocated())
    completed = 0
    stop_reason = None
    try:
        with (args.output / 'predictions.jsonl').open('x', encoding='utf-8') as stream:
            for row in rows:
                if time.monotonic() - started >= 15 * 60:
                    stop_reason = 'wall_time_limit'
                    break
                event('generation_start', index=completed + 1, id=row['id'], view=row['view'])
                ids = tokenizer.apply_chat_template([{'role': 'user', 'content': row['user_text']}],
                    tokenize=True, add_generation_prompt=True, enable_thinking=False, return_dict=False)
                tensor = torch.tensor([ids], device='cuda')
                call_started = time.monotonic()
                with torch.inference_mode():
                    generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                        do_sample=False, max_new_tokens=384, pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id, use_cache=True)
                raw = tokenizer.decode(generated[0, len(ids):], skip_special_tokens=True)
                result = {'id': row['id'], 'model': row['model'], 'view': row['view'], 'raw': raw,
                    'seconds': round(time.monotonic() - call_started, 4), 'input_tokens': len(ids),
                    'output_tokens': generated.shape[1] - len(ids), **structural_review(raw, row['user_text'])}
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
                stream.flush()
                completed += 1
                event('generation_complete', index=completed, id=row['id'], view=row['view'],
                    seconds=result['seconds'], parse_valid=result['parse_valid'])
                del tensor, generated
        write(args.output / 'completed.json', {'pid': os.getpid(), 'outputs': completed,
            'planned_maximum': 19, 'finished_schedule': completed == 19, 'stop_reason': stop_reason,
            'seconds': time.monotonic() - started, 'training_updates': 0})
    finally:
        del model
        torch.cuda.empty_cache()
        event('worker_exit', outputs=completed, stop_reason=stop_reason)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('inputs', 'base', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    run(parser.parse_args())
