"""Cached before/after interface audit; status agreement is not semantic accuracy."""
import argparse
from collections import Counter
import json
from pathlib import Path

from actor_feedback_bridge import read
from feedback_control import prepare
from prepare_feedback_control_run import write


def inspect(source,row,raw):
    try:
        payload=json.loads(raw)
    except ValueError:
        return dict(json_valid=False,interface_status='invalid_json',status_agreement=False if row['reference_status'] else None,
                    semantic_verified=False,payload=None)
    native=row['task']=='native'
    answer=source['answer'] if native else row['quote']
    ranges=[(r['start'],r['end']) for r in source['regions']] if native else [(0,len(answer))]
    p=prepare(answer,source['cards'],payload,controlled=True,allowed_ranges=ranges)
    expected=row['reference_status']
    return dict(json_valid=True,interface_status=p['status'],failure=p.get('failure'),
        status_agreement=payload.get('结论')==expected if expected and isinstance(payload,dict) else None,
        source_anchors_verified=p.get('source_anchors_verified',False),
        routes=[i['route'] for i in p['items']],semantic_verified=False,payload=payload)


def main(root):
    sources={r['id']:r for r in read(root/'inputs.json')}
    dev={r['id']:r for r in read(root/'development.json')}
    phases={}
    for phase in ('before','after'):
        records=[json.loads(s) for s in (root/'run'/(phase+'.jsonl')).read_text(encoding='utf8').splitlines()]
        assert len(records)==len(dev) and {r['id'] for r in records}==set(dev)
        items=[]
        for record in records:
            row=dev[record['id']]
            items.append(dict(id=row['id'],group=row['group'],task=row['task'],expected_status=row['reference_status'],
                hit_limit=record['output_tokens']==768,**inspect(sources[row['group']],row,record['raw'])))
        phases[phase]=dict(items=items,output_statuses=dict(Counter(i['payload'].get('结论') if isinstance(i['payload'],dict) else 'invalid' for i in items)),
            controlled_status_agreement=sum(i['status_agreement'] is True for i in items),
            controlled_denominator=sum(i['expected_status'] is not None for i in items),
            json_valid=sum(i['json_valid'] for i in items),
            interface_statuses=dict(Counter(i['interface_status'] for i in items)),hit_limits=sum(i['hit_limit'] for i in items))
    report=dict(human_gold=False,independent_validation=False,semantic_certified=False,
        warning='status agreement is constructed-label agreement, not semantic correctness; native outputs need source review',phases=phases)
    write(root/'interface_comparison.json',report)
    print(json.dumps({phase:{k:v for k,v in data.items() if k!='items'} for phase,data in phases.items()},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);main(p.parse_args().root)
