"""Evaluate the recovered checkpoint on the original frozen development rows."""
import argparse
import json
import os
from pathlib import Path
import time

from fava_trial import evaluate, readl, write


def frozen_rows(root):
    rows = readl(root/'development_pool.tokens.jsonl')
    before = readl(root/'before.jsonl')
    assert len(rows) == len(before) == 16
    assert len({r['id'] for r in rows}) == 16
    assert [r['id'] for r in rows] == [r['id'] for r in before]
    assert all(0 < r['prefix_length'] < len(r['input_ids']) <= 4096 for r in rows)
    return rows


def check_authorization(auth, now):
    assert auth['approved'] is True
    assert auth['purpose'] == 'checkpoint373_existing16_only'
    assert auth['training_updates'] == auth['training_epochs'] == 0
    assert 0 < auth['max_gpu_seconds'] <= 1200
    assert auth['deadline_epoch']-auth['start_epoch'] == auth['max_gpu_seconds']
    assert auth['start_epoch'] <= now < auth['deadline_epoch']


def run(root, base, checkpoint):
    auth = json.loads((root/'authorization.json').read_text(encoding='utf8'))
    check_authorization(auth, time.time())
    assert checkpoint.name == 'checkpoint-00373'
    rows = frozen_rows(root)
    output = root/'run'
    output.mkdir(exist_ok=False)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_XET='1')
    import torch
    from transformers import AutoTokenizer, BitsAndBytesConfig, Qwen3_5ForConditionalGeneration
    from peft import PeftModel, prepare_model_for_kbit_training

    torch.manual_seed(20261018)
    torch.cuda.manual_seed_all(20261018)
    write(output/'config.json', {**auth, 'base': str(base), 'checkpoint': str(checkpoint),
          'development_ids': [r['id'] for r in rows], 'training_started': False,
          'gpu': torch.cuda.get_device_name(), 'context_limit': 4096, 'max_new_tokens': 768})
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
              bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(base, local_files_only=True,
              dtype=torch.bfloat16, quantization_config=quant, device_map={'': 0},
              attn_implementation='sdpa')
    # Match the original evaluation's float32 norms and bfloat16 embeddings.
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model.get_input_embeddings().to(dtype=torch.bfloat16)
    model.get_output_embeddings().to(dtype=torch.bfloat16)
    model.model.visual.to(device='cpu')
    model = PeftModel.from_pretrained(model, checkpoint/'adapter',
                                     is_trainable=False, local_files_only=True)
    assert not any(p.requires_grad for p in model.parameters())
    result = evaluate(model, tokenizer, rows, output, 'after', auth['deadline_epoch'])
    del model
    torch.cuda.empty_cache()
    write(output/'status.json', {'after': result, 'finished_epoch': time.time(),
          'training_started': False, 'training_updates': 0})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.run:
        assert args.base is not None and args.checkpoint is not None
        run(args.root, args.base, args.checkpoint)
    else:
        print(json.dumps({'rows': len(frozen_rows(args.root)), 'model_loaded': False,
                          'training_started': False}))
