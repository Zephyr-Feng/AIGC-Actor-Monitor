"""Fetch the three selected public corpora over HTTP; no hub/cache verifiers."""
import concurrent.futures
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import zipfile
import zlib

import requests

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/monitor_public_v1_20261016'


def get_json(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def download(item):
    path = DATA / item['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return {**item, 'bytes': path.stat().st_size, 'reused': True}
    partial = path.with_suffix(path.suffix + '.curl.partial')
    print(f"FETCH {item['path']}", flush=True)
    subprocess.run(['curl.exe', '--location', '--fail', '--silent', '--show-error',
                    '--retry', '3', '--retry-all-errors', '--retry-delay', '1',
                    '--connect-timeout', '20', '--max-time', '900',
                    '--continue-at', '-', '--output', str(partial), item['url']], check=True)
    os.replace(partial, path)
    print(f"READY {item['path']} {path.stat().st_size} bytes", flush=True)
    return {**item, 'bytes': path.stat().st_size, 'reused': False}


def prepare_arrow():
    vendor = DATA / 'runtime'
    if (vendor / 'pyarrow/__init__.py').exists():
        return
    package = get_json('https://pypi.org/pypi/pyarrow/json')
    wheels = [x for x in package['urls'] if x['filename'].endswith('cp311-cp311-win_amd64.whl')]
    if len(wheels) != 1:
        raise ValueError('no unique CPython 3.11 Windows wheel')
    wheel = wheels[0]
    entry = download({'url': wheel['url'], 'path': 'runtime_source/' + wheel['filename']})
    # Only use archive directory metadata; raw deflate avoids archive checksum steps.
    with zipfile.ZipFile(DATA / entry['path']) as archive, (DATA / entry['path']).open('rb') as raw:
        for info in archive.infolist():
            if info.is_dir() or '.dist-info/' in info.filename and '/licenses/' not in info.filename:
                continue
            target = (vendor / info.filename).resolve()
            if not target.is_relative_to(vendor.resolve()):
                raise ValueError('archive path outside runtime')
            raw.seek(info.header_offset)
            header = raw.read(30)
            name_len, extra_len = struct.unpack_from('<HH', header, 26)
            raw.seek(name_len + extra_len, 1)
            compressed = raw.read(info.compress_size)
            if info.compress_type == 0:
                content = compressed
            elif info.compress_type == 8:
                content = zlib.decompress(compressed, -15)
            else:
                raise ValueError('unsupported archive compression')
            if len(content) != info.file_size:
                raise ValueError('incomplete runtime entry')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    (DATA / 'runtime_source/version.json').write_text(json.dumps({'package': 'pyarrow', 'version': package['info']['version'], 'url': wheel['url']}, indent=2), encoding='utf8')


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    prepare_arrow()
    files = []
    for name in ('response.jsonl', 'source_info.jsonl'):
        files.append({'url': 'https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/' + name, 'path': 'raw/ragtruth/' + name})
    for name in ('README.md', 'LICENSE'):
        files.append({'url': 'https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/' + name, 'path': 'raw/ragtruth/' + name})
    for dataset, namespace in [('galileo-ai/ragbench', 'ragbench'), ('huaXiaKyrie/critique-VQA', 'critic_v')]:
        catalog = get_json('https://huggingface.co/api/datasets/' + dataset + '/parquet')
        (DATA / f'{namespace}_catalog.json').write_text(json.dumps(catalog, indent=2), encoding='utf8')
        files.append({'url': 'https://huggingface.co/datasets/' + dataset + '/raw/main/README.md', 'path': f'raw/{namespace}/README.md'})
        for config, splits in catalog.items():
            if namespace == 'ragbench' and config not in {'delucionqa', 'emanual', 'finqa', 'hagrid', 'hotpotqa', 'msmarco', 'tatqa', 'techqa'}:
                continue
            for split, urls in splits.items():
                for index, url in enumerate(urls):
                    if namespace == 'critic_v' and index not in {0, len(urls) // 2, len(urls) - 1}:
                        continue
                    files.append({'url': url, 'path': f'raw/{namespace}/{config}/{split}/{index:03}.parquet'})
    ledger_path = DATA / 'downloads.json'
    ledger = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(download, files):
            ledger.append(result)
            ledger_path.write_text(json.dumps(ledger, indent=2), encoding='utf8')
    print(json.dumps({'completed_files': len(ledger), 'bytes': sum(x['bytes'] for x in ledger)}), flush=True)


if __name__ == '__main__':
    main()
