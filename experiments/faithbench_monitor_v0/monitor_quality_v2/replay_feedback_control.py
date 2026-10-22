"""Replay the existing 32 cached Chinese outputs, without model calls or labels."""
import argparse
from collections import Counter
import json
from pathlib import Path

from feedback_control import actor_request, prepare


def replay(inputs, predictions, output):
    rows = [json.loads(x) for x in inputs.read_text(encoding='utf8').splitlines()]
    ids = {r['id'] for r in rows}
    cached = {r['id']: r for r in (json.loads(x) for x in predictions.read_text(encoding='utf8').splitlines()) if r['id'] in ids}
    assert len(rows) == len(ids) == len(cached) == 32
    records = []
    for row in rows:
        material = json.loads(row['messages'][1]['content'])
        try:
            payload = json.loads(cached[row['id']]['raw'])
        except ValueError:
            payload = None
        for arm in ('B', 'C'):
            prepared = prepare(material['待核回答'], material['证据卡'], payload, controlled=arm == 'C')
            records.append(dict(id=row['id'], group=row['group'], arm=arm, prepared=prepared,
                                actor_request=actor_request(prepared), actor_called=False))
    report = dict(rows=32, source_groups=len({r['group'] for r in rows}),
                  natural_rows=16, constructed_rows=16, constructed_source_groups=1,
                  status_by_arm={arm: dict(Counter(r['prepared']['status'] for r in records if r['arm'] == arm)) for arm in ('B', 'C')},
                  routes_by_arm={arm: dict(Counter(i['route'] for r in records if r['arm'] == arm for i in r['prepared']['items'])) for arm in ('B', 'C')},
                  model_calls=0, semantic_verified=False, human_gold=False,
                  automatic_claim_mapping=False,
                  limitation='CPU replay verifies routing only. No natural-language claim-to-field mapper or semantic post-edit verifier is available.')
    output.mkdir(parents=True, exist_ok=False)
    (output/'replay.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), encoding='utf8')
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, default=Path('data/fava_next_stage_20261019/regression32.jsonl'))
    parser.add_argument('--predictions', type=Path, default=Path('data/fava_mixed_v1_20261019/run/before00373.jsonl'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.inputs, args.predictions, args.output), ensure_ascii=False))
