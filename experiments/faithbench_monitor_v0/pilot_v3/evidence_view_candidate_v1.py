"""CPU review sidecar; not a model prompt, parser, verdict or label repair.

Reuse the existing inventory and preserve all visible prior-return leaves.
Field descriptions document existing tool roles and never select evidence
for a particular claim. Structures have pointers, not invented citation IDs.
"""
from evidence_inventory import source_inventory, field_facts

FIELD_ROLES = {
    '/scope/num_regions_examined': '检查过的图块总数',
    '/observations/num_atypical_regions': '达到偏离异常阈值的图块数量',
    '/most_atypical_regions': '本次实际列出的区域列表',
    '/observation': '工具返回的观测文本',
    '/score': '工具返回的原始分数',
    '/signal': '工具返回的信号字段',
}


def review_view(data):
    inventory = source_inventory(data)
    groups = []
    for group in inventory['groups']:
        leaves = []
        for relative, field in group['fields'].items():
            if field['kind'] == 'leaf':
                leaves.append({'relative_pointer': relative, **field})
        structures = [
            {'relative_pointer': relative, **field}
            for relative, field in group['fields'].items()
            if field['kind'] != 'leaf'
        ]
        groups.append({
            'source': group['source'],
            'returned_after_step': group['returned_after_step'],
            'observation_pointer': group['observation_pointer'],
            'leaves': leaves,
            'structures': structures,
        })
    return {
        'case_id': inventory['case_id'],
        'atom_id': inventory['atom_id'],
        'claim_text': inventory['claim_text'],
        'decision_step': inventory['decision_step'],
        'field_roles': FIELD_ROLES.copy(),
        'listed_region_field_facts': field_facts(inventory, '/most_atypical_regions'),
        'prior_return_groups': groups,
        'capability_fields': inventory['capability_fields'],
    }
