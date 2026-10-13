"""Offline source inventory. Facts and literal candidates, never a verdict.

This candidate does not alter prompts, labels, responses or frozen parsers.
Literal absence is not semantic absence; a literal match is not entailment.
"""
import re
from typed_source import evidence_catalog


def _escape(key):
    return str(key).replace('~', '~0').replace('/', '~1')


def _walk(value, pointer=''):
    yield pointer, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, pointer + '/' + _escape(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, pointer + '/' + str(index))


def source_inventory(data):
    """Preserve every prior-return field and its original citation namespace."""
    catalog = evidence_catalog(data)
    groups = []
    for group in data['prior_source_returns']:
        fields = {}
        for relative, value in _walk(group['original_return']):
            field = {'pointer': group['observation_pointer'] + relative,
                     'reference_id': group['field_references'].get(relative)}
            if isinstance(value, dict):
                field.update(kind='object', keys=list(value))
            elif isinstance(value, list):
                field.update(kind='array', length=len(value))
            else:
                field.update(kind='leaf', value=value)
            fields[relative] = field
        groups.append({'source': group['source'],
                       'returned_after_step': group['returned_after_step'],
                       'observation_pointer': group['observation_pointer'],
                       'fields': fields})
    return {'case_id': data['case_id'], 'atom_id': data['atom_id'],
            'claim_text': data['text'], 'decision_step': data['decision_step'],
            'source': data['actor_claim_context']['source'], 'groups': groups,
            'capability_fields': catalog['tool_capability'],
            'semantic_verdict': None}


def field_facts(inventory, relative_pointer):
    """Inspect a requested JSON pointer; missing, null and empty stay distinct.

    Choosing which field a claim requires is outside this function. A missing
    field in an earlier return also cannot erase a field in another return.
    """
    if relative_pointer and not relative_pointer.startswith('/'):
        raise ValueError('expected relative JSON pointer')
    facts = []
    for group in inventory['groups']:
        field = group['fields'].get(relative_pointer)
        facts.append({'observation_pointer': group['observation_pointer'],
                      'returned_after_step': group['returned_after_step'],
                      'present': field is not None, 'field': field})
    return facts


def literal_candidates(inventory, text=None):
    """Find exact string containment ignoring whitespace, in actual returns.

    No joins between fields, tool-name inference, rounding or paraphrase rules.
    These are review candidates only; no match cannot prove not_returned.
    """
    text = inventory['claim_text'] if text is None else text
    fragment = re.sub(r'\s+', '', text)
    if not fragment:
        return []
    matches = []
    for group in inventory['groups']:
        for field in group['fields'].values():
            value = field.get('value')
            if isinstance(value, str) and fragment in re.sub(r'\s+', '', value):
                matches.append({'pointer': field['pointer'],
                                'reference_id': field['reference_id'],
                                'quote': value})
    return matches


def omitted_literal_candidates(inventory, selected_reference_ids):
    """Expose unused visible text candidates without declaring model error."""
    selected = set(selected_reference_ids)
    return [field for field in literal_candidates(inventory)
            if field['reference_id'] not in selected]
