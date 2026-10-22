"""Freeze existing development inputs for a single feedback-control run."""
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil

from feedback_control import prepare


CASES = ('case_005', 'case_016', 'case_017', 'case_028')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def project(action):
    text, regions = '', []
    fields = [('action_reason',)]
    for i, item in enumerate(action['current_evidence']):
        fields.extend([('current_evidence', i, 'observation'), ('current_evidence', i, 'interpretation')])
    fields.append(('evidence_gap',))
    for path in fields:
        value = action
        for key in path:
            value = value[key]
        assert isinstance(value, str)
        text += '\n[' + '/'.join(map(str, path)) + ']\n'
        start = len(text)
        text += value
        if value:
            regions.append(dict(path=list(path), start=start, end=len(text)))
    return text, regions


def apply_to_action(original, regions, edits):
    assert all(sum(r['start'] <= e['start'] < e['end'] <= r['end'] for r in regions) == 1 for e in edits)
    action = deepcopy(original)
    for region in regions:
        selected = [e for e in edits if region['start'] <= e['start'] < e['end'] <= region['end']]
        target = action
        for key in region['path'][:-1]:
            target = target[key]
        key = region['path'][-1]
        value = target[key]
        for edit in sorted(selected, key=lambda e: e['start'], reverse=True):
            a, b = edit['start']-region['start'], edit['end']-region['start']
            value = value[:a] + edit['replacement'] + value[b:]
        target[key] = value
    return action


def main():
    repo = Path(__file__).resolve().parents[3]
    root = repo/'data/feedback_control_v1_20261020'
    assert (root/'cpu_replay/summary.json').is_file()
    assert not (root/'inputs.json').exists()
    d2root = repo/'experiments/faithbench_monitor_v0/private/mechanism_d2_20261013'
    old = read(d2root/'inputs.json')
    regression = [json.loads(x) for x in (repo/'data/fava_next_stage_20261019/regression32.jsonl').read_text(encoding='utf8').splitlines()]
    cached = {r['id']: r for r in (json.loads(x) for x in (repo/'data/fava_mixed_v1_20261019/run/before00373.jsonl').read_text(encoding='utf8').splitlines())}
    rows = []
    for row in regression:
        material = json.loads(row['messages'][1]['content'])
        try:
            feedback = json.loads(cached[row['id']]['raw'])
        except ValueError:
            feedback = None
        rows.append(dict(id=row['id'], group=row['group'], kind='text_proxy', answer=material['待核回答'],
                         cards=material['证据卡'], feedback=feedback, prefix=None, regions=None,
                         monitor_system=row['messages'][0]['content']))
    system = regression[0]['messages'][0]['content']
    for cid in CASES:
        case = old['cases'][cid]
        action = json.loads(case['original_raw'])
        answer, regions = project(action)
        cards = []
        def card(location, value):
            cards.append(dict(id=f'E{len(cards)+1:03}', path=[location], value=value))
        first_text = next(p['text'] for p in case['prefix'][1]['content'] if p.get('type') == 'text')
        tools, _ = json.JSONDecoder().raw_decode(first_text.split('工具定义：\n', 1)[1])
        card('tool_cards', tools)
        card('review_contract', old['review_contract'])
        for message in case['prefix'][2:]:
            if message['role'] != 'user' or not isinstance(message['content'], list):
                continue
            for part in message['content']:
                if part.get('type') == 'text' and '工具真实返回：\n' in part['text']:
                    returned, _ = json.JSONDecoder().raw_decode(part['text'].split('工具真实返回：\n', 1)[1])
                    card('observed_tool_return', returned)
        assert len(cards) == len(case['used_tools'])+2, cid
        card('revision_scope', {'remaining_calls': case['remaining'], 'new_tool_calls': 0,
             'scope': '只审核已列出的解释和证据摘要。真假标签、置信度、direction和动作不在可修改范围。没有像素时不判视觉真相。'})
        rows.append(dict(id=cid, group=cid, kind='image_development', answer=answer, cards=cards,
                         feedback=None, prefix=case['prefix'], regions=regions, original_action=action,
                         monitor_system=system, original_raw=case['original_raw']))
    rng = random.Random(20261020)
    rng.shuffle(rows)
    for row in rows:
        row['arm_order'] = ['B', 'C']; rng.shuffle(row['arm_order'])
    assert len(rows) == 36 and len({r['id'] for r in rows}) == 36
    write(root/'inputs.json', rows)
    (root/'assets').mkdir()
    for name in old['assets']:
        source = d2root/name
        target = root/name
        assert source.is_file() and target.parent == root/'assets'
        shutil.copyfile(source, target)
    text_calls = sum(prepare(r['answer'], r['cards'], r['feedback'], controlled=arm == 'C')['status'] == 'ready'
                     for r in rows if r['kind'] == 'text_proxy' for arm in ('B', 'C'))
    write(root/'authorization.json', dict(approved=True, user_instruction='2026-10-20：按照上述方案做；预算回复：不设上限。',
        ssh_host='connect.bjb2.seetacloud.com', ssh_port=46101, budget_limits=None,
        training_updates=0, new_tool_calls=0, teacher_api_calls=0,
        planned_monitor_generations=4, planned_text_actor_generations=text_calls,
        maximum_visual_actor_generations=8, maximum_planned_generations=4+text_calls+8,
        actor='Qwen3-VL-8B-Instruct', actor_revision=old['model_spec']['model_revision'], monitor_adapter='checkpoint-00373',
        actor_prompt_adaptation='独立局部修订模式覆盖本次输出接口；权重和原始前缀保持保存。不是原Actor提示逐字重放。',
        existing_natural_text_sources=16, constructed_source_groups=1, exposed_image_sources=4,
        independent_validation=False, human_gold=False,
        field_mapping='无可靠自然语言主张映射，不启用自动布尔/数字冲突裁决或语义修订后验收。',
        no_hash_operations=True, stop_on_confirmed_severe_harm=True))
    print(json.dumps(dict(rows=36, cached_text_actor_calls=text_calls, new_monitor_calls=4, visual_actor_upper=8), ensure_ascii=False))


if __name__ == '__main__':
    main()
