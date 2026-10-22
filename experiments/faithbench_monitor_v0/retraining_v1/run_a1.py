"""Bounded inference-only reload/context diagnostic; never imports historical runners."""
import argparse
import contextlib
import json
import os
import random
import time
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def event(name, **fields):
    print(json.dumps({'event': name, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      **fields}, ensure_ascii=False), flush=True)


def validate_bundle(inputs):
    params = read(inputs / 'parameters.json')
    requests = read(inputs / 'requests.json')
    anchors = read(inputs / 'anchors.json') if (inputs / 'anchors.json').exists() else []
    keys = [(row['model'], row['view'], row['id']) for row in anchors + requests]
    batch_shape = (params['new_generations_limit'], len(anchors), len(requests))
    if len(keys) != len(set(keys)) or batch_shape not in ((30, 4, 26), (12, 0, 12)):
        raise ValueError('Unexpected or duplicated diagnostic schedule')
    if params['max_new_tokens'] != 384:
        raise ValueError('Generation budget changed')
    if set(row['model'] for row in anchors + requests) != {'base', 'v3_adapter'}:
        raise ValueError('Unexpected model condition')
    for row in anchors + requests:
        data = json.loads(row['user_text'].split('\n待审核数据：\n', 1)[1])
        if data['audit_target'] not in ('tool_return', 'tool_capability'):
            raise ValueError('Unexpected task')
        if any('field_references' not in item for item in data['prior_source_returns']):
            raise ValueError('Missing actual-return reference mapping')
    return params, anchors, requests


def structural_review(raw, user_text):
    try:
        result = json.loads(raw)
        data = json.loads(user_text.split('\n待审核数据：\n', 1)[1])
        required = {'audit_target', 'status', 'reason', 'return_reference_ids', 'capability_reference_ids'}
        if not isinstance(result, dict) or set(result) != required:
            raise ValueError('Invalid output fields')
        target = data['audit_target']
        states = {'tool_return': {'supported_by_source', 'not_returned_by_source', 'unassessable'},
                  'tool_capability': {'supported_by_card', 'contradicted_by_card', 'unassessable'}}
        if result['audit_target'] != target or result['status'] not in states[target]:
            raise ValueError('Invalid target or status')
        if not isinstance(result['reason'], str) or not result['reason'].strip():
            raise ValueError('Empty reason')
        allowed_returns = {value for item in data['prior_source_returns']
                           for value in item['field_references'].values()}
        allowed_cards = set(data['source_capability_fields'])
        for key, allowed in [('return_reference_ids', allowed_returns), ('capability_reference_ids', allowed_cards)]:
            if not isinstance(result[key], list) or not all(isinstance(value, str) and value in allowed for value in result[key]):
                raise ValueError('Unknown or invalid reference')
        wrong_kind = result['capability_reference_ids'] if target == 'tool_return' else result['return_reference_ids']
        if wrong_kind:
            raise ValueError('Cross-category reference')
        return {'parse_valid': True, 'parsed': result}
    except (ValueError, KeyError, TypeError) as error:
        return {'parse_valid': False, 'parse_error': str(error)}


def run(args):
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    params, anchors, requests = validate_bundle(args.inputs)
    if args.output.exists():
        raise FileExistsError('Refusing to overwrite diagnostic output')
    output = args.output.resolve()
    for source in (args.base.resolve(), args.adapter.resolve(), args.inputs.resolve()):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError('Output overlaps protected source')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    lengths = []
    for row in anchors + requests:
        tokens = tokenizer.apply_chat_template([{'role': 'user', 'content': row['user_text']}],
                                               tokenize=True, add_generation_prompt=True)
        if len(tokens) + params['max_new_tokens'] > 4096:
            raise ValueError('No truncation allowed: ' + row['id'])
        lengths.append({'id': row['id'], 'model': row['model'], 'view': row['view'], 'input_tokens': len(tokens)})
    args.output.mkdir(parents=True)
    write(args.output / 'preflight.json', {'schedule': lengths, 'model_loaded': False, 'training_updates': 0})
    if args.preflight_only:
        event('cpu_preflight_complete', requests=len(lengths), longest=max(r['input_tokens'] for r in lengths))
        return
    import torch
    from transformers import BitsAndBytesConfig, Qwen3VLForConditionalGeneration
    from peft import PeftModel, prepare_model_for_kbit_training
    started = time.monotonic()
    completed = []
    random.seed(params['seed'])
    torch.manual_seed(params['seed'])
    torch.cuda.manual_seed_all(params['seed'])
    write(args.output / 'runtime.json', {'pid': os.getpid(), 'base': str(args.base), 'adapter': str(args.adapter),
        'seed': params['seed'], 'quantization': params['quantization'], 'attention': 'sdpa',
        'max_new_tokens': 384, 'training_updates': 0, 'request_limit': params['new_generations_limit']})
    event('model_load_start', pid=os.getpid())
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    base = Qwen3VLForConditionalGeneration.from_pretrained(args.base, local_files_only=True,
        torch_dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=False)
    model = PeftModel.from_pretrained(base, args.adapter, is_trainable=False, local_files_only=True)
    model.requires_grad_(False)
    model.eval()
    event('model_load_complete', memory_bytes=torch.cuda.memory_allocated())
    reason = None
    try:
        with (args.output / 'predictions.jsonl').open('x', encoding='utf-8') as stream:
            for row in anchors + requests:
                if time.monotonic() - started >= params['hard_wall_minutes'] * 60:
                    reason = 'wall_time_limit'
                    break
                event('generation_start', index=len(completed) + 1, id=row['id'], model=row['model'], view=row['view'])
                ids = tokenizer.apply_chat_template([{'role': 'user', 'content': row['user_text']}],
                                                    tokenize=True, add_generation_prompt=True)
                tensor = torch.tensor([ids], device='cuda')
                call_started = time.monotonic()
                adapter_context = model.disable_adapter() if row['model'] == 'base' else contextlib.nullcontext()
                with adapter_context, torch.inference_mode():
                    generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                        do_sample=False, max_new_tokens=384, pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id, use_cache=True)
                raw = tokenizer.decode(generated[0, len(ids):], skip_special_tokens=True)
                result = {'id': row['id'], 'model': row['model'], 'view': row['view'], 'raw': raw,
                    'seconds': round(time.monotonic() - call_started, 4), 'input_tokens': len(ids),
                    'output_tokens': generated.shape[1] - len(ids), **structural_review(raw, row['user_text'])}
                if row['view'] == 'reload_anchor':
                    result['historical_text_matches'] = raw == row['raw']
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
                stream.flush()
                completed.append(result)
                event('generation_complete', index=len(completed), id=row['id'], model=row['model'],
                      view=row['view'], seconds=result['seconds'], parse_valid=result['parse_valid'])
                del tensor, generated
                if row['view'] == 'reload_anchor' and not result['historical_text_matches']:
                    reason = 'reload_anchor_text_mismatch'
                    break
        write(args.output / 'completed.json', {'pid': os.getpid(), 'outputs': len(completed),
            'planned_maximum': params['new_generations_limit'],
            'finished_schedule': len(completed) == params['new_generations_limit'], 'stop_reason': reason,
            'seconds': time.monotonic() - started, 'training_updates': 0})
    finally:
        del model, base
        torch.cuda.empty_cache()
        event('worker_exit', outputs=len(completed), stop_reason=reason)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('inputs', 'base', 'adapter', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    run(parser.parse_args())
