"""Recompute raw-result metrics on CPU, preserving the original scoring."""
from collections import Counter
import json
import math
from pathlib import Path

from assemble_feedback import assemble
from diagnose_fava_quotes import anchored_score
from fava_trial import readl, score, write
from prepare_fava_next import OUT


def main():
    rows = readl(OUT/'evaluation.tokens.jsonl')
    lookup = {r['id']: r for r in rows}
    reference_path = Path('data/monitor_public_v1_20261016/feedback_training_v1_20261017/before.metrics.json')
    reference = {r['id']: r['reference_conclusion'] for r in json.loads(reference_path.read_text(encoding='utf8'))['details']}
    summaries, phases = {}, {}
    for phase in ('old00952', 'current00373'):
        predictions = readl(OUT/'run'/f'{phase}.jsonl')
        assert len({p['id'] for p in predictions}) == len(predictions)
        assert [p['id'] for p in predictions] == [r['id'] for r in rows[:len(predictions)]]
        phases[phase] = {p['id']: p for p in predictions}
        totals = {cohort: Counter() for cohort in dict.fromkeys(r['cohort'] for r in rows)}
        failures = Counter()
        for p in predictions:
            row = lookup[p['id']]
            count = totals[row['cohort']]
            count['rows'] += 1
            count['hit_token_cap'] += p['hit_token_cap']
            if row['task'] == 'fava':
                assert math.isfinite(p['loss'])
                strict = score(p['raw'], row)
                anchored, reason = anchored_score(p['raw'], row)
                assert strict == p['strict'] and anchored == p['anchored'] and reason == p['anchor_failure']
                for key in ('json_valid', 'edits_valid', 'exact_author_corrected_answer', 'exact_author_edits', 'matched_edits', 'predicted_edits', 'author_edits'):
                    count['strict_'+key] += strict[key]
                if reason:
                    failures[row['cohort']+':'+reason] += 1
                if anchored is not None:
                    for key in ('edits_valid', 'exact_author_corrected_answer', 'exact_author_edits', 'matched_edits', 'predicted_edits'):
                        count['anchored_'+key] += anchored[key]
                payload = None
                try:
                    payload = json.loads(p['raw'])
                except ValueError:
                    pass
                if isinstance(payload, dict) and isinstance(payload.get('问题'), list):
                    count['nonempty_problem_list'] += bool(payload['问题'])
                    count['empty_problem_list'] += not payload['问题']
                if p['loss'] is not None:
                    count['loss_sum'] += p['loss']
            else:
                material = json.loads(row['messages'][1]['content'])
                try:
                    payload = json.loads(p['raw'])
                    count['json_valid'] += 1
                    checked = assemble(material['待核回答'], material['证据卡'], payload)
                    valid, conclusion = checked['source_anchors_verified'], payload['结论']
                except (ValueError, KeyError, TypeError, IndexError):
                    valid, conclusion = False, None
                assert valid == p['source_anchors_valid'] and conclusion == p['conclusion']
                count['contract_anchors_valid'] += valid
                count['reference_label_match_with_valid_contract'] += valid and conclusion == reference[row['id']]
                count['conclusion_'+str(conclusion)] += 1
        summaries[phase] = {'cohorts': {key: dict(value) for key, value in totals.items()},
                            'anchor_failures': dict(failures), 'rows': len(predictions)}
    transitions = {}
    semantic_queue = []
    for row in rows:
        a, b = (phases[p].get(row['id']) for p in ('old00952', 'current00373'))
        if a is None or b is None:
            continue
        if row['task'] == 'fava':
            state_a = bool(a['anchored'] and a['anchored']['exact_author_corrected_answer'])
            state_b = bool(b['anchored'] and b['anchored']['exact_author_corrected_answer'])
        else:
            state_a = (a['source_anchors_valid'], a['conclusion'])
            state_b = (b['source_anchors_valid'], b['conclusion'])
        key = row['cohort']
        transitions.setdefault(key, Counter())[str(state_a)+' -> '+str(state_b)] += 1
        if row['cohort'] in ('clean7', 'regression_control16') or state_a != state_b:
            semantic_queue.append({'id': row['id'], 'cohort': key, 'reason': 'control_or_changed_outcome',
                                   'human_gold': False})
    report = {'summaries': summaries, 'paired_transitions': {k: dict(v) for k, v in transitions.items()},
              'paired_rows': len(set(phases['old00952']) & set(phases['current00373'])), 'cpu_rescore_equal': True,
              'all_complete': all(summaries[p]['rows'] == len(rows) for p in summaries),
              'semantic_review_queue': semantic_queue, 'semantic_queue_rows': len(semantic_queue),
              'limits': 'internal development, synthetic author matching and source-anchor existence are not semantic accuracy; controls share sources',
              'training_started': False}
    write(OUT/'comparison.cpu.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('semantic_review_queue',)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
