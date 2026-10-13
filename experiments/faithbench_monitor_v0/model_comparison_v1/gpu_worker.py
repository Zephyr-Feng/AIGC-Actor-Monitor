"""Five frozen text requests, reusing the prior BF16 baseline configuration."""
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/actor_b'))
from run_b0 import canonical_hash, sha256, write_json

PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private/model_comparison_v1_20261012'
BASE = Path('/root/autodl-tmp/mini-faithbench-v0/model-cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b')


def protection():
    expected = json.loads((PRIVATE / 'expected_protection.json').read_text())
    actual = {name: {'size': Path(name).stat().st_size, 'sha256': sha256(Path(name))} for name in expected}
    assert actual == expected
    return actual


def main():
    import torch
    import transformers
    torch.set_num_threads(2)
    assert torch.__version__ == '2.12.1+cu130' and transformers.__version__ == '4.57.4'
    assert torch.cuda.is_available()
    package = json.loads((PRIVATE / 'inputs.json').read_text())
    freeze = json.loads((PRIVATE / 'freeze.json').read_text())
    expected = json.loads((PRIVATE / 'cpu_preflight.json').read_text())
    assert all(sha256(PRIVATE / n) == h for n, h in freeze['files'].items())
    assert package['a_new_request_limit'] == 5 and len(package['a_order']) == 5
    assert 'E1' not in package['a_order'] and package['adapter'] is None
    assert package['training_steps'] == package['actor_requests'] == 0 and not package['execute_tools']
    assert BASE.name == package['model_spec']['model_revision']
    assert all(sha256(BASE / n) == h for n, h in freeze['tokenizer_assets'].items())
    assert not (ROOT / 'output').exists()
    before = protection()
    write_json(ROOT / 'protection_before.json', before)
    tokenizer = transformers.AutoTokenizer.from_pretrained(BASE, local_files_only=True)
    inputs_by_case = {}
    for cid in package['a_order']:
        messages = package['cases'][cid]['messages']
        ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        assert len(ids) == expected[cid]['input_tokens']
        assert canonical_hash(ids) == expected[cid]['input_ids_sha256']
        assert canonical_hash(messages) == expected[cid]['messages_sha256']
        inputs_by_case[cid] = ids
    write_json(ROOT / 'deployment_preflight.json', {'cases': {cid: expected[cid] for cid in package['a_order']},
               'torch': torch.__version__, 'transformers': transformers.__version__, 'base': str(BASE),
               'generation': package['generation'], 'adapter': None, 'dtype': package['dtype']})
    print('25 protection files and all five token sequences verified', flush=True)
    output = ROOT / 'output'
    output.mkdir()
    torch.manual_seed(package['generation']['seed'])
    torch.cuda.manual_seed_all(package['generation']['seed'])
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        BASE, dtype=torch.bfloat16, device_map='cuda', local_files_only=True).eval()
    print('BF16 base loaded; five requests only', flush=True)
    try:
        for cid in package['a_order']:
            ids = inputs_by_case[cid]
            inputs = torch.tensor([ids], dtype=torch.long, device='cuda')
            torch.cuda.synchronize()
            start = time.perf_counter()
            with torch.inference_mode():
                generated = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                    max_new_tokens=1024, do_sample=False, repetition_penalty=1.05)
            torch.cuda.synchronize()
            tokens = generated[0, len(ids):].tolist()
            eos = model.generation_config.eos_token_id
            eos_ids = eos if isinstance(eos, list) else [eos]
            write_json(output / (cid + '.json'), {'case': cid, 'raw': tokenizer.decode(tokens, skip_special_tokens=True),
                       'output_ids': tokens, 'input_tokens': len(ids), 'output_tokens': len(tokens),
                       'seconds': time.perf_counter() - start, 'ended_with_eos': bool(tokens and tokens[-1] in eos_ids),
                       'hit_token_budget': len(tokens) >= 1024, 'messages_sha256': expected[cid]['messages_sha256']})
            print(cid + ' raw saved: ' + str(len(tokens)) + ' tokens', flush=True)
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
    write_json(ROOT / 'protection_after.json', protection())
    write_json(ROOT / 'worker_completed.json', {'requests': 5, 'protection_verified': len(before),
                                              'training_steps': 0, 'actor_requests': 0, 'tool_calls': 0})
    print('worker completed', flush=True)


if __name__ == '__main__':
    main()
