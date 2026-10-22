"""Compare frozen feedback contracts and controls; leave semantics to content review."""
import argparse
import json
from pathlib import Path

from assemble_feedback import assemble
from prepare_feedback_control_run import write


def records(path):
    return [json.loads(s) for s in path.read_text(encoding='utf8').splitlines()]


def check(row, output):
    material = json.loads(row['messages'][1]['content'])
    try:
        payload = json.loads(output['raw'])
        assemble(material['待核回答'], material['证据卡'], payload)
        valid, failure = True, None
    except (ValueError, KeyError, TypeError) as exc:
        payload = None; valid, failure = False, str(exc)
    return dict(id=row['id'], source_id=row['source_id'], condition=row['condition'],
                contract_valid=valid, failure=failure, status=payload['结论'] if payload else None,
                control_status_match=(payload['结论']==row['expected_status']) if payload and row['expected_status'] else None,
                hit_output_cap=output['output_tokens']>=768, output_tokens=output['output_tokens'],
                raw=output['raw'], semantic_certified=False)


def main(root):
    rows = json.loads((root/'evaluation.json').read_text(encoding='utf8'))
    old = Path('data/adviser_test_100_v1_20261021')
    frozen = {r['id']:r for r in json.loads((old/'monitor_inputs.json').read_text(encoding='utf8'))}
    for row in rows:
        assert row['messages'] == frozen[row['id']]['messages'], 'baseline message mismatch'
    arms = {}
    for name, path in [('current00373',old/'old00373/monitor_outputs.jsonl'),
                       ('unknown_candidate00012',old/'candidate00012/monitor_outputs.jsonl'),
                       ('new_candidate',root/'evaluation/monitor_outputs.jsonl')]:
        source = records(path)
        assert len(source)==len({r['id'] for r in source})
        if name=='new_candidate':
            assert [r['id'] for r in source] == [r['id'] for r in rows], 'incomplete or changed evaluation'
        arms[name] = [check(row,next(r for r in source if r['id']==row['id'])) for row in rows]
    regressions = []
    for index, row in enumerate(rows):
        new = arms['new_candidate'][index]
        for name in ('current00373','unknown_candidate00012'):
            baseline = arms[name][index]
            if baseline['contract_valid'] and not new['contract_valid']:
                regressions.append(dict(id=row['id'], baseline=name, kind='contract'))
            if baseline['control_status_match'] is True and new['control_status_match'] is not True:
                regressions.append(dict(id=row['id'], baseline=name, kind='control_status'))
    summary = {name:dict(n=len(results), valid=sum(r['contract_valid'] for r in results),
                       control_matches=sum(r['control_status_match'] is True for r in results),
                       cap_hits=sum(r['hit_output_cap'] for r in results)) for name,results in arms.items()}
    write(root/'quick_comparison.cpu.json',dict(summary=summary, arms=arms,
          mechanical_regressions=regressions, semantic_review_required=True, promoted=False))
    print(json.dumps(dict(summary=summary,mechanical_regressions=regressions),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
