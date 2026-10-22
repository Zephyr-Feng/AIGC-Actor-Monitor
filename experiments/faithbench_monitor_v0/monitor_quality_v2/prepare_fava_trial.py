"""Freeze source-grouped FAVA edit data; no model loading."""
import argparse
import json
from pathlib import Path
import random

SEED = 20261018
SYSTEM = ('你是中文审核助手。本任务只定位并编辑回答中的错误，不生成理由或证据绑定。'
          '只输出JSON：{"问题":[{"起点":整数,"终点":整数,"回答原文":"原句","建议":"替换文本"}]}。'
          '使用Python字符索引，终点不包含；插入时起点等于终点且原文为空，删除时建议为空。'
          '依据参考文本给出必要的最小编辑，其他内容保持不变。')


def prepare(source, output):
    with source.open(encoding='utf8') as f:
        rows = [json.loads(line) for line in f]
    groups = sorted({r['screening']['source_group'] for r in rows})
    random.Random(SEED).shuffle(groups)
    development = set(groups[:max(1, round(len(groups) * .1))])
    output.mkdir(exist_ok=False)
    counts = {'train': 0, 'development_pool': 0}
    with (output/'train.sft.jsonl').open('x', encoding='utf8') as train, (output/'development_pool.sft.jsonl').open('x', encoding='utf8') as dev:
        for row in rows:
            assert row['screening']['status'] == 'candidate'
            assert row['supervision']['all_flagged_issues_have_explicit_edits']
            group = row['screening']['source_group']
            split = 'development_pool' if group in development else 'train'
            target = {'问题': [{'起点': i['start'], '终点': i['end'], '回答原文': i['quote'], '建议': i['replacement']} for i in row['supervision']['issues']]}
            material = {'证据卡': row['input']['证据卡'], '待核回答': row['input']['待核回答']}
            record = {'id': row['id'], 'group': group, 'source_record_index': row['source_record_index'],
                      'human_gold': False, 'approved_for_this_trial': True,
                      'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)}, {'role': 'assistant', 'content': json.dumps(target, ensure_ascii=False)}],
                      'target': target, 'author_corrected_answer': row['supervision']['corrected_answer']}
            (dev if split == 'development_pool' else train).write(json.dumps(record, ensure_ascii=False)+'\n')
            counts[split] += 1
    report = {'seed': SEED, 'rows': len(rows), **counts, 'groups': len(groups), 'development_groups': len(development), 'split_method': 'seeded 90/10 source components', 'evaluation': '16 frozen length-eligible internal development rows selected before inference', 'independent_validation': False, 'source': str(source), 'teacher_calls': 0, 'training_started': False}
    (output/'data_freeze.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.input, a.output), ensure_ascii=False))
