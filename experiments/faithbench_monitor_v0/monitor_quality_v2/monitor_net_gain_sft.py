"""One bounded full-answer Monitor update; reuse existing QLoRA loss and saver."""
import argparse
import json
import os
from pathlib import Path
import random
import time

from actor_feedback_bridge import ADAPTER, MONITOR_BASE, event, read
from assemble_feedback import assemble
from prepare_feedback_control_run import write
from public_helpers import checkpoint, loss_for
from train_feedback import pack


def preflight(root):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MONITOR_BASE, local_files_only=True)
    rows = read(root/'train.json')
    assert len(rows) == 344 and len({r['id'] for r in rows}) == 344
    assert not {r['group'] for r in rows} & {r['source_id'] for r in read(root/'evaluation.json')}
    tokens = []
    for row in rows:
        material = json.loads(row['messages'][1]['content'])
        assemble(material['待核回答'], material['证据卡'], row['target'])
        encoded = pack(tokenizer, row)
        tokens.append(encoded)
    full = [r for r, source in zip(tokens, rows) if source['task'] != 'forensic_short_retention']
    report = dict(rows=344, full_answer_rows=len(full), max_length=max(len(r['input_ids']) for r in tokens),
                  supervised_tokens=sum(len(r['input_ids'])-r['prefix_length'] for r in tokens),
                  full_answer_supervised_tokens=sum(len(r['input_ids'])-r['prefix_length'] for r in full),
                  targets_over_evaluation_cap=sum(len(r['input_ids'])-r['prefix_length'] > 768 for r in tokens),
                  max_target=max(len(r['input_ids'])-r['prefix_length'] for r in tokens), truncated=False)
    write(root/'train.tokens.json', tokens)
    write(root/'preflight.json', report)
    event('full_answer_preflight', **report)


def run(root):
    import torch
    from transformers import BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    from peft import PeftModel, prepare_model_for_kbit_training
    auth = read(root/'authorization.json')
    assert auth['approved'] and auth['epochs'] == 1 and auth['planned_updates'] == 43
    assert auth['accumulation'] == 8 and auth['learning_rate'] == 1e-5
    assert auth['actor_training_updates'] == auth['teacher_api_calls'] == auth['new_tool_calls'] == 0
    assert auth['initial_adapter'] == ADAPTER.as_posix()
    rows = read(root/'train.tokens.json'); assert len(rows) == 344
    assert read(root/'preflight.json')['rows'] == 344
    output = root/'run'; output.mkdir()
    torch.set_num_threads(2)
    random.seed(20261021); torch.manual_seed(20261021); torch.cuda.manual_seed_all(20261021)
    started = time.monotonic(); cutoff = started + auth['max_gpu_seconds'] - 300
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                              bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    event('full_answer_load', pid=os.getpid())
    model = Qwen3_5ForConditionalGeneration.from_pretrained(MONITOR_BASE, local_files_only=True,
            dtype=torch.bfloat16, quantization_config=quant, device_map={'':0}, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                          gradient_checkpointing_kwargs={'use_reentrant':False})
    model.get_input_embeddings().to(dtype=torch.bfloat16)
    model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    model = PeftModel.from_pretrained(model, ADAPTER, is_trainable=True, local_files_only=True)
    parameters = [(n,p) for n,p in model.named_parameters() if p.requires_grad]
    assert parameters and all('lora_' in n and 'language_model.layers.' in n for n,p in parameters)
    write(output/'trainable.json', dict(names=[n for n,p in parameters], count=sum(p.numel() for n,p in parameters)))
    optimizer = torch.optim.AdamW([p for n,p in parameters], lr=1e-5, weight_decay=.01)
    order = list(range(344)); random.Random(20261021).shuffle(order)
    write(output/'sample_order.json', [rows[i]['id'] for i in order])
    model.train(); model.config.use_cache = False
    position = updates = seen = 0
    with (output/'training.jsonl').open('x', encoding='utf8') as stream:
        while position < 344 and time.monotonic() < cutoff:
            window = [rows[i] for i in order[position:position+8]]
            optimizer.zero_grad(set_to_none=True); total = 0.; tick = time.monotonic()
            for group in optimizer.param_groups:
                group['lr'] = 1e-5 * min(1., (updates+1)/2)
            for row in window:
                loss = loss_for(model, row); assert bool(torch.isfinite(loss))
                (loss/len(window)).backward(); total += float(loss.detach())/len(window)
                del loss
            assert any(p.grad is not None and bool(torch.any(p.grad != 0)) for n,p in parameters)
            assert all(p.grad is None or bool(torch.all(torch.isfinite(p.grad))) for n,p in parameters)
            norm = torch.nn.utils.clip_grad_norm_([p for n,p in parameters], 1.)
            assert bool(torch.isfinite(norm))
            optimizer.step(); position += len(window); updates += 1
            seen += sum(len(r['input_ids']) for r in window)
            item = dict(update=updates, position=position, loss=total, grad_norm=float(norm), seconds=time.monotonic()-tick)
            stream.write(json.dumps(item)+'\n'); stream.flush(); event('full_answer_update', **item)
        saved = checkpoint(model, optimizer, output, position, updates, seen)
    write(output/'status.json', dict(completed=position==344, updates=updates, samples=position,
          checkpoint=str(saved), seconds=time.monotonic()-started, peak_bytes=torch.cuda.max_memory_allocated()))
    del model, optimizer
    torch.cuda.empty_cache(); event('full_answer_finished', updates=updates, samples=position)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    if not args.run:
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    (run if args.run else preflight)(args.root)
