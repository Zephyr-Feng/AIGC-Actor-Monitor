"""One public-data epoch from the official base; assistant-only QLoRA."""
import argparse
import contextlib
import json
import math
import os
import random
import time
from pathlib import Path


def event(name, **fields):
    print(json.dumps({'event': name, 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **fields}), flush=True)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def read_rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines()]


def supervised_positions(row):
    prefix, length = row['prefix_length'], len(row['input_ids'])
    assert 0 < prefix < length
    return list(range(prefix - 1, length - 1)), row['input_ids'][prefix:]


def loss_for(model, row, reduction='mean'):
    import torch
    positions, target = supervised_positions(row)
    x = torch.tensor([row['input_ids']], device='cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        output = model(input_ids=x, attention_mask=torch.ones_like(x), use_cache=False,
                       logits_to_keep=torch.tensor(positions, device='cuda'))
        # This is exactly the causal loss after masking all prompt labels.
        loss = torch.nn.functional.cross_entropy(output.logits[0].float(),
                    torch.tensor(target, device='cuda'), reduction=reduction)
    return loss


def score(raw, target, response):
    result = {'json_valid': False, 'status_correct': False, 'exact_spans': False,
              'span_offsets_valid': False, 'gold_has_error': bool(target['问题片段'])}
    try:
        prediction = json.loads(raw)
        spans = prediction['问题片段']
        assert isinstance(spans, list)
        valid = all(type(s['起点']) is int and type(s['终点']) is int and
                    0 <= s['起点'] < s['终点'] <= len(response) and
                    response[s['起点']:s['终点']] == s['原文'] for s in spans)
        result.update(json_valid=True, status_correct=prediction['判定'] == target['判定'],
                      exact_spans=spans == target['问题片段'], span_offsets_valid=valid,
                      predicted_error=prediction['判定'] == '存在来源忠实性问题')
    except (ValueError, KeyError, TypeError, AssertionError):
        pass
    return result


def evaluate(model, tokenizer, rows, originals, root, phase, baseline=False):
    import torch
    path = root / f'{phase}.jsonl'
    if path.exists():
        existing = read_rows(path)
        assert [x['id'] for x in existing] == [r['id'] for r in rows[:len(existing)]]
    else:
        existing = []
    model.eval()
    manager = model.disable_adapter() if baseline else contextlib.nullcontext()
    with manager, path.open('a', encoding='utf8') as stream:
        for row in rows[len(existing):]:
            started = time.monotonic()
            event('evaluation_start', phase=phase, index=len(existing)+1, id=row['id'])
            with torch.inference_mode():
                loss = float(loss_for(model, row))
                x = torch.tensor([row['input_ids'][:row['prefix_length']]], device='cuda')
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    generated = model.generate(input_ids=x, attention_mask=torch.ones_like(x),
                        do_sample=False, max_new_tokens=768, use_cache=True,
                        pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
                raw = tokenizer.decode(generated[0, x.shape[1]:], skip_special_tokens=True)
            output_tokens = generated.shape[1]-x.shape[1]
            response = json.loads(originals[row['id']]['messages'][1]['content'])['材料']['待核回答']
            record = {'id': row['id'], 'loss': loss, 'raw': raw, 'output_tokens': output_tokens,
                'hit_token_cap': output_tokens == 768, 'seconds': time.monotonic()-started,
                **score(raw, row['target'], response)}
            stream.write(json.dumps(record, ensure_ascii=False)+'\n'); stream.flush()
            existing.append(record)
            event('evaluation_end', phase=phase, index=len(existing), seconds=round(record['seconds'],2),
                  status_correct=record['status_correct'], json_valid=record['json_valid'])
            del generated, x
    report = {'rows': len(existing), 'mean_sequence_loss': sum(r['loss'] for r in existing)/len(existing),
        **{key: sum(bool(r[key]) for r in existing) for key in
           ('json_valid', 'status_correct', 'exact_spans', 'span_offsets_valid', 'hit_token_cap')}}
    for error in (False, True):
        subset = [r for r in existing if r['gold_has_error'] == error]
        report['error' if error else 'no_error'] = {'rows': len(subset),
            'status_correct': sum(r['status_correct'] for r in subset)}
    write(root/f'{phase}.summary.json', report)
    event('evaluation_complete', phase=phase, **report)


def checkpoint(model, optimizer, root, position, updates, seen_tokens):
    import torch
    destination = root/f'checkpoint-{updates:05d}'
    destination.mkdir()
    model.save_pretrained(destination/'adapter', safe_serialization=True)
    torch.save({'optimizer': optimizer.state_dict(), 'position': position, 'updates': updates,
                'seen_tokens': seen_tokens, 'torch_rng': torch.get_rng_state(),
                'cuda_rng': torch.cuda.get_rng_state_all()}, destination/'training_state.pt')
    write(root/'latest.json', {'checkpoint': destination.name, 'position': position, 'updates': updates})
    event('checkpoint_saved', checkpoint=destination.name, samples=position, updates=updates)
    return destination


def run(args):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    import torch
    import transformers
    import peft
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    root, base = args.root.resolve(), args.base.resolve()
    assert not root.is_relative_to(base) and not base.is_relative_to(root)
    output = root/'run'
    if args.resume:
        assert args.resume.resolve().is_relative_to(output) and (output/'config.json').exists()
    else:
        output.mkdir()
    started = time.monotonic()
    random.seed(20261016); torch.manual_seed(20261016); torch.cuda.manual_seed_all(20261016)
    train = read_rows(root/'train.tokens.jsonl')
    dev_ids = json.loads((root/'development_ids.json').read_text())
    dev_map = {r['id']: r for r in read_rows(root/'validation.tokens.jsonl')}
    dev = [dev_map[i] for i in dev_ids]
    originals = {r['id']: r for r in read_rows(root/'validation.primary.sft.jsonl') if r['id'] in dev_ids}
    assert len(train) == 12141 and len(dev) == 64
    order = list(range(len(train))); random.Random(20261016).shuffle(order)
    total_updates = math.ceil(len(train)/8)
    config = {'base': str(base), 'train_rows': len(train), 'epochs': 1, 'updates': total_updates,
        'microbatch': 1, 'gradient_accumulation': 8, 'learning_rate': 5e-5, 'warmup_ratio': .03,
        'lora_rank': 8, 'lora_alpha': 16, 'lora_dropout': .05, 'seed': 20261016,
        'context_limit': 4096, 'loss': 'assistant_token_cross_entropy', 'enable_thinking': False,
        'development_rows': 64, 'generation_cap': 768, 'hard_wall_hours_per_process': args.hours,
        'transformers': transformers.__version__, 'peft': peft.__version__, 'torch': torch.__version__,
        'test_used': False, 'silver_used': False, 'visual_aux_used': False}
    if not args.resume:
        write(output/'config.json', config)
    event('load_start', pid=os.getpid(), **config)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(base, local_files_only=True,
        dtype=torch.bfloat16, quantization_config=quant, device_map={'':0}, attn_implementation='sdpa')
    event('base_loaded', allocated=torch.cuda.memory_allocated())
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                gradient_checkpointing_kwargs={'use_reentrant': False})
    # Keep the large frozen embedding/head and unused vision tower in their original BF16 precision.
    model.get_input_embeddings().to(dtype=torch.bfloat16)
    model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    targets = r'model\.language_model\.layers\.\d+\.(self_attn\.(q_proj|k_proj|v_proj|o_proj)|linear_attn\.(in_proj_qkv|in_proj_z|in_proj_b|in_proj_a|out_proj)|mlp\.(gate_proj|up_proj|down_proj))'
    if args.resume:
        model = PeftModel.from_pretrained(model, args.resume/'adapter', is_trainable=True, local_files_only=True)
    else:
        model = get_peft_model(model, LoraConfig(task_type='CAUSAL_LM', r=8, lora_alpha=16,
            lora_dropout=.05, target_modules=targets))
    trainable = [(n,p) for n,p in model.named_parameters() if p.requires_grad]
    assert trainable and all('lora_' in n and 'language_model.layers.' in n for n,p in trainable)
    assert len({int(n.split('layers.')[1].split('.')[0]) for n,p in trainable}) == 32
    if not args.resume:
        write(output/'trainable.json', {'total': sum(p.numel() for n,p in trainable),
            'parameters': [{'name':n, 'shape':list(p.shape)} for n,p in trainable]})
    optimizer = torch.optim.AdamW([p for n,p in trainable], lr=5e-5, weight_decay=.01)
    position, updates, seen_tokens = 0, 0, 0
    if args.resume:
        state = torch.load(args.resume/'training_state.pt', map_location='cpu', weights_only=True)
        optimizer.load_state_dict(state['optimizer'])
        position, updates, seen_tokens = state['position'], state['updates'], state['seen_tokens']
        torch.set_rng_state(state['torch_rng']); torch.cuda.set_rng_state_all(state['cuda_rng'])
    event('load_complete', trainable=sum(p.numel() for n,p in trainable), allocated=torch.cuda.memory_allocated())
    if not args.resume:
        # An actual backward pass catches unsupported kernels/OOM before spending time on baseline generation.
        model.train(); model.config.use_cache=False
        loss = loss_for(model, train[order[0]])
        assert torch.isfinite(loss)
        loss.backward()
        assert all(p.grad is None for n,p in model.named_parameters() if not p.requires_grad)
        assert any(p.grad is not None and bool(torch.any(p.grad != 0)) for n,p in trainable)
        optimizer.zero_grad(set_to_none=True); del loss
        event('backward_preflight_complete', peak_allocated=torch.cuda.max_memory_allocated())
    evaluate(model, tokenizer, dev, originals, output, 'before', baseline=True)
    model.train(); model.config.use_cache=False
    last_save, last_checkpoint = time.monotonic(), args.resume
    with (output/'training.jsonl').open('a', encoding='utf8') as stream:
        while position < len(order):
            if time.monotonic()-started >= args.hours*3600:
                event('wall_limit', samples=position, updates=updates)
                break
            window = [train[i] for i in order[position:position+8]]
            target_tokens = sum(len(r['input_ids'])-r['prefix_length'] for r in window)
            warmup = math.ceil(total_updates*.03)
            scale = min(1., (updates+1)/warmup) if updates < warmup else .1+.9*.5*(1+math.cos(math.pi*(updates-warmup)/(total_updates-warmup)))
            for group in optimizer.param_groups:
                group['lr'] = 5e-5*scale
            optimizer.zero_grad(set_to_none=True)
            step_started, loss_sum = time.monotonic(), 0.
            for row in window:
                event('micro_start', update=updates+1, sample=position+1, id=row['id'], tokens=len(row['input_ids']))
                loss = loss_for(model, row, reduction='sum')/target_tokens
                assert torch.isfinite(loss), 'nonfinite loss'
                loss.backward(); loss_sum += float(loss.detach()); del loss
                position += 1; seen_tokens += len(row['input_ids'])
            gradient = torch.nn.utils.clip_grad_norm_([p for n,p in trainable], 1.)
            assert torch.isfinite(gradient), 'nonfinite gradient'
            optimizer.step(); updates += 1
            record = {'update':updates, 'samples':position, 'loss':loss_sum, 'grad_norm':float(gradient),
                'lr':optimizer.param_groups[0]['lr'], 'seconds':time.monotonic()-step_started,
                'seen_tokens':seen_tokens, 'peak_allocated':torch.cuda.max_memory_allocated()}
            stream.write(json.dumps(record)+'\n'); stream.flush(); event('update_complete', **record)
            if updates % 100 == 0 or time.monotonic()-last_save >= 1800:
                last_checkpoint = checkpoint(model, optimizer, output, position, updates, seen_tokens)
                last_save = time.monotonic()
    if last_checkpoint is None or json.loads((output/'latest.json').read_text())['position'] != position:
        last_checkpoint = checkpoint(model, optimizer, output, position, updates, seen_tokens)
    if position == len(order):
        evaluate(model, tokenizer, dev, originals, output, 'after')
    write(output/'status.json', {'epoch_complete':position == len(order), 'samples':position,
        'updates':updates, 'seconds':time.monotonic()-started, 'checkpoint':str(last_checkpoint)})
    del model, optimizer; torch.cuda.empty_cache()
    event('worker_exit', epoch_complete=position == len(order), samples=position, updates=updates)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--hours', type=float, default=6.)
    parser.add_argument('--resume', type=Path)
    run(parser.parse_args())
