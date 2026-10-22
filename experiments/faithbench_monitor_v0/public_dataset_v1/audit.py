"""Audit content, groups, image presence and exported targets."""
from collections import Counter, defaultdict
import argparse
import json
from build import DATA, sft


def read(path):
    with path.open(encoding='utf8') as handle:
        for line in handle:
            yield json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    args = parser.parse_args()
    root = (DATA / args.directory).resolve()
    if root.parent != DATA.resolve():
        raise ValueError('unexpected data path')
    groups, samples = defaultdict(set), defaultdict(list)
    counts, labels, positions = Counter(), Counter(), Counter()
    ids, lengths = set(), defaultdict(list)
    for split in ('train', 'validation', 'test'):
        exported = read(root / f'{split}.sft.jsonl')
        for record in read(root / f'{split}.records.jsonl'):
            assert record['id'] not in ids, 'duplicate record id'
            ids.add(record['id'])
            assert record['split'] == split
            groups[split].add(record['group'])
            counts[f"{split}/{record['dataset']}"] += 1
            actual = next(exported)
            assert actual == sft(record), 'export mismatch'
            user = json.loads(actual['messages'][1]['content'].removeprefix('<image>\n'))
            assert user['材料'] == record['input'], 'label metadata leaked'
            lengths[record['task']].append(sum(len(x['content']) for x in actual['messages']))
            if record['task'] == 'ragtruth_spans':
                category = 'error' if record['target']['问题片段'] else 'no_annotated_error'
                for span in record['target']['问题片段']:
                    assert record['input']['待核回答'][span['起点']:span['终点']] == span['原文']
            elif record['task'] == 'ragbench_support':
                category = 'not_fully_supported' if any(x['判定'] == '未完整支持' for x in record['target']['逐句核对']) else 'supported'
                for annotation in record['target']['逐句核对']:
                    assert annotation['回答句编号'] in record['input']['待核回答句']
                    assert all(ref in record['input']['证据句'] for ref in annotation['原标注依据编号'])
            else:
                category = record['target']['较优反馈']
                positions[f'{split}/{category}'] += 1
                image = (root / record['image']).resolve()
                assert image.is_relative_to(root / 'images') and image.is_file()
            labels[f"{split}/{record['task']}/{category}"] += 1
            bucket = f"{split}/{record['task']}/{category}"
            if split != 'test' and len(samples[bucket]) < 3:
                samples[bucket].append(record)
        assert next(exported, None) is None, 'extra export rows'
    for a, b in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
        assert not groups[a].intersection(groups[b]), 'group leakage'
    length_summary = {}
    for task, values in lengths.items():
        values.sort()
        length_summary[task] = {'median_chars': values[len(values) // 2], 'p95_chars': values[int((len(values) - 1) * .95)], 'max_chars': values[-1]}
    report = {'counts': dict(counts), 'labels': dict(labels), 'visual_position_counts': dict(positions), 'groups': {k: len(v) for k, v in groups.items()}, 'lengths': length_summary, 'structural_checks_passed': True, 'independent_semantic_reviewers': 0, 'tokenized': False}
    if (root / 'tiers.json').exists():
        tiers = json.loads((root / 'tiers.json').read_text(encoding='utf8'))
        tier_counts, tier_ids = Counter(), set()
        quarantine = json.loads((root / 'semantic_quarantine.json').read_text(encoding='utf8'))
        quarantined_ids = {item['record']['id'] for item in quarantine}
        for split in ('train', 'validation', 'test'):
            for tier in ('primary', 'visual_aux', 'silver_candidate'):
                exported = read(root / f'{split}.{tier}.sft.jsonl')
                for record in read(root / f'{split}.{tier}.records.jsonl'):
                    assert record['id'] in ids and record['id'] not in tier_ids
                    assert record['id'] not in quarantined_ids
                    assert record['split'] == split
                    assert record['dataset'] == {'primary': 'ragtruth', 'visual_aux': 'critic_v', 'silver_candidate': 'ragbench'}[tier]
                    assert next(exported) == sft(record)
                    tier_ids.add(record['id'])
                    tier_counts[f'{split}/{tier}'] += 1
                assert next(exported, None) is None
        assert tier_ids == ids - quarantined_ids
        assert dict(tier_counts) == tiers['counts']
        assert tiers['silver_training_enabled'] is False
        report['tier_checks_passed'] = True
        report['tier_counts'] = dict(tier_counts)
    (root / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (root / 'review_samples.json').write_text(json.dumps(dict(samples), ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
