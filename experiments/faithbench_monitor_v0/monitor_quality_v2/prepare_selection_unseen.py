"""Freeze three existing, interface-unseen image development sources; no GT."""
from copy import deepcopy
import json
from pathlib import Path

from prepare_feedback_control_run import write
from typed_feedback import apply_verified

IDS = ('case_001', 'case_002', 'case_003')


def explanations(action):
    fields = [('action_reason',)] + [('current_evidence', i, 'interpretation') for i in range(len(action['current_evidence']))] + [('evidence_gap',)]
    answer, regions = '', []
    for path in fields:
        value = action
        for part in path:
            value = value[part]
        answer += '\n['+'/'.join(map(str, path))+']\n'; start = len(answer); answer += value
        if value:
            regions.append(dict(path=list(path), start=start, end=len(answer)))
    return answer, regions


def make(repo, root, ids=IDS):
    source = repo/'experiments/faithbench_monitor_v0/private/natural_actor_monitor_20261013'
    old = json.loads((repo/'data/feedback_control_v1_20261020/inputs.json').read_text(encoding='utf8'))
    policy = next(c['value'] for r in old if r['id'] == 'case_005' for c in r['cards'] if c['path'] == ['review_contract'])
    system = next(r['monitor_system'] for r in old if r['kind'] == 'text_proxy')
    tools = json.loads((source/'tool_cards.json').read_text(encoding='utf8'))
    rows = []
    for cid in ids:
        record = json.loads((source/'actor_backup/output/records'/f'{cid}.json').read_text(encoding='utf8'))
        assert not {'gt', 'ground_truth', 'gold_label', 'label'} & set(record)
        assert record['raw_parse_valid'] is True
        assert record['call_budget_used'] == record['num_tool_calls'] == len(record['tool_calls'])
        original = json.loads(record['raw_terminal_text']); normalized = deepcopy(original)
        cards = [dict(id='E001', path=['tool_cards'], value=tools), dict(id='E002', path=['review_contract'], value=policy)]
        images = [record['relative_path']]
        for step in record['steps']:
            value = step.get('tool_observation')
            if not isinstance(value, dict):
                continue
            assert value['tool'] in record['tool_calls']
            cards.append(dict(id=f'E{len(cards)+1:03}', path=['observed_tool_return'], value=value))
            images.extend(x['crop_path'] for x in value.get('most_atypical_regions', []))
        returns = {c['value']['tool']: c for c in cards if isinstance(c['value'], dict) and 'tool' in c['value']}
        assert set(returns) == set(record['tool_calls']) and len(returns) == len(cards)-2
        repairs = []
        for i in range(len(normalized['current_evidence'])):
            item = normalized['current_evidence'][i]
            if item['source'] not in returns:
                continue
            card = returns[item['source']]
            item['observation'] = f'原始工具返回见证据{card["id"]}，由程序绑定。'
            if item['source'] == 'global_forensic_analyzer':
                proposal = dict(rule='global_direction', evidence_id=card['id'], actor_index=i,
                                observed=item['direction'], proposed='inconclusive')
                result = apply_verified(normalized, cards, proposal)
                if result['verification']['status'] == 'verified_repair':
                    repairs.append(result['verification']); normalized = result['candidate_action']
        for key in ('final_verdict', 'final_confidence', 'next_action', 'selected_tool', 'unresolved_conflicts'):
            assert original[key] == normalized[key]
        images = list(dict.fromkeys(images))
        assert all(p.startswith('assets/'+cid) and '..' not in p for p in images)
        cards.append(dict(id=f'E{len(cards)+1:03}', path=['task_state'], value={
            'max_tool_calls':4, 'used_tools':record['tool_calls'], 'remaining_calls':4-len(record['tool_calls']),
            'new_tool_calls':0, 'tool_returns':'仅当时已调用工具的完整返回，无未来工具结果',
            'editable':'action_reason、interpretation、evidence_gap', 'protected':'最终真假、置信度、direction和动作'}))
        answer, regions = explanations(normalized)
        prefix = [{'role': 'system', 'content': '固定Actor的来源核对任务'},
                  {'role': 'user', 'content': [{'type': 'image', 'image': p} for p in images]}]
        rows.append(dict(id=cid, group=cid, kind='image_development', cards=cards, answer=answer,
            regions=regions, original_action=normalized, historical_original_action=original,
            rule_repairs=repairs, prefix=prefix, monitor_system=system,
            feedback=None, arm_order=['P'], normalization='tool observations bound to original evidence IDs; no model-written summaries'))
    root.mkdir(exist_ok=False)
    write(root/'inputs.json', rows)
    write(root/'authorization.json', dict(approved=True, frozen_ids=list(ids), monitor_generations=len(ids), actor_generations='conditional per valid issue, no retries',
        training_updates=0, teacher_api_calls=0, new_tool_calls=0, budget_limits=None,
        source='existing natural30 cached development; explicitly frozen IDs, not independent human gold',
        source_groups_verified=False, independent_human_gold=False))
    print(json.dumps({'rows': len(rows), 'normalization_repairs': {r['id']: len(r['rule_repairs']) for r in rows},
                      'image_paths': {r['id']: [p['image'] for p in r['prefix'][1]['content']] for r in rows}}, ensure_ascii=False))


if __name__ == '__main__':
    make(Path(__file__).resolve().parents[3], Path('data/feedback_selection_unseen_v1_20261020'))
