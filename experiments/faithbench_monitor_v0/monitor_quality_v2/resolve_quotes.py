"""Resolve quoted text against the visible answer; never use reference labels."""
from copy import deepcopy


def occurrences(text, quote):
    if not isinstance(quote, str) or not quote:
        return []
    positions, start = [], 0
    while (index := text.find(quote, start)) >= 0:
        positions.append((index, index + len(quote)))
        start = index + 1
    return positions


def resolve(answer, prediction):
    proposed, details = deepcopy(prediction), []
    for span in proposed['问题片段']:
        old = deepcopy(span)
        candidates = occurrences(answer, span.get('原文'))
        original = (span.get('起点'), span.get('终点'))
        if len(candidates) == 1:
            selected, status = candidates[0], 'unique_quote'
        elif original in candidates:
            selected, status = original, 'original_consistent'
        else:
            selected, status = None, 'ambiguous_quote' if candidates else 'quote_not_found'
        span['起点'], span['终点'] = selected if selected is not None else (None, None)
        details.append({'status':status, 'original':old, 'candidates':candidates,
                        'resolved':deepcopy(span)})
    complete = all(r['status'] in ('unique_quote','original_consistent') for r in details)
    return {'resolved':complete, 'adoptable_payload':proposed if complete else None,
            'span_resolution':details}
