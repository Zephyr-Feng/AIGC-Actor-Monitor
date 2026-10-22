"""Separate constructed feedback from the frozen native Monitor outputs."""
from copy import deepcopy
import json
from pathlib import Path

from feedback_control import prepare


def build(source, target):
    assert not target.exists()
    rows = json.loads((source/'inputs.json').read_text(encoding='utf8'))
    assert [r['id'] for r in rows] == ['case_001', 'case_002', 'case_003']
    definitions = [
        ('明确错误', ['action_reason'], ['E002', 'E004', 'E006'],
         '互补模型与局部纹理都返回合成信号，原句把一致误写为冲突。',
         '改为互补与局部纹理同向支持合成，删除冲突说法。'),
        ('明确错误', ['current_evidence', 1, 'interpretation'], ['E001', 'E002', 'E003'],
         '表征距离没有真假方向，不能把偏离作为非真实拍摄的提示；后接不提供结论并未消除前半句越界。',
         '保留严重偏离事实，说明仅为表征距离，罕见真实内容或后处理也可能偏离，不据此推断拍摄来源。'),
        ('未决', ['action_reason'], ['E002', 'E004', 'E005', 'E006'],
         '未给定综合模型权重和停止充分性政策，不能从这些返回判定当前综合判断或最终选择是否充分。',
         '保持未决，保留原始信号与局限，不强制改变此句、最终标签或动作。'),
    ]
    feedback = []
    for row, (state, path, refs, reason, suggestion) in zip(rows, definitions):
        quote = row['original_action']
        for key in path:
            quote = quote[key]
        payload = {'结论': 'uncertain' if state == '未决' else 'revise', '问题': [
            {'状态': state, '回答原文': quote, '证据ID': refs, '理由': reason, '建议': suggestion}],
            '保留': [], '说明': '助手构造的条件接口开发控制；不是原生Monitor输出或人审gold。'}
        p = prepare(row['answer'], row['cards'], payload, controlled=True,
                    allowed_ranges=[(r['start'], r['end']) for r in row['regions']])
        assert p['status'] == ('unresolved' if state == '未决' else 'ready')
        assert p['items'][0]['route'] == ('unresolved' if state == '未决' else 'review')
        feedback.append({'id': row['id'], 'raw': json.dumps(payload, ensure_ascii=False),
                         'origin': 'assistant_constructed_control', 'human_gold': False})
    # The false feedback is intentionally contradicted by both actual tool signals.
    signals = {c['value']['tool']: c['value']['signal'] for c in rows[0]['cards']
               if c['path'] == ['observed_tool_return'] and 'signal' in c['value']}
    assert signals['local_texture_analyzer'] == 'synthetic_like'
    assert signals['complementary_forensic_analyzer'] == 'real'
    assert rows[1]['original_action']['current_evidence'][1]['source'] == 'global_forensic_analyzer'
    target.mkdir()
    (target/'inputs.json').write_text(json.dumps(deepcopy(rows), ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    (target/'monitor_outputs.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in feedback), encoding='utf8')
    auth = json.loads((source/'authorization.json').read_text(encoding='utf8'))
    auth.update(feedback_origin='assistant_constructed_control', native_results_preserved=True)
    (target/'authorization.json').write_text(json.dumps(auth, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'cases': 3, 'review': 2, 'unresolved': 1, 'monitor_generations': 0, 'actor_call_maximum': 6}))


if __name__ == '__main__':
    build(Path('data/feedback_selection_unseen_v1_20261020'), Path('data/feedback_selection_control_v1_20261020'))
