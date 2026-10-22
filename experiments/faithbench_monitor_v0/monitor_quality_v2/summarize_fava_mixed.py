"""CPU scoring and exact coverage audit of the approved mixed trial."""
from collections import Counter
import json
import math
from pathlib import Path

from assemble_feedback import assemble
from diagnose_fava_quotes import compact_score
from fava_trial import readl, write

ROOT = Path('data/fava_mixed_v1_20261019')


def main():
    rows = readl(ROOT/'evaluation.tokens.jsonl')
    lookup = {r['id']: r for r in rows}
    ref_file = Path('data/monitor_public_v1_20261016/feedback_training_v1_20261017/before.metrics.json')
    refs = {r['id']: r['reference_conclusion'] for r in json.loads(ref_file.read_text(encoding='utf8'))['details']}
    phases, summaries = {}, {}
    for phase in ('before00373', 'after_mixed'):
        path = ROOT/'run'/(phase+'.jsonl')
        if not path.exists():
            continue
        predictions = readl(path)
        assert [r['id'] for r in predictions] == [r['id'] for r in rows[:len(predictions)]]
        assert len({r['id'] for r in predictions}) == len(predictions)
        phases[phase] = {r['id']: r for r in predictions}
        totals, failures = {}, Counter()
        for p in predictions:
            row = lookup[p['id']]
            count = totals.setdefault(row['cohort'], Counter())
            count['rows'] += 1
            count['hit_token_cap'] += p['hit_token_cap']
            if row['task'] == 'fava':
                recalculated = compact_score(p['raw'], row)
                assert recalculated == p['compact']
                assert math.isfinite(p['loss'])
                count['loss_sum'] += p['loss']
                for key in ('json_valid', 'contract_valid', 'application_valid', 'exact_author_corrected_answer',
                            'exact_author_edits', 'matched_edits', 'predicted_edits', 'author_edits', 'empty_problem_list'):
                    count[key] += recalculated[key]
                if recalculated['failure']:
                    failures[row['cohort']+':'+recalculated['failure']] += 1
            else:
                m = json.loads(row['messages'][1]['content'])
                try:
                    payload = json.loads(p['raw'])
                    count['json_valid'] += 1
                    checked = assemble(m['待核回答'], m['证据卡'], payload)
                    valid, conclusion = checked['source_anchors_verified'], payload['结论']
                except (ValueError, KeyError, TypeError, IndexError):
                    valid, conclusion = False, None
                assert valid == p['source_anchors_valid'] and conclusion == p['conclusion']
                count['contract_anchors_valid'] += valid
                count['valid_contract_reference_label_match'] += valid and conclusion == refs[row['id']]
                count['conclusion_'+str(conclusion)] += 1
        summaries[phase] = {'rows': len(predictions), 'complete': len(predictions) == len(rows),
                            'cohorts': {k: dict(v) for k, v in totals.items()}, 'failures': dict(failures)}
    paired = {}
    if len(phases) == 2:
        for row in rows:
            a, b = (phases[p].get(row['id']) for p in ('before00373', 'after_mixed'))
            if a is None or b is None:
                continue
            if row['task'] == 'fava':
                x, y = (p['compact']['exact_author_corrected_answer'] for p in (a, b))
            else:
                x, y = ((p['source_anchors_valid'], p['conclusion']) for p in (a, b))
            paired.setdefault(row['cohort'], Counter())[str(x)+' -> '+str(y)] += 1
    coverage = None
    training_file = ROOT/'run/training.jsonl'
    if training_file.exists():
        train = readl(ROOT/'train.tokens.jsonl')
        index = {r['id']: r for r in train}
        order = json.loads((ROOT/'run/sample_order.json').read_text(encoding='utf8'))
        assert len(order) == len(index) == len(train) and set(order) == set(index)
        logs = readl(training_file)
        ids = [i for r in logs for i in r['ids']]
        assert [r['update'] for r in logs] == list(range(1, len(logs)+1))
        assert len(ids) == len(set(ids)) and ids == order[:len(ids)]
        tokens = sum(len(index[i]['input_ids']) for i in ids)
        supervised = sum(len(index[i]['input_ids'])-index[i]['prefix_length'] for i in ids)
        tasks = dict(Counter(index[i]['task'] for i in ids))
        if logs:
            assert logs[-1]['samples'] == len(ids) and logs[-1]['seen_tokens'] == tokens
            assert logs[-1]['supervised_tokens_seen'] == supervised and logs[-1]['task_seen'] == tasks
        coverage = {'updates': len(logs), 'unique_samples': len(ids), 'available_samples': len(train),
                    'exact_frozen_order_prefix': True, 'seen_tokens': tokens, 'supervised_tokens': supervised,
                    'tasks': tasks, 'epoch_complete': len(ids) == len(train)}
    report = {'summaries': summaries, 'paired_transitions': {k: dict(v) for k, v in paired.items()},
              'training_coverage': coverage, 'cpu_rescore_equal': True,
              'complete': len(summaries) == 2 and all(v['complete'] for v in summaries.values()),
              'limits': 'joint intervention; exposed development, source-label matching is not semantic accuracy'}
    name = 'comparison.cpu.json' if len(phases) == 2 else 'baseline.cpu.json'
    write(ROOT/name, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
