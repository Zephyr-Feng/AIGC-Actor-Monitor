"""Separate primary supervision, visual auxiliary labels and unverified silver."""
from collections import Counter
import argparse
import json
import random
from build import DATA, SEED, sft

DISPUTED = {'ragbench:delucionqa:train:369:9': '原文0a/2a与0c/0f均指Stop/Start Off同一开关；教师却以不同机制为由否定回答a。助手抽查标为待裁决，未改原始标签。'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    args = parser.parse_args()
    root = (DATA / args.directory).resolve()
    if root.parent != DATA.resolve():
        raise ValueError('unexpected data path')
    counts, handles = Counter(), {}
    rng = random.Random(SEED)
    quarantined = []
    try:
        for split in ('train', 'validation', 'test'):
            rows = [json.loads(line) for line in (root / f'{split}.records.jsonl').open(encoding='utf8')]
            rng.shuffle(rows)
            for row in rows:
                if row['id'] in DISPUTED:
                    quarantined.append({'record': row, 'reason': DISPUTED[row['id']], 'independent_human_confirmed': False})
                    continue
                tier = {'ragtruth': 'primary', 'critic_v': 'visual_aux', 'ragbench': 'silver_candidate'}[row['dataset']]
                counts[f'{split}/{tier}'] += 1
                for kind, value in [('records', row), ('sft', sft(row))]:
                    name = f'{split}.{tier}.{kind}.jsonl'
                    if name not in handles:
                        handles[name] = (root / name).open('x', encoding='utf8')
                    handles[name].write(json.dumps(value, ensure_ascii=False) + '\n')
    finally:
        for handle in handles.values():
            handle.close()
    (root / 'semantic_quarantine.json').write_text(json.dumps(quarantined, ensure_ascii=False, indent=2), encoding='utf8')
    for name in ('train.recommended.records.jsonl', 'train.recommended.sft.jsonl', 'mix.json'):
        old = root / name
        if old.exists():
            old.rename(root / ('pre_review_' + name))
    report = {'counts': dict(counts), 'quarantined': len(quarantined), 'default_text_training': 'train.primary.sft.jsonl', 'visual_auxiliary': 'train.visual_aux.sft.jsonl', 'silver_training_enabled': False, 'note': 'RAGBench remains unverified. pre_review files are obsolete, not training defaults.'}
    (root / 'tiers.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
