"""Approved comparison only: two existing adapters, no optimizer or training."""
import argparse
import json
import os
from pathlib import Path
import time

from assemble_feedback import assemble
from diagnose_fava_quotes import anchored_score
from fava_trial import pack, readl, score, write
from public_helpers import event, loss_for


def authorize(auth, now):
    assert auth['approved'] is True and auth['purpose'] == 'fava_next_development_comparison'
    assert auth['training_updates'] == auth['training_epochs'] == 0
    assert 0 < auth['max_gpu_seconds'] <= 7200
    assert 0 < auth['max_generations'] <= 384
    assert auth['deadline_epoch']-auth['start_epoch'] == auth['max_gpu_seconds']
    assert auth['start_epoch'] <= now < auth['deadline_epoch']


def rows(root):
    fava = readl(root/'fava.development128.jsonl')
    clean = readl(root/'clean.accepted7.jsonl')
    regression = readl(root/'regression32.jsonl')
    assert len(fava) == 128 and len(clean) == 7 and len(regression) == 32
    assert len({r['group'] for r in fava}) == 128
    assert all(r['approved_for_evaluation'] is True and not r['target']['问题'] for r in clean)
    all_rows = [dict(r, task='fava', cohort='original16' if i < 16 else 'additional112') for i, r in enumerate(fava)]
    all_rows += [dict(r, task='fava', cohort='clean7') for r in clean]
    all_rows += [dict(r, task='regression', cohort='regression_natural16' if i < 16 else 'regression_control16') for i, r in enumerate(regression)]
    assert len({r['id'] for r in all_rows}) == len(all_rows) == 167
    return all_rows


def preflight(root, base):
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    packed, lengths = [], []
    for row in rows(root):
        if row['task'] == 'fava':
            item = pack(tokenizer, row)
            limit = 768
            prefix = item['prefix_length']
        else:
            tokens = tokenizer.apply_chat_template(row['messages'], tokenize=True, add_generation_prompt=True,
                                                  enable_thinking=False, return_dict=False)
            item = {**row, 'input_ids': tokens, 'prefix_length': len(tokens)}
            limit, prefix = 1024, len(tokens)
        assert prefix+limit <= 4096, row['id']
        if row['task'] == 'fava':
            assert len(item['input_ids']) <= 4096
        item['generation_limit'] = limit
        packed.append(item)
    with (root/'evaluation.tokens.jsonl').open('x', encoding='utf8') as f:
        for item in packed:
            f.write(json.dumps(item, ensure_ascii=False)+'\n')
    supervised = 0
    for row in readl(root/'train.compact.candidate.jsonl'):
        item = pack(tokenizer, row)
        lengths.append(len(item['input_ids']))
        supervised += len(item['input_ids'])-item['prefix_length']
    report = {'evaluation_rows': len(packed), 'planned_generations': len(packed)*2,
              'evaluation_context_valid': True, 'compact_train_rows': len(lengths),
              'compact_total_tokens': sum(lengths), 'compact_supervised_tokens': supervised,
              'compact_max_tokens': max(lengths), 'compact_over_4096': sum(n > 4096 for n in lengths),
              'model_loaded': False, 'training_started': False}
    write(root/'token_preflight.json', report)
    print(json.dumps(report), flush=True)


def evaluate_rows(model, tokenizer, packed, output, phase, auth, generated_so_far, compact_score_fn=None):
    import torch
    records = []
    model.eval()
    with (output/(phase+'.jsonl')).open('x', encoding='utf8') as stream:
        for row in packed:
            if time.time() > auth['deadline_epoch']-120 or generated_so_far+len(records) >= auth['max_generations']:
                break
            tick = time.monotonic()
            event('row_start', phase=phase, index=len(records)+1, id=row['id'], cohort=row['cohort'])
            with torch.inference_mode():
                nll = float(loss_for(model, row)) if row['task'] == 'fava' else None
                x = torch.tensor([row['input_ids'][:row['prefix_length']]], device='cuda')
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    y = model.generate(input_ids=x, attention_mask=torch.ones_like(x), do_sample=False,
                                       max_new_tokens=row['generation_limit'], use_cache=True,
                                       pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
                raw = tokenizer.decode(y[0, x.shape[1]:], skip_special_tokens=True)
            length = y.shape[1]-x.shape[1]
            record = {'id': row['id'], 'group': row['group'], 'cohort': row['cohort'], 'raw': raw,
                      'loss': nll, 'output_tokens': length, 'hit_token_cap': length == row['generation_limit'],
                      'seconds': time.monotonic()-tick, 'semantic_verified': False}
            if row['task'] == 'fava':
                if compact_score_fn is None:
                    record['strict'] = score(raw, row)
                    record['anchored'], record['anchor_failure'] = anchored_score(raw, row)
                else:
                    record['compact'] = compact_score_fn(raw, row)
            else:
                material = json.loads(row['messages'][1]['content'])
                try:
                    payload = json.loads(raw)
                    checked = assemble(material['待核回答'], material['证据卡'], payload)
                    record.update(source_anchors_valid=checked['source_anchors_verified'],
                                  conclusion=payload['结论'], validation_failure=None)
                except (ValueError, KeyError, TypeError, IndexError) as exc:
                    record.update(source_anchors_valid=False, conclusion=None, validation_failure=str(exc))
            stream.write(json.dumps(record, ensure_ascii=False)+'\n')
            stream.flush()
            records.append(record)
            event('row_end', phase=phase, index=len(records), id=row['id'], seconds=round(record['seconds'], 2))
            del x, y
    write(output/(phase+'.summary.json'), {'rows': len(records), 'complete': len(records) == len(packed)})
    return len(records)


def run(root, base, old, current):
    auth = json.loads((root/'authorization.json').read_text(encoding='utf8'))
    authorize(auth, time.time())
    expected = rows(root)
    packed = readl(root/'evaluation.tokens.jsonl')
    assert [r['id'] for r in packed] == [r['id'] for r in expected]
    assert len(packed)*2 <= auth['max_generations']
    assert all(r['prefix_length']+r['generation_limit'] <= 4096 for r in packed)
    output = root/'run'
    output.mkdir(exist_ok=False)
    import torch
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    from peft import PeftModel, prepare_model_for_kbit_training
    torch.manual_seed(20261018)
    torch.cuda.manual_seed_all(20261018)
    write(output/'config.json', {**auth, 'base': str(base), 'old': str(old), 'current': str(current),
          'gpu': torch.cuda.get_device_name(), 'seed': 20261018, 'thinking': False,
          'decoding': 'greedy', 'fava_generation_limit': 768, 'regression_generation_limit': 1024,
          'evaluation_ids': [r['id'] for r in packed], 'training_started': False})
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                              bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(base, local_files_only=True, dtype=torch.bfloat16,
                quantization_config=quant, device_map={'': 0}, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model.get_input_embeddings().to(dtype=torch.bfloat16)
    model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    model = PeftModel.from_pretrained(model, old, adapter_name='old', is_trainable=False, local_files_only=True)
    count = 0
    for phase, adapter in (('old00952', old), ('current00373', current)):
        if phase == 'current00373':
            if time.time() > auth['deadline_epoch']-120:
                break
            model.load_adapter(adapter, adapter_name='current', is_trainable=False, local_files_only=True)
            model.set_adapter('current')
        # set_adapter can enable adapter gradients; this worker freezes every parameter.
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        assert not any(p.requires_grad for p in model.parameters())
        count += evaluate_rows(model, tokenizer, packed, output, phase, auth, count)
    write(output/'status.json', {'finished_epoch': time.time(), 'generations': count,
          'expected_generations': len(packed)*2, 'complete': count == len(packed)*2,
          'training_started': False, 'training_updates': 0})
    del model
    torch.cuda.empty_cache()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--old', type=Path)
    p.add_argument('--current', type=Path)
    p.add_argument('--run', action='store_true')
    a = p.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    if a.run:
        assert a.old and a.current
        run(a.root, a.base, a.old, a.current)
    else:
        preflight(a.root, a.base)
