"""Isolated PEFT runtime and native-template CPU preparation; no model loading."""
import argparse
import json
import random
import struct
import urllib.request
import zipfile
import zlib
from pathlib import Path


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def install_peft(root):
    root.mkdir(parents=True, exist_ok=False)
    with urllib.request.urlopen('https://pypi.org/pypi/peft/0.18.0/json', timeout=30) as response:
        package = json.load(response)
    wheel, = [x for x in package['urls'] if x['filename'].endswith('py3-none-any.whl')]
    source = root / wheel['filename']
    with urllib.request.urlopen(wheel['url'], timeout=60) as response, source.open('xb') as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
    # Read archive metadata and raw deflate payloads without archive verification steps.
    with zipfile.ZipFile(source) as archive, source.open('rb') as stream:
        for info in archive.infolist():
            if info.is_dir() or info.filename.endswith('/RECORD'):
                continue
            destination = (root / info.filename).resolve()
            if not destination.is_relative_to(root.resolve()):
                raise ValueError('package path outside isolated runtime')
            stream.seek(info.header_offset)
            header = stream.read(30)
            name_size, extra_size = struct.unpack_from('<HH', header, 26)
            stream.seek(name_size + extra_size, 1)
            content = stream.read(info.compress_size)
            if info.compress_type == 8:
                content = zlib.decompress(content, -15)
            elif info.compress_type != 0:
                raise ValueError('unsupported compression')
            if len(content) != info.file_size:
                raise ValueError('incomplete package member')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    write(root / 'source.json', {'package': 'peft', 'version': '0.18.0', 'url': wheel['url']})


def tokenize(tokenizer, row):
    messages = row['messages']
    assert row['task'] == 'ragtruth_spans' and row['images'] == []
    assert [x['role'] for x in messages] == ['system', 'user', 'assistant']
    options = dict(tokenize=True, enable_thinking=False, return_dict=False)
    prefix = tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, **options)
    full = tokenizer.apply_chat_template(messages, add_generation_prompt=False, **options)
    if full[:len(prefix)] != prefix or len(full) <= len(prefix):
        raise ValueError('native chat prefix mismatch: ' + row['id'])
    assert len(full) <= 8192, ('sequence exceeds planned context', row['id'], len(full))
    return {'id': row['id'], 'group': row['group'], 'input_ids': full,
            'prefix_length': len(prefix), 'target': json.loads(messages[-1]['content'])}


def preflight(root, base):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    rows = {}
    for split, expected in [('train', 12141), ('validation', 1379)]:
        rows[split] = [json.loads(x) for x in (root / f'{split}.primary.sft.jsonl').read_text(encoding='utf8').splitlines()]
        assert len(rows[split]) == expected
    assert not ({r['group'] for r in rows['train']} & {r['group'] for r in rows['validation']})
    report = {'model_loaded': False, 'truncated': False, 'enable_thinking': False, 'splits': {}}
    for split in rows:
        lengths, answer_lengths = [], []
        with (root / f'{split}.tokens.jsonl').open('x', encoding='utf8') as stream:
            for index, row in enumerate(rows[split], 1):
                packed = tokenize(tokenizer, row)
                stream.write(json.dumps(packed, ensure_ascii=False) + '\n')
                lengths.append(len(packed['input_ids']))
                answer_lengths.append(lengths[-1] - packed['prefix_length'])
                if index % 1000 == 0:
                    print(json.dumps({'event': 'tokenized', 'split': split, 'rows': index}), flush=True)
        ordered = sorted(lengths)
        report['splits'][split] = {'rows': len(lengths), 'total_tokens': sum(lengths),
            'supervised_tokens': sum(answer_lengths), 'max_answer_tokens': max(answer_lengths),
            'p50': ordered[len(ordered)//2], 'p95': ordered[int(len(ordered)*.95)], 'max': max(ordered)}
    # Balanced development check, one response per source group; test split stays unopened.
    candidates = rows['validation'].copy()
    random.Random(20261016).shuffle(candidates)
    selected, groups, counts = [], set(), {False: 0, True: 0}
    for row in candidates:
        error = bool(json.loads(row['messages'][-1]['content'])['问题片段'])
        if counts[error] < 32 and row['group'] not in groups:
            selected.append(row['id']); groups.add(row['group']); counts[error] += 1
    assert len(selected) == 64
    write(root / 'development_ids.json', selected)
    write(root / 'preflight.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--install-peft', action='store_true')
    args = parser.parse_args()
    if args.install_peft:
        install_peft(args.root / 'vendor')
    else:
        preflight(args.root, args.base)
