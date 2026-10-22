"""Prepare evidence packets and quote-resolution sidecars from saved outputs."""
import argparse
from collections import Counter
import json
from pathlib import Path

from resolve_quotes import resolve


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]


def run(data, output):
    output.mkdir(parents=True,exist_ok=False)
    validation={r['id']:r for r in rows(data/'built_v3/validation.primary.sft.jsonl')}
    after=rows(data/'training_v1/completed_20261017/after.jsonl')
    assert len(after)==len({r['id'] for r in after})==64
    counts=Counter()
    with (output/'review_packets.jsonl').open('x',encoding='utf8') as packets, (output/'quote_resolution.jsonl').open('x',encoding='utf8') as resolutions:
        for item in after:
            original=validation[item['id']]
            material=json.loads(original['messages'][1]['content'])['材料']
            prediction=json.loads(item['raw'])
            reference=json.loads(original['messages'][-1]['content'])
            fixed=resolve(material['待核回答'],prediction)
            counts.update(r['status'] for r in fixed['span_resolution'])
            counts['fully_resolved_rows']+=fixed['resolved']
            counts['nonempty_rows']+=bool(prediction['问题片段'])
            counts['fully_resolved_nonempty_rows']+=fixed['resolved'] and bool(prediction['问题片段'])
            packet={'id':item['id'],'group':original['group'],'source':material['原始资料'],
                'answer':material['待核回答'],'author_reference':reference,
                'prediction':prediction,'status_matches_author':item['status_correct'],
                'raw':item['raw'],'review_status':'not_reviewed'}
            packets.write(json.dumps(packet,ensure_ascii=False)+'\n')
            resolutions.write(json.dumps({'id':item['id'],**fixed},ensure_ascii=False)+'\n')
    report={'rows':64,'new_model_calls':0,'uses_gold_for_resolution':False,'counts':dict(counts),
        'raw_modified':False,'semantic_review_completed':False,'independent_test':False}
    (output/'preparation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.data,args.output)
