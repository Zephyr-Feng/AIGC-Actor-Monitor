"""Proposed scoped five-field interface, inactive and not a verdict repair."""
import copy
import json
import re
from typed_source import schema as leaf_schema
from source_scope_candidate_v1 import typed_scopes, resolve_scope


def candidate_schema(data):
    result = copy.deepcopy(leaf_schema(data))
    if data['audit_target'] == 'tool_return':
        scopes = typed_scopes(data)
        if scopes:
            refs = result['properties']['return_reference_ids']
            refs['items']['enum'] = refs['items'].get('enum', []) + list(scopes)
            refs['minItems'] = 1
            refs.pop('maxItems', None)
    return result


def candidate_parse(raw, data):
    """Validate format, namespace and scope; never infer support or absence."""
    value = json.loads(raw)
    contract = candidate_schema(data)['properties']
    if not isinstance(value, dict) or set(value) != set(contract):
        raise ValueError('invalid fields')
    for key in ['audit_target', 'status']:
        if value[key] not in contract[key]['enum']:
            raise ValueError('invalid target or status')
    if not isinstance(value['reason'], str) or not re.search(r'[\u4e00-\u9fff]', value['reason']):
        raise ValueError('reason has no Chinese explanation text')
    for key in ['return_reference_ids', 'capability_reference_ids']:
        ids = value[key]
        allowed = contract[key]['items'].get('enum', [])
        if not isinstance(ids, list) or any(sid not in allowed for sid in ids) or (allowed and not ids):
            raise ValueError('invalid citation scope')
    if data['audit_target'] == 'tool_return':
        scopes = typed_scopes(data)
        for sid in value['return_reference_ids']:
            if sid in scopes:
                resolve_scope(sid, scopes, data['actor_claim_context']['source'], data['decision_step'])
    return value
