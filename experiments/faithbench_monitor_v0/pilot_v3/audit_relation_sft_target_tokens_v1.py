"""CPU-only descriptive token allocation in the already used 144 targets."""
import os
import sys
import json
import hashlib
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'experiments/faithbench_monitor_v0/private/relation_sft_comparison_20261011'
ASSETS = ROOT / 'experiments/faithbench_monitor_v0/private/relation_sft_materials_v1_20261011'
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
sys.path.insert(0, str(ASSETS / 'python_libs'))


def run():
    from transformers import AutoTokenizer
    package = json.loads((HERE / 'inputs.json').read_text(encoding='utf8'))
    tokenizer = AutoTokenizer.from_pretrained(ASSETS / 'tokenizer_cache', local_files_only=True)
    summaries, details = {}, []
    for method, rows in package['train'].items():
        results = []
        for row in rows:
            messages = [{'role': 'user', 'content': row['user_text']}]
            prefix_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            prefix_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
            body = row['assistant_text']
            messages.append({'role': 'assistant', 'content': body})
            full_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            full_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False)
            encoded = tokenizer(full_text, add_special_tokens=False, return_offsets_mapping=True)
            assert encoded['input_ids'] == full_ids and full_ids[:len(prefix_ids)] == prefix_ids
            assert full_text.startswith(prefix_text + body)
            positions = {}
            for key in ['reason', 'return_reference_ids', 'judgement']:
                marker = '"' + key + '":'
                start = body.index(marker) + len(marker)
                end = start + len(json.dumps(row['answer'][key], ensure_ascii=False, separators=(',', ':')))
                if key != 'return_reference_ids':
                    start += 1
                    end -= 1
                lo, hi = len(prefix_text) + start, len(prefix_text) + end
                positions[key] = [i for i, (a, b) in enumerate(encoded['offset_mapping']) if i >= len(prefix_ids) and a < hi and b > lo]
            record = {'id': row['id'], 'method': method, 'assistant_tokens': len(full_ids) - len(prefix_ids), 'value_overlap_token_counts': {key: len(value) for key, value in positions.items()}}
            record['judgement_value_share_of_supervised_tokens'] = len(positions['judgement']) / record['assistant_tokens']
            results.append(record)
        summaries[method] = {'records': len(results), 'supervised_tokens': sum(row['assistant_tokens'] for row in results),
            'value_overlap_token_totals': {key: sum(row['value_overlap_token_counts'][key] for row in results) for key in ['reason', 'return_reference_ids', 'judgement']},
            'mean_per_step_judgement_value_share': statistics.mean(row['judgement_value_share_of_supervised_tokens'] for row in results)}
        details.extend(results)
    assert summaries['ordinary']['supervised_tokens'] == 3404 and summaries['relation']['supervised_tokens'] == 4366
    assert summaries['ordinary']['value_overlap_token_totals']['judgement'] == summaries['relation']['value_overlap_token_totals']['judgement']
    result = {'kind': 'posthoc_target_token_allocation_only', 'model_loaded': False, 'new_model_requests': 0, 'optimizer_steps': 0,
              'method': 'Fast tokenizer offsets on exact full chat text; tokens overlapping reason/judgement string contents, and reference array serialization. Includes no measured token loss.',
              'limits': ['Shares describe equal-step mean-token supervision, not gradient size or causal contribution.', 'Per-field/token losses and final teacher-forcing/generation accuracy are unavailable.', 'No target or training objective changed.'],
              'summary': summaries, 'rows': details, 'input_sha256': hashlib.sha256((HERE / 'inputs.json').read_bytes()).hexdigest(),
              'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    path = HERE / 'posthoc_target_token_audit_v1.json'
    with path.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(summaries))


if __name__ == '__main__':
    run()
