"""One bounded mixed-supervision epoch; existing adapters and train allocations only."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import random
import shutil
import time

from diagnose_fava_quotes import compact_score
from evaluate_fava_next import evaluate_rows
from fava_trial import pack, readl, write
from prepare_fava_next import write_rows
from public_helpers import checkpoint, event, loss_for


def authorization(auth, now):
    assert auth['approved'] is True and auth['purpose'] == 'mixed_compact_noerror_chinese_replay'
    assert auth['epochs'] == 1 and auth['max_updates'] == 500
    assert auth['max_gpu_seconds'] == 28800 and auth['max_generations'] == 334
    assert auth['deadline_epoch']-auth['start_epoch'] == 28800
    assert auth['training_cutoff_epoch'] == auth['deadline_epoch']-3600
    assert auth['start_epoch'] <= now < auth['training_cutoff_epoch']


def preflight(root, base):
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    train, exclusions, task_tokens = [], [], Counter()
    for filename in ('positive.sft.jsonl', 'replay1024.sft.jsonl'):
        for row in readl(root/filename):
            item = pack(tokenizer, row)
            assert len(item['input_ids']) <= 4096, row['id']
            train.append(item)
    negatives = []
    held = {r['id'] for r in readl(root/'negative.hold.jsonl')}
    for row in readl(root/'negative.candidates1024.jsonl'):
        if row['id'] in held:
            exclusions.append({'id': row['id'], 'reason': 'assistant_spotcheck_author_label_disagreement'})
            continue
        item = pack(tokenizer, row)
        if len(item['input_ids']) > 4096:
            exclusions.append({'id': row['id'], 'tokens': len(item['input_ids']), 'reason': 'context_over_4096_no_truncation'})
            continue
        negatives.append(item)
        if len(negatives) == 512:
            break
    assert len(negatives) == len({r['group'] for r in negatives}) == 512
    train += negatives
    assert len({r['id'] for r in train}) == len(train) <= 8000
    evaluation = []
    for row in readl(root/'evaluation.sft.jsonl'):
        if row['task'] == 'compact_eval':
            item = pack(tokenizer, row)
            item['task'], item['generation_limit'] = 'fava', 768
        else:
            prefix = tokenizer.apply_chat_template(row['messages'], tokenize=True, add_generation_prompt=True,
                                                   enable_thinking=False, return_dict=False)
            item = {**row, 'input_ids': prefix, 'prefix_length': len(prefix), 'generation_limit': 1024}
        assert item['prefix_length']+item['generation_limit'] <= 4096
        evaluation.append(item)
    assert len(evaluation) == 167
    assert not {r['group'] for r in train} & {r['group'] for r in evaluation}
    write_rows(root/'train.tokens.jsonl', train)
    write_rows(root/'evaluation.tokens.jsonl', evaluation)
    write_rows(root/'negative.selected512.sft.jsonl', [{k: v for k, v in r.items() if k not in ('input_ids', 'prefix_length')} for r in negatives])
    counts = Counter(r['task'] for r in train)
    for r in train:
        task_tokens[r['task']] += len(r['input_ids'])-r['prefix_length']
    report = {'rows': len(train), 'planned_updates': math.ceil(len(train)/16), 'tasks': dict(counts),
              'task_supervised_tokens': dict(task_tokens), 'total_tokens': sum(len(r['input_ids']) for r in train),
              'supervised_tokens': sum(task_tokens.values()), 'max_length': max(len(r['input_ids']) for r in train),
              'source_groups': len({r['group'] for r in train}), 'negative_exclusions': exclusions,
              'evaluation_rows': 167, 'planned_generations': 334, 'truncated': False,
              'groups_disjoint': True, 'model_loaded': False, 'training_started': False,
              'loss': 'mean assistant-token CE per example, then mean across accumulation window'}
    write(root/'token_preflight.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


def run(root, base, initial, comparison):
    auth = json.loads((root/'authorization.json').read_text(encoding='utf8'))
    authorization(auth, time.time())
    train = readl(root/'train.tokens.jsonl')
    dev = readl(root/'evaluation.tokens.jsonl')
    assert len(dev) == 167 and len({r['id'] for r in train}) == len(train) <= 8000
    assert not {r['group'] for r in train} & {r['group'] for r in dev}
    planned = math.ceil(len(train)/16)
    assert planned <= 500
    output = root/'run'
    output.mkdir(exist_ok=False)
    import torch
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    from peft import PeftModel, prepare_model_for_kbit_training
    seed = 20261019
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    write(output/'config.json', {**auth, 'base': str(base), 'initial_adapter': str(initial),
          'comparison_adapter': str(comparison), 'rows': len(train), 'planned_updates': planned,
          'gpu': torch.cuda.get_device_name(), 'seed': seed, 'learning_rate': 1e-5, 'microbatch': 1,
          'gradient_accumulation': 16, 'lora_rank': 8, 'lora_alpha': 16, 'lora_dropout': .05,
          'context_limit': 4096, 'loss': 'equal example weights; assistant-token mean per example',
          'new_optimizer': True, 'joint_intervention_not_single_factor': True})
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True,
                              bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(base, local_files_only=True, dtype=torch.bfloat16,
              quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                          gradient_checkpointing_kwargs={'use_reentrant': False})
    model.get_input_embeddings().to(dtype=torch.bfloat16)
    model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    model = PeftModel.from_pretrained(model, initial, is_trainable=True, local_files_only=True)
    parameters = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    assert parameters and all('lora_' in n and '.default.' in n and 'language_model.layers.' in n for n, p in parameters)
    assert len({int(n.split('layers.')[1].split('.')[0]) for n, p in parameters}) == 32
    write(output/'trainable.json', {'total': sum(p.numel() for n, p in parameters),
                                   'parameters': [{'name': n, 'shape': list(p.shape)} for n, p in parameters]})
    optimizer = torch.optim.AdamW([p for n, p in parameters], lr=1e-5, weight_decay=.01)
    model.train()
    model.config.use_cache = False
    longest = max(train, key=lambda r: len(r['input_ids']))
    event('backward_preflight_start', id=longest['id'], tokens=len(longest['input_ids']))
    loss = loss_for(model, longest)
    assert bool(torch.isfinite(loss))
    loss.backward()
    assert any(p.grad is not None and bool(torch.any(p.grad != 0)) for n, p in parameters)
    assert all(p.grad is None or bool(torch.all(torch.isfinite(p.grad))) for n, p in parameters)
    optimizer.zero_grad(set_to_none=True)
    del loss
    event('backward_preflight_complete', peak_allocated=torch.cuda.max_memory_allocated())
    model.load_adapter(comparison, adapter_name='comparison', is_trainable=False, local_files_only=True)
    model.set_adapter('comparison')
    for p in model.parameters():
        p.requires_grad_(False)
    before_auth = {**auth, 'deadline_epoch': min(auth['training_cutoff_epoch'], auth['start_epoch']+2700)}
    before_count = evaluate_rows(model, tokenizer, dev, output, 'before00373', before_auth, 0, compact_score)
    assert before_count == len(dev), 'incomplete baseline; no training permitted'
    model.set_adapter('default')
    model.delete_adapter('comparison')
    assert all(p.requires_grad for n, p in parameters)
    model.train()
    model.config.use_cache = False
    order = list(range(len(train)))
    random.Random(seed).shuffle(order)
    write(output/'sample_order.json', [train[i]['id'] for i in order])
    position = updates = seen_tokens = supervised = 0
    task_seen = Counter()
    latest, last_save = None, time.monotonic()
    owned = []

    def save():
        nonlocal latest, last_save
        latest = checkpoint(model, optimizer, output, position, updates, seen_tokens)
        owned.append(latest)
        while len(owned) > 2:
            old = owned.pop(0)
            assert old.resolve().is_relative_to(output.resolve()) and not old.is_symlink() and old.name.startswith('checkpoint-')
            shutil.rmtree(old)
        last_save = time.monotonic()

    with (output/'training.jsonl').open('x', encoding='utf8') as stream:
        while position < len(order) and updates < 500 and time.time() < auth['training_cutoff_epoch']-180:
            window = [train[i] for i in order[position:position+16]]
            optimizer.zero_grad(set_to_none=True)
            for group in optimizer.param_groups:
                group['lr'] = 1e-5*min(1., (updates+1)/15)
            tick, loss_sum = time.monotonic(), 0.
            event('update_start', update=updates+1, position=position)
            for row in window:
                loss = loss_for(model, row)/len(window)
                assert bool(torch.isfinite(loss))
                loss.backward()
                loss_sum += float(loss.detach())
                del loss
                position += 1
                seen_tokens += len(row['input_ids'])
                supervised += len(row['input_ids'])-row['prefix_length']
                task_seen[row['task']] += 1
            norm = torch.nn.utils.clip_grad_norm_([p for n, p in parameters], 1.)
            assert bool(torch.isfinite(norm))
            optimizer.step()
            updates += 1
            record = {'update': updates, 'samples': position, 'loss': loss_sum, 'grad_norm': float(norm),
                      'lr': optimizer.param_groups[0]['lr'], 'ids': [r['id'] for r in window],
                      'seconds': time.monotonic()-tick, 'seen_tokens': seen_tokens,
                      'supervised_tokens_seen': supervised, 'task_seen': dict(task_seen)}
            stream.write(json.dumps(record)+'\n')
            stream.flush()
            event('update_complete', **record)
            if updates % 50 == 0 or time.monotonic()-last_save >= 600:
                save()
        if latest is None or json.loads((output/'latest.json').read_text())['position'] != position:
            save()
    event('training_stopped', samples=position, updates=updates, epoch_complete=position == len(train))
    after_count = evaluate_rows(model, tokenizer, dev, output, 'after_mixed', auth, before_count, compact_score)
    write(output/'status.json', {'epoch_complete': position == len(train), 'samples': position, 'available_rows': len(train),
          'updates': updates, 'checkpoint': str(latest), 'task_seen': dict(task_seen), 'seen_tokens': seen_tokens,
          'supervised_tokens_seen': supervised, 'before_count': before_count, 'after_count': after_count,
          'generations': before_count+after_count, 'finished_epoch': time.time(), 'deadline_epoch': auth['deadline_epoch']})
    del model, optimizer
    torch.cuda.empty_cache()
    event('worker_exit', updates=updates, after_complete=after_count == len(dev))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--initial', type=Path)
    p.add_argument('--comparison', type=Path)
    p.add_argument('--run', action='store_true')
    a = p.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    try:
        if a.run:
            assert a.initial and a.comparison
            run(a.root, a.base, a.initial, a.comparison)
        else:
            preflight(a.root, a.base)
    except Exception as exc:
        write(a.root/'failure.json', {'error': repr(exc), 'epoch': time.time()})
        raise
