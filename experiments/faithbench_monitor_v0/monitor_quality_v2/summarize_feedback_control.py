"""Summarize interface behavior and build evidence packets, without semantic scores."""
import argparse
from collections import Counter
import json
from pathlib import Path


def summarize(root):
    inputs = json.loads((root/'inputs.json').read_text(encoding='utf8'))
    outputs = [json.loads(x) for x in (root/'actor_outputs.jsonl').read_text(encoding='utf8').splitlines()]
    expected = {(r['id'], a) for r in inputs for a in ('B', 'C')}
    assert len(outputs) == len(expected) == 72 and {(r['id'], r['arm']) for r in outputs} == expected
    monitor = [json.loads(x) for x in (root/'monitor_outputs.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(monitor) == 4
    metrics = {}
    for kind in ('text_proxy', 'image_development'):
        metrics[kind] = {}
        for arm in ('B', 'C'):
            rows = [r for r in outputs if r['kind'] == kind and r['arm'] == arm]
            decisions = [x for r in rows for x in r['result']['records']]
            metrics[kind][arm] = dict(rows=len(rows), source_groups=len({r['group'] for r in rows}),
                actor_calls=sum(r['actor_called'] for r in rows),
                status=dict(Counter(r['result']['status'] for r in rows)),
                decisions=dict(Counter(x['decision'] or x['route'] for x in decisions)),
                applied_items=sum(x['applied'] for x in decisions),
                changed_answers=sum(r['result']['answer'] != r['prepared']['answer'] for r in rows),
                output_limit_hits=sum(r['output_tokens'] == 768 for r in rows),
                input_tokens=sum(r['input_tokens'] for r in rows), output_tokens=sum(r['output_tokens'] for r in rows))
    report = dict(interface=metrics, monitor_calls=4, actor_calls=sum(r['actor_called'] for r in outputs),
                  total_generations=4+sum(r['actor_called'] for r in outputs),
                  monitor_output_limit_hits=sum(r['output_tokens'] == 1024 for r in monitor),
                  semantic_accuracy=None, human_gold=False, independent_validation=False,
                  training_updates=0, teacher_api_calls=0, new_tool_calls=0)
    packets = []
    for row in inputs:
        arms = {r['arm']: r for r in outputs if r['id'] == row['id']}
        packets.append(dict(id=row['id'], group=row['group'], kind=row['kind'], cards=row['cards'],
            original=row['answer'], arms={a: dict(feedback=r['prepared'].get('feedback'),
                feedback_failure=r['prepared'].get('failure'), raw=r['raw'], result=r['result']) for a, r in arms.items()},
            review=dict(monitor_item_judgments=[], original_errors=[], new_errors=[], supported_content_losses=[], unresolved=[],
                        reviewer='pending', human_gold=False, condition_blinded=False)))
    with (root/'interface_summary.json').open('x', encoding='utf8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    with (root/'review_packets.jsonl').open('x', encoding='utf8') as stream:
        stream.write(''.join(json.dumps(p, ensure_ascii=False)+'\n' for p in packets))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.root), ensure_ascii=False))
