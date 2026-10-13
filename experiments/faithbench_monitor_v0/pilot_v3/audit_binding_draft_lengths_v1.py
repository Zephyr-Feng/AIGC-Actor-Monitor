"""Measure six frozen draft bodies locally; no prompt, target or budget changes."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'experiments/faithbench_monitor_v0/private/evidence_binding_drafts_v1_20261011'
ASSETS = ROOT / 'experiments/faithbench_monitor_v0/private/relation_sft_materials_v1_20261011'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze = json.loads((HERE / 'freeze.json').read_text(encoding='utf-8'))
    for name, digest in freeze['artifact_hashes'].items():
        assert sha(ROOT / name) == digest, name
    provenance = json.loads((ASSETS / 'tokenizer_cache_provenance.json').read_text(encoding='utf-8'))
    for name, expected in provenance['files'].items():
        assert sha(ASSETS / 'tokenizer_cache' / name) == expected['sha256'], name
    os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1')
    sys.path.insert(0, str(ASSETS / 'python_libs'))
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(ASSETS / 'tokenizer_cache', local_files_only=True)
    drafts = json.loads((HERE / 'drafts.json').read_text(encoding='utf-8'))['records']
    rows = []
    for draft in drafts:
        body = json.dumps(draft['draft_target'], ensure_ascii=False, separators=(',', ':'))
        old = json.dumps(draft['original_relation_target'], ensure_ascii=False, separators=(',', ':'))
        encoded = tokenizer(body, add_special_tokens=False, return_offsets_mapping=True)
        ids = encoded['input_ids']
        assert tokenizer.decode(ids) == body
        marker = '"judgement":'
        position = body.rindex(marker) + len(marker)
        first = next(i for i, (a, b) in enumerate(encoded['offset_mapping']) if b > position)
        rows.append(dict(source_case_id=draft['source_case_id'],
                         compact_draft_body_tokens=len(ids),
                         original_relation_body_tokens=len(tokenizer.encode(old, add_special_tokens=False)),
                         fits_old_384_body_budget=len(ids) <= 384,
                         judgement_value_first_token_index_zero_based=first,
                         judgement_value_starts_within_384=first < 384))
    result = dict(kind='frozen_six_draft_output_body_length_only',
                  method='Exact compact JSON body, standalone tokenization, no special tokens; offsets locate final judgement value.',
                  limits=['No new prompt defined or tokenized; not a new full-chat context or assistant-mask preflight.',
                          'Body token counts omit chat end tokens and do not measure actual model generation.',
                          '384 is the completed comparison budget, not an approved new budget.',
                          'Draft schema, targets, runner and budgets remain unchanged.'],
                  model_loaded=False, model_requests=0, optimizer_steps=0, remote_calls=0,
                  rows=rows, old_budget_body_fit_count=sum(r['fits_old_384_body_budget'] for r in rows),
                  draft_token_range=[min(r['compact_draft_body_tokens'] for r in rows),
                                     max(r['compact_draft_body_tokens'] for r in rows)],
                  input_sha256=sha(HERE / 'drafts.json'), source_freeze_sha256=sha(HERE / 'freeze.json'),
                  tokenizer_asset_hashes={name: v['sha256'] for name, v in provenance['files'].items()},
                  code_sha256=sha(Path(__file__)))
    with (HERE / 'output_length_audit_v1.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(dict(rows=rows, range=result['draft_token_range'],
                         fits_384=result['old_budget_body_fit_count']), ensure_ascii=False))


if __name__ == '__main__':
    main()
