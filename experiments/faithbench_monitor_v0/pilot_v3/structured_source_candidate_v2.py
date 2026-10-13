"""Candidate prompt sidecar from complete prior returns, without verdicts.

Reuse inventory facts; do not choose fields based on a claim or model output.
The existing five-field schema and original prompt stay frozen.
"""
import json
from pathlib import Path

from evidence_inventory import source_inventory, field_facts
from evidence_view_candidate_v1 import FIELD_ROLES


def mechanical_facts(data):
    inventory = source_inventory(data)
    inspections = {
        relative: field_facts(inventory, relative)
        for relative in FIELD_ROLES
    }
    for relative, observations in inspections.items():
        for fact, group in zip(observations, inventory['groups'], strict=True):
            parent = relative.rsplit('/', 1)[0]
            fact['parent_field'] = group['fields'].get(parent)
    return {
        'field_roles': FIELD_ROLES.copy(),
        'field_role_contract': (Path(__file__).parent / 'region_field_contract.md').read_text(encoding='utf8'),
        'prior_return_inspections': inspections,
        'structural_positions_are_new_citation_ids': False,
    }


def candidate_prompt(original_prompt, data):
    if data['audit_target'] == 'tool_capability':
        return original_prompt
    return original_prompt + '\n机械字段盘点（完整同源返回的结构事实）：\n' + json.dumps(
        mechanical_facts(data), ensure_ascii=False, sort_keys=True)
