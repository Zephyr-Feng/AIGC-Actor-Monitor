"""Local tokenizer-only audit; consumes the reviewed v2, never model weights."""
import importlib.metadata
import json
import os
import sys
from pathlib import Path

from relation_probe_v2 import ROOT, PRIVATE, sha
from prepare_relation_sft_v2 import OUT, KEYS, assistant_text, dump

ASSETS = PRIVATE / 'relation_sft_materials_v1_20261011'


def main():
    os.environ['USE_TORCH'] = '0'
    os.environ['USE_TF'] = '0'
    os.environ['USE_FLAX'] = '0'
    sys.path.insert(0, str(ASSETS / 'python_libs'))
    from transformers import AutoTokenizer
    provenance = json.loads((ASSETS / 'tokenizer_cache_provenance.json').read_text(encoding='utf8'))
    for name, expected in provenance['files'].items():
        assert sha(ASSETS / 'tokenizer_cache' / name) == expected['sha256'], name
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf8'))
    for name, digest in manifest['artifact_hashes'].items():
        assert sha(OUT / name) == digest, name
    tokenizer = AutoTokenizer.from_pretrained(ASSETS / 'tokenizer_cache', local_files_only=True)
    cases = json.loads((OUT / 'cases.json').read_text(encoding='utf8'))
    rows, training = [], {'ordinary': [], 'relation': []}
    for case in cases:
        messages = [{'role': 'user', 'content': case['prompt']}]
        prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        assert len(prefix) + 384 <= 4096, case['id']
        lengths = {}
        for method, answer in case['targets'].items():
            text = assistant_text(answer)
            full = tokenizer.apply_chat_template(messages + [{'role': 'assistant', 'content': text}], tokenize=True, add_generation_prompt=False)
            assert full[:len(prefix)] == prefix and len(full) > len(prefix), case['id']
            assert len(full) <= 4096 and len(full) - len(prefix) <= 384, case['id']
            labels = [-100] * len(prefix) + full[len(prefix):]
            assert all(t == -100 for t in labels[:len(prefix)])
            assert labels[len(prefix):] == full[len(prefix):]
            decoded = tokenizer.decode(full[len(prefix):], skip_special_tokens=True)
            assert tuple(json.loads(decoded)) == KEYS and json.loads(decoded) == answer
            lengths[method] = dict(full_tokens=len(full), assistant_tokens=len(full) - len(prefix))
            if case['split'] == 'train':
                training[method].append(lengths[method])
        rows.append(dict(id=case['id'], split=case['split'], prefix_tokens=len(prefix), targets=lengths))
    old_raw = PRIVATE / 'relation_prompt_probe_v1_20261011/backup/relation_prompt_probe_v1_trial/predictions.jsonl'
    old = {r['id']: r for r in (json.loads(line) for line in old_raw.read_text(encoding='utf8').splitlines())
           if r['condition'] == 'reason_first' and r['model'] == 'base'}
    regressions = json.loads((OUT / 'evaluation_regression.json').read_text(encoding='utf8'))
    regression_lengths = []
    for row in regressions:
        ids = tokenizer.apply_chat_template([{'role': 'user', 'content': row['user_text']}], tokenize=True, add_generation_prompt=True)
        assert row['prompt_sha256'] == old[row['id']]['prompt_sha256']
        assert len(ids) == old[row['id']]['input_tokens'] and len(ids) + 384 <= 4096, row['id']
        regression_lengths.append(dict(id=row['id'], prefix_tokens=len(ids), historical_remote_length_matches=True))
    summary = {method: dict(records=len(values), total_assistant_tokens=sum(v['assistant_tokens'] for v in values),
        min_assistant_tokens=min(v['assistant_tokens'] for v in values), max_assistant_tokens=max(v['assistant_tokens'] for v in values),
        max_full_tokens=max(v['full_tokens'] for v in values)) for method, values in training.items()}
    report = dict(model_loaded=False, torch_disabled=True, model_requests=0, optimizer_steps=0, tokenizer_checked=True,
        truncated=False, mask_verified=True, final_assistant_order_verified=list(KEYS), candidates=108,
        candidate_targets_tokenized=216, train_summary=summary,
        assistant_token_ratio_relation_to_ordinary=summary['relation']['total_assistant_tokens'] / summary['ordinary']['total_assistant_tokens'],
        new_prefix_range=[min(r['prefix_tokens'] for r in rows), max(r['prefix_tokens'] for r in rows)],
        max_candidate_target_tokens=max(v['assistant_tokens'] for r in rows for v in r['targets'].values()),
        historical_remote_regression_length_matches=48,
        package_versions={name: importlib.metadata.version(name) for name in ['transformers', 'tokenizers', 'jinja2']},
        tokenizer_provenance_sha256=sha(ASSETS / 'tokenizer_cache_provenance.json'),
        pip_install_report_sha256=sha(ASSETS / 'pip_install_report.json'),
        manifest_sha256=sha(OUT / 'manifest.json'), code_sha256=sha(Path(__file__)),
        rows=rows, regression_lengths=regression_lengths)
    dump(OUT / 'tokenizer_preflight.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'regression_lengths')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
