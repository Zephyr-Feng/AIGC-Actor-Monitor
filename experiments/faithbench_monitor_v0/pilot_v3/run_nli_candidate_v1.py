"""Local-only FP32 CPU NLI diagnostic; execution requires confirmed conditions.

Uses the author's AutoTokenizer/AutoModel NLI pattern. No network downloads,
training, GPU dispatch, label conversion or Monitor integration happen here.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(checkpoint, inputs_path, output_path):
    import torch
    import transformers
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

    started = time.monotonic()
    data = json.loads(inputs_path.read_text(encoding='utf8'))
    rows = data['inputs']
    if data['inference_fields'] != ['premise', 'hypothesis'] or len(rows) != 20:
        raise ValueError('expected the reviewed 20-input candidate projection')
    if output_path.exists():
        raise FileExistsError(output_path)
    torch.set_num_threads(4)
    config = AutoConfig.from_pretrained(checkpoint, local_files_only=True, trust_remote_code=False)
    labels = {int(key): value for key, value in config.id2label.items()}
    if labels != {0: 'entailment', 1: 'neutral', 2: 'contradiction'}:
        raise ValueError('checkpoint label order differs from reviewed author config')
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True, trust_remote_code=False)
    encoded = [tokenizer(row['premise'], row['hypothesis'], truncation=False, return_tensors='pt') for row in rows]
    lengths = [item['input_ids'].shape[-1] for item in encoded]
    if max(lengths) > config.max_position_embeddings:
        raise ValueError('candidate exceeds context; no silent truncation')
    print(json.dumps({'phase': 'tokenizer_preflight', 'inputs': len(rows), 'max_tokens': max(lengths)}), flush=True)
    checkpoint_hashes = {path.name: sha(path) for path in checkpoint.iterdir() if path.is_file()}
    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint, local_files_only=True, trust_remote_code=False,
        use_safetensors=True, torch_dtype=torch.float32).to('cpu').eval()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('x', encoding='utf8', newline='\n') as stream:
        def save(record):
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
            stream.flush()
        save({'kind': 'run_metadata', 'inputs_sha256': sha(inputs_path),
              'checkpoint_hashes': checkpoint_hashes, 'id2label': labels,
              'device': 'cpu', 'dtype': 'float32', 'torch_threads': 4,
              'torch_version': torch.__version__, 'transformers_version': transformers.__version__,
              'model_parameters': sum(parameter.numel() for parameter in model.parameters()),
              'load_seconds': time.monotonic() - started, 'new_training_records': 0})
        with torch.inference_mode():
            for index, (row, tensors) in enumerate(zip(rows, encoded)):
                before = time.monotonic()
                probabilities = model(**tensors).logits[0].softmax(-1)
                if not torch.isfinite(probabilities).all():
                    raise ValueError('nonfinite model probabilities')
                prediction = int(probabilities.argmax().item())
                save({'kind': 'prediction', 'id': row['id'], 'input_tokens': lengths[index],
                      'probabilities': {labels[key]: float(probabilities[key]) for key in labels},
                      'predicted_NLI_label': labels[prediction], 'seconds': time.monotonic() - before})
                print(json.dumps({'completed': index + 1, 'total': len(rows),
                                  'elapsed_seconds': time.monotonic() - started}), flush=True)
        save({'kind': 'completion', 'predictions': len(rows), 'seconds': time.monotonic() - started,
              'Monitor_state_mapping_performed': False, 'new_training_records': 0})
    print(json.dumps({'output_sha256': sha(output_path), 'predictions': len(rows)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    run(args.checkpoint, args.inputs, args.output)
