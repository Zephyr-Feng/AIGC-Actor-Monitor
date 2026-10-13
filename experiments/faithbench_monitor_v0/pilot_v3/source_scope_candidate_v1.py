"""Offline candidate reference scopes; no active parser or verdict changes.

Only complete actual returns and actual region lists receive new S IDs.
Original E IDs stay untouched. Scope validity does not imply entailment.
"""
import json
import re

from typed_source import evidence_catalog


def object_at(packet, pointer):
    value = packet
    for part in pointer.strip('/').split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def group_scopes(groups):
    result = {}
    for group in groups:
        source = group['source']
        pointer = group['observation_pointer']
        returned = group['original_return']
        if not re.fullmatch(r'/trajectory/steps/\d+/tool_observation', pointer) or returned.get('tool') != source:
            raise ValueError('invalid actual-return scope')
        containers = [(pointer, returned)]
        regions = returned.get('most_atypical_regions')
        if isinstance(regions, list):
            containers.append((pointer + '/most_atypical_regions', regions))
        for location, value in containers:
            if any(scope['pointer'] == location for scope in result.values()):
                raise ValueError('duplicate scope pointer')
            record = {'source': source, 'returned_after_step': group['returned_after_step'],
                      'pointer': location, 'kind': 'object' if isinstance(value, dict) else 'array',
                      'quote': json.dumps(value, ensure_ascii=False, sort_keys=True)}
            if isinstance(value, dict):
                record['keys'] = list(value)
            else:
                record['length'] = len(value)
            result[f'S{len(result)+1:04d}'] = record
    return result


def typed_scopes(data):
    # Reuse the established same-source/prior-time checks before adding scopes.
    evidence_catalog(data)
    return group_scopes(data['prior_source_returns'])


def packet_scopes(packet):
    groups = []
    for row in packet['runtime_snapshot']['evidence_ledger']:
        returned = object_at(packet, row['observation_ref'])
        if returned != row['observation']:
            raise ValueError('ledger differs from visible packet')
        groups.append({'source': row['source'], 'returned_after_step': row['returned_after_step'],
                       'observation_pointer': row['observation_ref'], 'original_return': returned})
    return group_scopes(groups)


def eligible_scopes(catalog, source, decision_step):
    return {sid: record for sid, record in catalog.items()
            if record['source'] == source and record['returned_after_step'] < decision_step}


def resolve_scope(sid, catalog, source, decision_step):
    allowed = eligible_scopes(catalog, source, decision_step)
    if sid not in allowed:
        raise ValueError('scope from another source, current/future return, or unknown ID')
    return allowed[sid]['quote']


def scope_summary(catalog):
    """Input-side index; source object text already exists in the packet.

    No verdict, selected citations, inferred semantics or generated gold.
    """
    return {sid: {key: value for key, value in record.items() if key != 'quote'}
            for sid, record in catalog.items()}
