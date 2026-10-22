"""Keep error cases; cap supported cases at 2:1, without repeating records."""
from collections import Counter, defaultdict
import argparse
import json
import random

from build import DATA, SEED, sft


def category(row):
    if row['task'] == 'ragtruth_spans':
        return 'error' if row['target']['问题片段'] else 'supported'
    if row['task'] == 'ragbench_support':
        return 'error' if any(x['判定'] == '未完整支持' for x in row['target']['逐句核对']) else 'supported'
    return 'visual'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    args = parser.parse_args()
    root = (DATA / args.directory).resolve()
    if root.parent != DATA.resolve():
        raise ValueError('unexpected data path')
    rows = [json.loads(line) for line in (root / 'train.records.jsonl').open(encoding='utf8')]
    buckets = defaultdict(list)
    for index, row in enumerate(rows):
        assert row['split'] == 'train'
        buckets[(row['task'], category(row))].append(index)
    selected = []
    rng = random.Random(SEED)
    for (task, kind), indexes in sorted(buckets.items()):
        if kind == 'supported':
            limit = 2 * len(buckets[(task, 'error')])
            if not limit:
                raise ValueError('no error examples for balancing')
            indexes = rng.sample(indexes, min(limit, len(indexes)))
        selected.extend(indexes)
    rng.shuffle(selected)
    assert len(selected) == len(set(selected))
    distribution = Counter()
    with (root / 'train.recommended.records.jsonl').open('x', encoding='utf8') as records, (root / 'train.recommended.sft.jsonl').open('x', encoding='utf8') as exported:
        for index in selected:
            row = rows[index]
            distribution[row['task'] + '/' + category(row)] += 1
            records.write(json.dumps(row, ensure_ascii=False) + '\n')
            exported.write(json.dumps(sft(row), ensure_ascii=False) + '\n')
    result = {'seed': SEED, 'rows': len(selected), 'groups': len({rows[i]['group'] for i in selected}), 'distribution': dict(distribution), 'policy': 'All error rows and all visual rows; supported rows capped at 2 per error within each text task. No duplicate sampling; validation/test unchanged.'}
    (root / 'mix.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
