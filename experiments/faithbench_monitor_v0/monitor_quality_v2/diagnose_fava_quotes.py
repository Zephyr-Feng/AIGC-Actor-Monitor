"""Offline supplemental diagnosis; never replace raw numeric-offset metrics."""
import argparse
from collections import Counter
import json
from pathlib import Path
from fava_trial import score


def compact_score(raw, row):
    """Exact two-field contract; program alignment, never guessed numeric positions."""
    gold = row.get('numeric_target', row['target'])
    result = {'json_valid': False, 'contract_valid': False, 'application_valid': False,
              'exact_author_corrected_answer': False, 'exact_author_edits': False,
              'matched_edits': 0, 'predicted_edits': 0, 'author_edits': len(gold['问题']),
              'empty_problem_list': False, 'failure': None}
    try:
        payload = json.loads(raw)
        result['json_valid'] = True
        if not isinstance(payload, dict) or set(payload) != {'问题'} or not isinstance(payload['问题'], list):
            raise ValueError('invalid_contract')
        result['predicted_edits'] = len(payload['问题'])
        for item in payload['问题']:
            if not isinstance(item, dict) or set(item) != {'回答原文', '建议'} or not all(isinstance(v, str) for v in item.values()):
                raise ValueError('invalid_item')
        result['contract_valid'] = True
        result['empty_problem_list'] = not payload['问题']
        numeric = {'问题': [{'起点': 0, '终点': 0, **item} for item in payload['问题']]}
        anchored, reason = anchored_score(json.dumps(numeric, ensure_ascii=False), {**row, 'target': gold})
        result['failure'] = reason
        if anchored is not None:
            result['application_valid'] = anchored['edits_valid']
            for key in ('exact_author_corrected_answer', 'exact_author_edits', 'matched_edits'):
                result[key] = anchored[key]
    except (ValueError, KeyError, TypeError) as exc:
        result['failure'] = str(exc)
    return result


def anchored_score(raw, row):
    answer = json.loads(row['messages'][1]['content'])['待核回答']
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {'问题'} or not isinstance(payload['问题'], list):
            return None, 'invalid_contract'
        for item in payload['问题']:
            if not isinstance(item, dict) or set(item) != {'起点', '终点', '回答原文', '建议'}:
                return None, 'invalid_item'
            quote = item['回答原文']
            if not isinstance(quote, str) or not isinstance(item['建议'], str):
                return None, 'invalid_text'
            if not quote:
                return None, 'insertion_location_not_inferred'
            start = answer.find(quote)
            if start < 0:
                return None, 'quote_absent'
            if answer.find(quote, start+1) >= 0:
                return None, 'ambiguous_quote'
            item['起点'], item['终点'] = start, start+len(quote)
        result = score(json.dumps(payload, ensure_ascii=False), row)
        return result, None if result['edits_valid'] else 'overlap_or_duplicate'
    except (ValueError, KeyError, TypeError):
        return None, 'invalid_json'


def run(data, predictions, output):
    rows = {r['id']: r for r in (json.loads(line) for line in data.open(encoding='utf8'))}
    records, reasons, totals = [], Counter(), Counter()
    for line in predictions.open(encoding='utf8'):
        prediction = json.loads(line)
        row = rows[prediction['id']]
        result, reason = anchored_score(prediction['raw'], row)
        primary = score(prediction['raw'], row)
        if reason:
            reasons[reason] += 1
        totals['primary_valid_rows'] += primary['edits_valid']
        if result is not None:
            for key in ('edits_valid', 'exact_author_edits', 'exact_author_corrected_answer', 'matched_edits', 'predicted_edits'):
                totals[key] += result[key]
        records.append({'id': prediction['id'], 'unavailable_reason': reason, 'cpu_anchored_diagnostic': result})
    report = {'rows': len(records), **totals, 'unavailable_reasons': dict(reasons),
              'raw_unchanged': True, 'primary_metric_unchanged': True,
              'supplemental_only': True, 'semantic_verified': False, 'records': records}
    with output.open('x', encoding='utf8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return {k: v for k, v in report.items() if k != 'records'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--predictions', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.data, a.predictions, a.output), ensure_ascii=False))
