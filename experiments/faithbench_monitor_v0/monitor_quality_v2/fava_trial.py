"""Bounded Monitor continuation on existing FAVA edit annotations."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import shutil
import time
from public_helpers import event, loss_for, checkpoint


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def readl(path):
    with path.open(encoding='utf8') as f:
        return [json.loads(line) for line in f]


def resume_cursor(state, rows, order):
    position, updates, seen = state['position'], state['updates'], state['seen_tokens']
    assert 0 <= updates <= 500 and position == min(updates*16, len(rows))
    prefix = [rows[i] for i in order[:position]]
    assert seen == sum(len(r['input_ids']) for r in prefix)
    return position, updates, seen, sum(len(r['input_ids'])-r['prefix_length'] for r in prefix)


def train(root, base, initial, resume=None, baseline_root=None):
    import torch
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    from peft import PeftModel, prepare_model_for_kbit_training
    auth = json.loads((root/'authorization.json').read_text())
    assert auth['approved'] and auth['max_updates'] == 500 and auth['epochs'] == 1
    assert auth['max_gpu_seconds'] in (7200, 28800)
    assert auth['deadline_epoch']-auth['start_epoch'] == auth['max_gpu_seconds']
    deadline, cutoff = auth['deadline_epoch'], auth['training_cutoff_epoch']
    assert time.time() < cutoff < deadline
    output = root/'run'
    output.mkdir(exist_ok=False)
    train_rows = readl(root/'train.tokens.jsonl')
    dev = readl(root/'development_pool.tokens.jsonl')
    assert len(dev) == 16 and not {r['group'] for r in train_rows} & {r['group'] for r in dev}
    random.seed(20261018)
    torch.manual_seed(20261018)
    torch.cuda.manual_seed_all(20261018)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    config = {**auth, 'initial_adapter': str(initial), 'base': str(base), 'learning_rate': 1e-5,
              'microbatch': 1, 'gradient_accumulation': 16, 'new_optimizer': resume is None,
              'seed': 20261018, 'context_limit': 4096, 'output_limit': 768,
              'loss': 'assistant-token CE, window normalized by target-token count',
              'task': 'edit spans only; no generated evidence/reason/protection labels'}
    write(output/'config.json', config)
    event('model_load_start', pid=os.getpid())
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(base, local_files_only=True, dtype=torch.bfloat16,
                quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False})
    model.get_input_embeddings().to(dtype=torch.bfloat16)
    model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    model = PeftModel.from_pretrained(model, initial, is_trainable=True, local_files_only=True)
    parameters = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    assert parameters and all('lora_' in n and 'language_model.layers.' in n for n, p in parameters)
    assert len({int(n.split('layers.')[1].split('.')[0]) for n, p in parameters}) == 32
    write(output/'trainable.json', {'total': sum(p.numel() for n, p in parameters), 'parameters': [{'name': n, 'shape': list(p.shape)} for n, p in parameters]})
    optimizer = torch.optim.AdamW([p for n, p in parameters], lr=1e-5, weight_decay=.01)
    model.train()
    model.config.use_cache = False
    longest = max(train_rows, key=lambda r: len(r['input_ids']))
    event('backward_preflight_start', id=longest['id'], tokens=len(longest['input_ids']))
    loss = loss_for(model, longest)
    assert bool(torch.isfinite(loss))
    loss.backward()
    assert any(p.grad is not None and bool(torch.any(p.grad != 0)) for n, p in parameters)
    assert all(p.grad is None or bool(torch.all(torch.isfinite(p.grad))) for n, p in parameters)
    optimizer.zero_grad(set_to_none=True)
    del loss
    event('backward_preflight_complete', peak_allocated=torch.cuda.max_memory_allocated())
    if resume is None:
        before = evaluate(model, tokenizer, dev, output, 'before', min(cutoff, auth['start_epoch']+1800))
    else:
        assert baseline_root is not None
        before = json.loads((baseline_root/'run/before.summary.json').read_text())
        assert [r['id'] for r in dev] == [r['id'] for r in readl(baseline_root/'development_pool.tokens.jsonl')]
        write(output/'baseline_reference.json', {'root': str(baseline_root), 'summary': before})
    assert before['complete'], 'baseline incomplete; no training updates permitted'
    order = list(range(len(train_rows)))
    random.Random(20261018).shuffle(order)
    write(output/'sample_order.json', [train_rows[i]['id'] for i in order])
    model.train()
    model.config.use_cache = False
    position = updates = seen_tokens = supervised_seen = 0
    if resume is not None:
        assert [train_rows[i]['id'] for i in order] == json.loads((baseline_root/'run/sample_order.json').read_text())
        state = torch.load(resume/'training_state.pt', map_location='cpu', weights_only=True)
        position, updates, seen_tokens, supervised_seen = resume_cursor(state, train_rows, order)
        optimizer.load_state_dict(state['optimizer'])
        torch.set_rng_state(state['torch_rng'])
        torch.cuda.set_rng_state_all(state['cuda_rng'])
        event('resume_position', position=position, updates=updates, supervised_tokens_seen=supervised_seen)
        write(output/'resume.json', {'checkpoint': str(resume), 'position': position, 'updates': updates,
              'optimizer_restored': True, 'rng_restored': True, 'original_epoch_order_preserved': True})
        del state
    last_save, latest = time.monotonic(), None
    planned = min(500, math.ceil(len(order)/16))
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
        while position < len(order) and updates < 500 and time.time() < cutoff-90:
            window = [train_rows[i] for i in order[position:position+16]]
            total = sum(len(r['input_ids'])-r['prefix_length'] for r in window)
            lr = 1e-5 * min(1., (updates+1)/15)
            for group in optimizer.param_groups:
                group['lr'] = lr
            optimizer.zero_grad(set_to_none=True)
            started, loss_sum = time.monotonic(), 0.
            for row in window:
                loss = loss_for(model, row, reduction='sum')/total
                assert bool(torch.isfinite(loss))
                loss.backward()
                loss_sum += float(loss.detach())
                position += 1
                seen_tokens += len(row['input_ids'])
                del loss
            norm = torch.nn.utils.clip_grad_norm_([p for n, p in parameters], 1.)
            assert bool(torch.isfinite(norm))
            optimizer.step()
            updates += 1
            supervised_seen += total
            record = {'update': updates, 'samples': position, 'loss': loss_sum, 'lr': lr,
                      'grad_norm': float(norm), 'target_tokens': total, 'supervised_tokens_seen': supervised_seen,
                      'ids': [r['id'] for r in window], 'seconds': time.monotonic()-started}
            stream.write(json.dumps(record)+'\n')
            stream.flush()
            event('update_complete', **record)
            if time.monotonic()-last_save >= 600:
                save()
    if latest is None or json.loads((output/'latest.json').read_text())['updates'] != updates:
        save()
    event('training_stopped', updates=updates, samples=position)
    after = evaluate(model, tokenizer, dev, output, 'after', deadline)
    write(output/'status.json', {'updates': updates, 'samples': position, 'supervised_tokens_seen': supervised_seen, 'available_rows': len(train_rows),
          'epoch_complete': position == len(order), 'planned_max_updates': planned, 'checkpoint': str(latest),
          'before_complete': before['complete'], 'after_complete': after['complete'],
          'finished_epoch': time.time(), 'deadline_epoch': deadline})
    del model, optimizer
    torch.cuda.empty_cache()
    event('worker_exit', updates=updates, after_complete=after['complete'])


def pack(tokenizer, row):
    options = dict(tokenize=True, enable_thinking=False, return_dict=False)
    prefix = tokenizer.apply_chat_template(row['messages'][:-1], add_generation_prompt=True, **options)
    full = tokenizer.apply_chat_template(row['messages'], add_generation_prompt=False, **options)
    assert full[:len(prefix)] == prefix and len(full) > len(prefix)
    return {**row, 'input_ids': full, 'prefix_length': len(prefix)}


def preflight(root, base):
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    counts, groups, selected = {}, {}, {}
    rejected = []
    for split in ('train', 'development_pool'):
        accepted = []
        originals = readl(root/f'{split}.sft.jsonl')
        groups[split] = {r['group'] for r in originals}
        for row in originals:
            item = pack(tokenizer, row)
            reason = ('context_over_4096' if len(item['input_ids']) > 4096 else
                      'generation_length_ineligible' if split != 'train' and
                      (item['prefix_length']+768 > 4096 or len(item['input_ids'])-item['prefix_length'] > 768) else None)
            if reason:
                rejected.append({'id': row['id'], 'split': split, 'reason': reason, 'tokens': len(item['input_ids'])})
            else:
                accepted.append(item)
        counts[split] = len(accepted)
        if split != 'train':
            random.Random(20261018).shuffle(accepted)
            accepted = accepted[:16]
            assert len(accepted) == 16
        selected[split] = accepted
        with (root/f'{split}.tokens.jsonl').open('x', encoding='utf8') as f:
            for row in accepted:
                f.write(json.dumps(row, ensure_ascii=False)+'\n')
        event('tokenized', split=split, accepted=counts[split], selected=len(accepted))
    assert not groups['train'] & groups['development_pool']
    train = selected['train']
    lengths = sorted(len(r['input_ids']) for r in train)
    report = {'train_rows': len(train), 'development_pool_eligible': counts['development_pool'],
              'evaluation_ids': [r['id'] for r in selected['development_pool']], 'evaluation_rows': 16,
              'train_total_tokens': sum(lengths),
              'train_supervised_tokens': sum(len(r['input_ids'])-r['prefix_length'] for r in train),
              'total_token_length': {'min': lengths[0], 'p50': lengths[len(lengths)//2], 'max': lengths[-1]},
              'excluded_for_length': rejected, 'truncated': False, 'groups_disjoint': True,
              'context_limit': 4096, 'generation_limit': 768, 'model_loaded': False, 'training_started': False}
    write(root/'token_preflight.json', report)
    return report


def score(raw, row):
    answer = json.loads(row['messages'][1]['content'])['待核回答']
    gold = row['target']['问题']
    result = {'json_valid': False, 'edits_valid': False, 'exact_author_edits': False,
              'exact_author_corrected_answer': False, 'matched_edits': 0, 'predicted_edits': 0,
              'author_edits': len(gold), 'edits_outside_author_spans': 0}
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {'问题'} or not isinstance(payload['问题'], list):
            return result
        result['json_valid'] = True
        edits = payload['问题']
        result['predicted_edits'] = len(edits)
        keys = {'起点', '终点', '回答原文', '建议'}
        for i in edits:
            if not isinstance(i, dict) or set(i) != keys or type(i['起点']) is not int or type(i['终点']) is not int:
                return result
            if not isinstance(i['回答原文'], str) or not isinstance(i['建议'], str):
                return result
            if not 0 <= i['起点'] <= i['终点'] <= len(answer) or answer[i['起点']:i['终点']] != i['回答原文']:
                return result
        edits = sorted(edits, key=lambda i: (i['起点'], i['终点']))
        if any(a['终点'] > b['起点'] for a, b in zip(edits, edits[1:])) or any(a == b for a, b in zip(edits, edits[1:])):
            return result
        result['edits_valid'] = True
        result['matched_edits'] = sum(i in gold for i in edits)
        result['exact_author_edits'] = len(edits) == len(gold) and all(i in gold for i in edits)
        result['edits_outside_author_spans'] = sum(not any(g['起点'] <= i['起点'] <= i['终点'] <= g['终点'] for g in gold) for i in edits)
        edited = answer
        for i in reversed(edits):
            edited = edited[:i['起点']] + i['建议'] + edited[i['终点']:]
        result['exact_author_corrected_answer'] = edited == row['author_corrected_answer']
    except (ValueError, KeyError, TypeError):
        pass
    return result


def evaluate(model, tokenizer, dev, output, phase, deadline):
    import torch
    model.eval()
    records = []
    with (output/f'{phase}.jsonl').open('x', encoding='utf8') as stream:
        for row in dev:
            if time.time() > deadline-120:
                break
            started = time.monotonic()
            with torch.inference_mode():
                nll = float(loss_for(model, row))
                x = torch.tensor([row['input_ids'][:row['prefix_length']]], device='cuda')
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    generated = model.generate(input_ids=x, attention_mask=torch.ones_like(x), do_sample=False,
                                               max_new_tokens=768, use_cache=True,
                                               pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
                raw = tokenizer.decode(generated[0, x.shape[1]:], skip_special_tokens=True)
            record = {'id': row['id'], 'group': row['group'], 'raw': raw, 'loss': nll,
                      'output_tokens': generated.shape[1]-x.shape[1], 'seconds': time.monotonic()-started, **score(raw, row)}
            stream.write(json.dumps(record, ensure_ascii=False)+'\n')
            stream.flush()
            records.append(record)
            event('evaluation_row', phase=phase, index=len(records), id=row['id'], seconds=round(record['seconds'], 2), valid=record['edits_valid'])
            del x, generated
    report = {'rows': len(records), 'complete': len(records) == len(dev),
              'mean_sequence_loss': sum(r['loss'] for r in records)/len(records) if records else None}
    for key in ('json_valid', 'edits_valid', 'exact_author_edits', 'exact_author_corrected_answer', 'matched_edits', 'predicted_edits', 'author_edits', 'edits_outside_author_spans'):
        report[key] = sum(r[key] for r in records)
    report['author_edit_precision'] = report['matched_edits']/max(1, report['predicted_edits'])
    report['author_edit_recall'] = report['matched_edits']/max(1, report['author_edits'])
    write(output/f'{phase}.summary.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['preflight', 'train'], required=True)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--initial', type=Path)
    p.add_argument('--resume', type=Path)
    p.add_argument('--baseline-root', type=Path)
    a = p.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    try:
        if a.mode == 'preflight':
            result = preflight(a.root, a.base)
            print(json.dumps({k: v for k, v in result.items() if k != 'excluded_for_length'}, ensure_ascii=False))
        else:
            assert a.initial is not None
            train(a.root, a.base, a.initial, a.resume, a.baseline_root)
    except Exception as exc:
        write(a.root/f'{a.mode}_failure.json', {'error': repr(exc), 'time_epoch': time.time()})
        raise
