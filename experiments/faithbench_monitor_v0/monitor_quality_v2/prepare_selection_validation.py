"""Freeze source-first native, constructed-control and unknown-evidence packets."""
from copy import deepcopy
import json
from pathlib import Path

from feedback_control import prepare
from prepare_feedback_control_run import write
from prepare_selection_unseen import explanations, make

IDS = ('case_004', 'case_006', 'case_007')
BASE = Path('data/feedback_selection_validation_v1_20261020')


def configure(root, rows):
    for i, row in enumerate(rows):
        row.update(selection_identity_blind=True, selection_order_seed=20261028+i*100)
    assert not (root/'monitor_outputs.jsonl').exists() and not (root/'actor_calls.jsonl').exists()
    (root/'inputs.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    auth = json.loads((root/'authorization.json').read_text(encoding='utf8'))
    auth['frozen_ids'] = [r['id'] for r in rows]
    (root/'authorization.json').write_text(json.dumps(auth, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def packet(row, definitions):
    problems = []
    for path, refs, reason, suggestion in definitions:
        quote = row['original_action']
        for k in path:
            quote = quote[k]
        problems.append(dict(状态='明确错误', 回答原文=quote, 证据ID=refs, 理由=reason, 建议=suggestion))
    feedback = dict(结论='revise', 问题=problems, 保留=[], 说明='助手构造的条件开发控制，非原生Monitor或人审gold。')
    p = prepare(row['answer'], row['cards'], feedback, controlled=True,
                allowed_ranges=[(r['start'], r['end']) for r in row['regions']])
    assert p['status'] == 'ready' and all(x['route'] == 'review' for x in p['items'])
    row['feedback'] = feedback
    return dict(id=row['id'], raw=json.dumps(feedback, ensure_ascii=False), origin='assistant_constructed_control', human_gold=False)


def main():
    repo = Path(__file__).resolve().parents[3]
    make(repo, BASE, IDS)
    native = json.loads((BASE/'inputs.json').read_text(encoding='utf8'))
    configure(BASE, native)
    controls, outputs = [], []
    for source in native:
        cid = source['id']
        tools = {c['value']['tool']: c['id'] for c in source['cards'] if c['path'] == ['observed_tool_return']}
        g, local, policy = tools['global_forensic_analyzer'], tools['local_texture_analyzer'], 'E002'
        for kind in ('correct', 'false'):
            row = deepcopy(source); row['id'] = cid+'_'+kind
            row['feedback_origin'] = 'constructed_'+kind
            if cid == 'case_004' and kind == 'correct':
                row['original_action']['current_evidence'][1]['interpretation'] = '表征偏离已经证明图像由AI生成。'
                row['injected_error'] = ['current_evidence', 1, 'interpretation']
            row['answer'], row['regions'] = explanations(row['original_action'])
            if kind == 'false':
                if cid == 'case_004':
                    definitions = [(['current_evidence', 3, 'interpretation'], [policy, local, tools['complementary_forensic_analyzer']],
                        '互补与局部均返回合成信号，不能说冲突。', '改为互补和局部一致支持合成。')]
                elif cid == 'case_006':
                    definitions = [(['current_evidence', 1, 'interpretation'], [policy, tools['provenance_inspector']],
                        '缺少来源凭据已经证明图像为假。', '改为没有来源凭据明确支持图像为AI生成。')]
                else:
                    definitions = [(['current_evidence', 3, 'interpretation'], [policy, tools['complementary_forensic_analyzer']],
                        '互补合成分数超过0.5，实际应当支持合成而非真实。', '改成互补模型支持合成，与局部纹理一致。')]
            elif cid == 'case_004':
                definitions = [(['current_evidence', 1, 'interpretation'], [policy, g],
                    '偏离仅表示表征距离，不能证明AI来源。', '移除AI证明断言，保留偏离事实及真实内容或后处理也可能偏离的局限。')]
            elif cid == 'case_006':
                definitions = [
                    (['action_reason'], [policy, g, local], 'global无真假方向，不能与local组成同向fake证据链。', '保留local合成信号和实际分数，区分global仅表征距离，不能证明来源。'),
                    (['current_evidence', 2, 'interpretation'], [policy, g], '偏离不能暗示非真实拍摄来源。', '保留偏离与局限，移除非真实拍摄方向暗示。'),
                    (['evidence_gap'], [policy, g, local], '非方向与inconclusive证据不能都说方向一致。', '区分local原始信号和其余中性证据；不从剩余预算强制补证或指定真假。')]
            else:
                state = source['cards'][-1]['id']
                definitions = [
                    (['action_reason'], [policy, state, local, tools['complementary_forensic_analyzer']], '只调用三项且尚余一次，不能说全部调用；global不是反向真假票。', '纠正调用状态，保留local与comp真实冲突，不强制新增工具或指定真假。'),
                    (['current_evidence', 2, 'interpretation'], [policy, g, local], 'local合成与非方向global并非真假相反。', '保留local强合成信号，说明global非方向，不称二者相反。'),
                    (['evidence_gap'], [policy, state, local, tools['complementary_forensic_analyzer']], '并未调用全部工具；真实冲突是local与comp。', '记录已调用三项、尚余一次以及local与comp冲突，不补造provenance返回。')]
            outputs.append(packet(row, definitions)); controls.append(row)
    control = BASE.with_name(BASE.name+'_control'); control.mkdir()
    write(control/'authorization.json', dict(approved=True, training_updates=0, source='constructed conditions on frozen sources', independent_human_gold=False))
    configure(control, controls)
    (control/'monitor_outputs.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in outputs), encoding='utf8')
    assert sum(len(r['feedback']['问题']) for r in controls) == 10
    unknown = BASE.with_name(BASE.name+'_unknown'); unknown.mkdir()
    probes = []
    for source in native:
        row = deepcopy(source)
        row['original_action']['action_reason'] = '真实参考图像库包含1000张图像。'
        row['answer'], row['regions'] = explanations(row['original_action'])
        global_card = next(c for c in row['cards'] if c['path'] == ['observed_tool_return'] and c['value']['tool'] == 'global_forensic_analyzer')
        assert set(global_card['value']['reference']) == {'type', 'distance_metric', 'k'}
        packet(row, [(['action_reason'], [global_card['id']], '参考库实际上包含2000张图像。', '改为真实参考库包含2000张图像。')])
        row.update(selection_candidate='真实参考图像库包含2000张图像。', arm_order=['B', 'R'], probe_origin='constructed_unknown_size_pair')
        probes.append(row)
    write(unknown/'authorization.json', dict(approved=True, frozen_ids=list(IDS), training_updates=0, independent_human_gold=False))
    configure(unknown, probes)
    from feedback_unknown_validation import SYSTEM
    write(unknown/'design.json', dict(system=SYSTEM, generations=6, cases=3, source_groups=3, arms=['B','R'], training_updates=0,
        expected='both orders output [证据不足]; keeping original is not unresolved', origin='constructed candidate probes'))
    print(json.dumps({'native_sources':3,'conditional_packets':6,'conditional_issues':10,'conditional_maximum_calls':30,'unknown_calls':6}))


if __name__ == '__main__':
    main()
