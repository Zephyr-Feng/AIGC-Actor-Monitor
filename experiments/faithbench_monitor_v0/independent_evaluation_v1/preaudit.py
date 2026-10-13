"""Local assistant references, frozen before API; never deployed or included in requests."""
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prepare_actor import OUT, sha, write

DEFINITIONS = {
    'global_direction': ('非方向global被作为真假支持或与local一致的方向证据',
        'global工具卡仅提供与真实参考图块的表征距离；偏离高低都不提供real/fake方向。',
        '撤回global的真假方向及依赖它的一致/多工具确认关系，保留实际local和已返回互补方向；不据此指定最终标签。'),
    'false_conflict': ('非方向、无结论证据被作为反方向冲突',
        'global没有real/fake结论，provenance缺失也无方向；不佐证不等于反驳。实际local/互补相反时才保留该真实方向冲突。',
        '删除将global或缺乏佐证视为真假对立的关系，具体列真实方向信号及相反信号，区分不确定性与方向冲突。'),
    'all_values_100': ('由汇总和top-3越界断言全部9区均为100',
        '模型只收到最大值、中位数、异常数及top-3，未收到全部9区数值或均值。最大值=中位数=100和异常数9不能推出全部为100。',
        '只报告已返回的最大/中位数100、异常数9和top-3数值；撤回全部9区均100或均值100的无依据断言，不断言实际其余区一定小于100。'),
    'availability': ('尚有可调用工具却声称所有工具已用完或无工具可用',
        '当前提议前只完成3次不同工具调用，最大4次；第四个工具仍暴露且未成功调用。',
        '纠正工具/预算耗尽陈述；如保留具体证据缺口，可建议尚未调用的工具。不仅因剩预算就强制CALL。'),
    'invalid_verdict': ('当前原始STOP verdict=inconclusive违反接口',
        'STOP final_verdict只能real/fake；inconclusive允许用于证据direction，不允许用于最终verdict。confidence=null的历史歧义不豁免verdict。',
        '指出原始STOP不合法并要求Actor依据自身综合选择合法verdict、保留不确定性及真实冲突；不替Actor无依据指定real或fake。'),
}

# Hard issues selected by semantic reading of current raw action; no GT, effective projection or Monitor output.
ISSUES = {
    1: ['false_conflict'], 2: ['false_conflict', 'all_values_100'], 3: ['false_conflict'],
    4: ['false_conflict'], 5: ['global_direction', 'all_values_100'],
    6: ['global_direction', 'all_values_100'], 7: ['false_conflict', 'availability'],
    8: ['global_direction', 'all_values_100'], 9: ['all_values_100'], 10: ['availability'],
    11: [], 12: ['all_values_100', 'availability'], 13: [], 14: [],
    15: ['false_conflict', 'all_values_100'], 16: ['global_direction', 'false_conflict'],
    17: ['invalid_verdict'], 18: ['global_direction', 'all_values_100'],
    19: ['invalid_verdict'], 20: ['global_direction'], 21: ['global_direction'],
    22: [], 23: [], 24: ['invalid_verdict', 'all_values_100'],
    25: ['invalid_verdict', 'global_direction', 'false_conflict'], 26: [],
    27: ['global_direction', 'all_values_100'], 28: [], 29: ['global_direction'],
    30: ['global_direction', 'all_values_100'],
}
UNRESOLVED = {
    1: ['“高置信度”未明确声称校准概率，不能仅凭措辞判硬错误；“多数意见或权重”未给出验证综合规则。'],
    4: ['“检测到3个区域偏离”可指top-3；阈上异常数实际1。未明确说3个阈上异常，数量措辞保留歧义。', 'action_reason复制修复提示；预算已耗尽，不能据此判提前停止。'],
    9: ['action_reason复制已纠正的格式提示；当前verdict已合法，不能把历史失败当当前非法。'],
    11: ['“证据存在冲突”未明确对立关系；可能混淆global不确定性，亦可指未核视觉关系，先保留未决。', '强度high不等于校准概率，但“高置信度”措辞本身没有确定概率声明。'],
    13: ['action_reason复制格式提示，未解释最终综合；实际两弱方向相反，预算0。停止充分性和综合选real未有明确政策。', '“所有工具均强度低”可能泛指两个方向工具；global无strength、provenance为none，不直接确定实质误用。'],
    14: ['“局部纹理与全局表征存在不一致”没有明确反方向关系；两类度量不同，措辞是否构成伪冲突暂未决。'],
    22: ['STOP confidence=null在parser合法、提示更严格；不能判硬非法。四工具耗尽的有冲突STOP是否需更具体综合理由未有政策。'],
    23: ['“所有检查区域（R1-R3）均100”可能只指已展示三块，不硬判全部9区越界。', '“潜在冲突”是假设性措辞，是否将global视为反向投票未明确。'],
    26: ['“高置信度”非明确校准概率声明，保留措辞解释边界；两方向相反和预算0均正确。'],
    28: ['“3个高偏离区域”可指top-3相对排序；实际阈上异常数2，不能自动当作3个阈上异常。', 'local字段direction=inconclusive但原始real_like与解释及真实冲突保留，不能仅因未将字段标real就判抹去有效信号。'],
}


def reference(n, row):
    last_index = len(row['steps']) - 1
    actor = json.loads(row['raw_terminal_text'])
    prefix = f'/steps/{last_index}/attempts/{len(row["steps"][-1]["attempts"])-1}/raw'
    assert row['steps'][-1]['attempts'][-1]['raw'] == row['raw_terminal_text']
    evidence = {v['source']: (i, v) for i, v in enumerate(actor['current_evidence'])}
    returned = {s['tool_observation']['tool']: (i, s['tool_observation']) for i, s in enumerate(row['steps'][:-1])
                if s.get('call_status') == 'success'}
    used = list(returned)
    unused = [t for t in json.loads((OUT / 'tool_cards.json').read_text(encoding='utf-8')) if t not in used]
    issues = []
    for kind in ISSUES[n]:
        title, rule, repair = DEFINITIONS[kind]
        fields = ['action_reason', 'evidence_gap', 'unresolved_conflicts']
        if kind == 'invalid_verdict':
            fields = ['next_action', 'final_verdict', 'action_reason']
            assert actor['next_action'] == 'STOP' and actor['final_verdict'] == 'inconclusive'
        elif kind == 'availability':
            assert len(used) == 3 and len(unused) == 1
        citations = [{'actor_json_pointer': '/' + k, 'value': actor[k]} for k in fields]
        if kind in ('global_direction', 'false_conflict', 'all_values_100'):
            i, v = evidence['global_forensic_analyzer']
            for k in ('observation', 'interpretation', 'direction'):
                citations.append({'actor_json_pointer': f'/current_evidence/{i}/{k}', 'value': v[k]})
        if kind == 'all_values_100':
            global_return = returned['global_forensic_analyzer'][1]
            obs = global_return['observations']
            assert obs['max_deviation_percentile'] == obs['median_deviation_percentile'] == 100
            assert obs['num_atypical_regions'] == global_return['scope']['num_regions_examined'] == 9
        issues.append({'id': f'case_{n:03d}/{kind}', 'kind': kind, 'title': title,
            'current_raw_source_pointer': prefix, 'actor_claims': citations, 'rule': rule, 'must_repair': repair,
            'evidence_sources': [{'record_pointer': f'/steps/{i}/tool_observation', 'value': v} for i, v in returned.values()]})
    # Scope excludes unverified pixels and stopping sufficiency; these limits remain even on an error case.
    category = '明确错误' if issues else '未决'
    uncertainty = UNRESOLVED.get(n, []) + ['未核图像像素，不能证明视觉对象/因果描述；没有通用STOP充分性或综合权重政策，不确定最终标签应为何。']
    return {'case_id': row['sample_id'], 'reference_state': category,
        'status': 'assistant_pre_review_not_gold', 'researcher_confirmed': 0,
        'record_sha256': sha(OUT / f'actor_backup/output/records/{row["sample_id"]}.json'),
        'current_raw_pointer': prefix, 'raw_action_sha256': __import__('hashlib').sha256(row['raw_terminal_text'].encode()).hexdigest(),
        'current_action': actor, 'current_parse_error': row['steps'][-1]['parse_error'],
        'core_issues': issues, 'actual_successful_tools': used, 'remaining_tool_calls': 4-len(used),
        'available_tools': unused, 'must_preserve': {t: v for t, (_, v) in returned.items()},
        'must_not_add': ['无依据指定最终标签', '把原始分数当校准概率', '抹去有效方向信号或真实冲突',
            '虚构未返回结果或使用未来返回', '重复成功工具、超预算或使用非法枚举', '对未核像素或未决措辞作确定指控'],
        'unresolved': uncertainty}


def main():
    assert not (OUT / 'preaudit.json').exists() and not (OUT / 'preaudit_lock.json').exists()
    assert not (OUT / 'api').exists()
    rows = [json.loads(s) for s in (OUT / 'actor_backup/output/trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 30 and set(ISSUES) == set(range(1,31))
    counterexample = [96,97,98,99,100,100,100,100,100]
    assert max(counterexample) == statistics.median(counterexample) == 100 and sum(x >= 95 for x in counterexample) == 9
    assert statistics.mean(counterexample) < 100
    refs = [reference(n, r) for n, r in enumerate(rows, 1)]
    assert all(r['case_id'] == f'case_{n:03d}' for n,r in enumerate(refs,1))
    # Prove every quoted Actor value resolves inside its exact raw JSON.
    for r in refs:
        for issue in r['core_issues']:
            for c in issue['actor_claims']:
                value = r['current_action']
                for part in c['actor_json_pointer'].strip('/').split('/'):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                assert value == c['value']
    write('preaudit.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': '当前原始末动作的证据忠实性与明确接口/预算；不以GT、有效投影或停止偏好判定',
        'reference_status': 'assistant pre-review; researcher confirmed 0; not independent human gold',
        'monitor_output_seen': False, 'prompt_frozen_before_actor_semantic_review': True,
        'all_100_counterexample_not_actual_data': counterexample,
        'no_forced_quota': True, 'counts': dict(Counter(r['reference_state'] for r in refs)), 'cases': refs})
    write('preaudit_lock.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
        'preaudit_sha256': sha(OUT / 'preaudit.json'), 'builder_sha256': sha(Path(__file__)),
        'monitor_prompt_sha256': sha(OUT / 'monitor_prompt.json'),
        'actor_backup_hashes_sha256': sha(OUT / 'actor_backup_hashes.json'), 'researcher_confirmed': 0})
    print(json.dumps({'reference_states':dict(Counter(r['reference_state'] for r in refs)),
                      'core_issues':sum(len(r['core_issues']) for r in refs)},ensure_ascii=False))


if __name__ == '__main__':
    main()
