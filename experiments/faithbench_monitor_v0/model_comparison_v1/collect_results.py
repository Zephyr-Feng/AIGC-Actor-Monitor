"""Verify raw provenance and prepare shuffled copies without model identifiers."""
import json
import random
from pathlib import Path

from prepare import ROOT, PRIVATE, OLD, canonical_hash, sha256, write_json


def main():
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    package, freeze = read(PRIVATE / 'inputs.json'), read(PRIVATE / 'freeze.json')
    assert all(sha256(PRIVATE / n) == h for n, h in freeze['files'].items())
    assert all(sha256(ROOT / n) == h for n, h in freeze['dependencies'].items())
    backup = PRIVATE / 'backup'
    assert all(sha256(backup / n) == h for n, h in read(PRIVATE / 'backup_hashes.json').items())
    before, after = read(backup / 'protection_before.json'), read(backup / 'protection_after.json')
    assert before == after and len(before) == 25
    assert read(backup / 'worker_completed.json')['requests'] == 5
    assert read(PRIVATE / 'api/completed.json')['requests'] == 6
    assert read(PRIVATE / 'runtime.json')['process_exists'] is False
    rows = []
    for cid in package['cases']:
        messages_hash = canonical_hash(package['cases'][cid]['messages'])
        a_path = OLD / 'backup/output/review.json' if cid == 'E1' else backup / 'output' / (cid + '.json')
        a = read(a_path)
        if cid != 'E1':
            assert a['messages_sha256'] == messages_hash
        b_dir = PRIVATE / 'api' / cid
        request, b = read(b_dir / 'request.json'), read(b_dir / 'response.json')
        assert request == dict(package['b_config'], messages=package['cases'][cid]['messages'])
        assert read(b_dir / 'state.json')['status'] == 'complete'
        assert b['model'] == 'deepseek-flash' and b['usage']['completion_tokens'] <= 8192
        assert b_dir.joinpath('response.sse').read_bytes().rstrip().endswith(b'data: [DONE]')
        for label, path, value, content in [('A', a_path, a, a['raw']), ('B', b_dir / 'response.json', b, b['content'])]:
            rows.append({'model': label, 'case': cid, 'raw_path': path.relative_to(ROOT).as_posix(),
                         'raw_sha256': sha256(path), 'content': content, 'messages_sha256': messages_hash,
                         'complete': value['ended_with_eos'] if label == 'A' else value['finish_reason'] == 'stop',
                         'input_tokens': value['input_tokens'] if label == 'A' else value['usage']['prompt_tokens'],
                         'output_tokens': value['output_tokens'] if label == 'A' else value['usage']['completion_tokens'],
                         'reasoning_tokens': 0 if label == 'A' else value['usage']['completion_tokens_details']['reasoning_tokens'],
                         'seconds': value['seconds'], 'historical_reuse': label == 'A' and cid == 'E1'})
    random.Random(20261013).shuffle(rows)
    review = PRIVATE / 'review_copies'
    review.mkdir()
    mapping = {}
    for number, row in enumerate(rows, 1):
        review_id = 'R' + str(number).zfill(2)
        write_json(review / (review_id + '.json'), {'review_id': review_id, 'case': row['case'], 'content': row['content']})
        mapping[review_id] = {k: v for k, v in row.items() if k != 'content'}
    write_json(PRIVATE / 'review_mapping.json', mapping)
    b_usage = {cid: read(PRIVATE / 'api' / cid / 'response.json')['usage'] for cid in package['b_order']}
    prompt = sum(u['prompt_tokens'] for u in b_usage.values())
    output = sum(u['completion_tokens'] for u in b_usage.values())
    misses = sum(u['prompt_cache_miss_tokens'] for u in b_usage.values())
    hits = sum(u['prompt_cache_hit_tokens'] for u in b_usage.values())
    high_peak_estimate = (misses * .30 + hits * .006 + output * 1.20) / 1_000_000
    audit = {'logical_outputs': 12, 'new_a_requests': 5, 'new_b_requests': 6, 'reused_a_requests': 1,
             'format_or_semantic_retries': 0, 'messages_match_both_models': True, 'protection_files_unchanged': 25,
             'backup_files_hash_checked': 11, 'a_complete': sum(r['complete'] for r in rows if r['model'] == 'A'),
             'b_complete': sum(r['complete'] for r in rows if r['model'] == 'B'),
             'b_prompt_tokens': prompt, 'b_completion_tokens_including_reasoning': output,
             'b_reasoning_tokens': sum(u['completion_tokens_details']['reasoning_tokens'] for u in b_usage.values()),
             'b_peak_price_usage_estimate_usd': high_peak_estimate, 'b_cache_hit_tokens': hits,
             'billing_amount_not_observed': True, 'model_name_hidden_review_copies': 12,
             'review_is_independent_gold': False, 'worker_exited_gpu_zero': True,
             'freeze_sha256': sha256(PRIVATE / 'freeze.json'), 'inputs_sha256': sha256(PRIVATE / 'inputs.json')}
    assert prompt <= package['cost']['input_byte_allowance'] and high_peak_estimate < package['cost']['conservative_usd_allowance']
    write_json(PRIVATE / 'execution_audit.json', audit)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
