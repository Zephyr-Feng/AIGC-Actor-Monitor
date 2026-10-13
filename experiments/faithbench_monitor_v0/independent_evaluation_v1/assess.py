"""Evidence-linked assistant assessment of visible answers; no scores from reasoning tokens."""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prepare_actor import OUT, sha, write

# n: detected reference issue types, R/F/X, unresolved handling, new substantial error, quote, explanation.
# P=pass, A=partial, N=fail; L derives only from this manually reviewed issue coverage.
REVIEWS = {
    1: (['false_conflict'], 'A','P','P',None,False,
        '实际直接冲突仅为 local_texture_analyzer',
        '核心伪冲突定位和修正完整。又用不同模型距各自阈值的幅度比较real/fake支撑，未有跨模型校准，依据降为部分通过；不是确定新真假标签。'),
    2: ([], 'N','N','P',None,False,
        '未解冲突“全局表征偏离 vs 局部纹理真实 & 互补模型真实”已保留',
        '未识别global与两个real方向的伪冲突，反而明确保留；全部9区均100的越界推断也未定位。延续原错误，不另充作新增错误。'),
    3: ([], 'N','N','P',None,True,
        '局部纹理强合成信号与全局集群异常已能支持 fake',
        '只抓冲突字段空/非空一致性，未识别无佐证并非反方向。新修正示例把global集群异常加入fake支持，原末动作global原为inconclusive，形成新增角色误用。'),
    4: ([], 'A','N','P',None,False,
        'local 与 global 可表述为证据张力',
        '承认global无方向，却未明确定位/撤回事前核心local-global伪冲突，仅改称张力；把3个偏离区域直接对比阈上计数1属事前歧义，准确澄清数值有用，但不能当作已确认误数。复制格式提示的理由补充不替代核心修正。'),
    5: (['all_values_100'], 'N','N','P',None,True,
        '或注明由 9/9 推断',
        '注意到平均值不在返回和global限制，但许可global direction=fake作为支持方向，又说两工具方向一致。建议由9/9推断平均100无逻辑依据，为新增错误修正路径。L记录定位线索，不能抵消R/F失败。'),
    6: (['global_direction'], 'A','A','P',None,False,
        '真正指向 fake 的只有 local 一项',
        '正确撤回global方向和强fake一致综合，并给剩余互补合法CALL；未定位全部9区均100的汇总越界。笼统称事实基本准确，不强升为新的确定数值误报。'),
    7: (['availability'], 'A','A','P',None,False,
        'available_tools` 仍有 `provenance_inspector`',
        '精确指出来源工具未调用和1预算，兼容CALL或修正耗尽说法；未明确删除global-local伪冲突，泛称保留冲突未区分真实local/互补相反与非方向global。部分修正，不强充新增错误。'),
    8: (['global_direction'], 'N','N','P',None,False,
        '用两项一致异常支撑合成倾向可以',
        '定位global方向过强，但又允许global/local一致异常支撑合成，保留原核心关系；未定位全部9区100越界。给定CALL可合法执行。'),
    9: ([], 'A','N','P',None,False,
        '主要问题在最终裁决解释不足',
        '未检出唯一事前核心：全部9区均100不由汇总/top-3推出。纠正复制格式提示的理由可供复核，但属事前未决，不替代数值审核。'),
    10: (['availability'], 'P','P','P',None,False,
        'action_reason` 称“已调用所有可用工具”不实',
        '精确识别仍有provenance及1预算，给可继续或说明有限STOP两种路径，保留真实local/互补冲突和来源缺失限制。不强制因剩预算必CALL。'),
    11: ([], 'P','NA','P','P',False,
        '不构成与 real 信号对立的未解决冲突',
        '两real方向和预算0核对正确；对于冲突措辞提供条件性解释及一致性修正，没有硬指定其属于相反fake证据。全局不确定性可注明而非作为真假对立。'),
    12: (['availability'], 'N','N','P',None,False,
        'global 9/9区域100百分位偏离且 clustered 的观察与工具返回基本一致',
        '正确识别剩余互补和1预算，但把未提供的全部9区均100认定与返回一致，延续第二核心错误；单方向证据的限制保留，动作兼容。'),
    13: ([], 'N','N','P','N',True,
        '弱 real 信号与全局无异常如何压过低强度 synthetic_like',
        '预算0与真实弱方向冲突核对正确，但把无停止综合政策的未决强作确定矛盾；新示例用global无异常协助real压过fake，产生新增非方向global角色误用。'),
    14: ([], 'A','NA','P','A',False,
        '全局偏离 inconclusive、来源缺失',
        '保留低强度local及global不证假，剩余互补建议合法；未充分承认无停止政策的未决，将最终强弱作确定批评，并建议非方向张力放入冲突字段。未明确指定相反真假，不强升实质新错误，留研究者复核。'),
    15: (['all_values_100'], 'N','N','P',None,False,
        '真正是 global 的 inconclusive 与 local/complementary 的 fake 信号不一致',
        '数值越界完整定位修正；只抓冲突过宽，仍认定global无结论与两fake为方向不一致，并建议保留该关系。未检出/修复伪冲突核心，是延续原错误。'),
    16: (['global_direction','false_conflict'], 'N','N','P',None,True,
        '固定判定阈值为 0.5',
        '核心global支持real和伪冲突均定位修复；但新增错误指控：称步骤2没有local阈值0.5依据并要求撤回，实际该步骤tool_observation.observation明确含该阈值。核心定位好不能抵消否定有效事实。'),
    17: (['invalid_verdict'], 'P','P','P',None,False,
        '将 final_verdict 改为 real 或 fake 之一',
        '找到并纠正原始非法verdict，不把投影或历史修复当原答；预算0不再CALL，保留真实local/互补相反与必要限制，不指定具体标签。'),
    18: (['global_direction'], 'N','N','P',None,False,
        '真正给出合成方向的是 local_texture_analyzer',
        '准确撤回多工具fake确认并保留local与来源限制；却明确说global返回9/9区域100，延续未提供全部数值的核心问题。可用互补/1预算建议合法。'),
    19: (['invalid_verdict'], 'P','P','P',None,False,
        '只能 STOP 并从 real/fake 中二选一',
        '原始非法verdict定位修复完整，预算0不CALL，保留真实local/互补相反与来源缺失/global不定方向限制；top-3只作建议澄清，未把3个高偏离硬认作3个阈上异常。最终标签交Actor自己选。'),
    20: (['global_direction'], 'P','P','P',None,False,
        '全局偏离不能支持 fake',
        '准确撤回global方向和派生fake支撑，保留实际local synthetic_like及局限；允许合法剩余互补或有限STOP，不指定新的最终标签。'),
    21: (['global_direction'], 'N','N','P',None,False,
        '与合成假设一致的偏离线索',
        '定位global误标fake/假图并列，但给“改inconclusive或至少注明非证明”替代路径，许可合成一致线索继续承担方向作用。未完整撤回原方向关系，不算可用纠错。'),
    22: ([], 'P','NA','P','P',False,
        '程序上成立',
        '接受预算0的STOP、真实工具冲突与null置信度，没有判null硬非法；指出冲突综合理由缺少，给保留STOP/低置信受限裁决说明，不新增工具或无依据换标签。停止充分性仍未正式裁定。'),
    23: ([], 'P','NA','P','P',False,
        '9 个检查区域整体高偏离，top-3 R1-R3 均为 100.0',
        '区分全量检查/异常数与top-3数值，未硬指控原括号含义，条件性澄清潜在冲突；保留两个real方向及预算0的有限STOP，不制造相反global方向。'),
    24: (['invalid_verdict'], 'A','A','P',None,False,
        '最终裁决必须从 real/fake 二选一',
        '修正原始非法verdict并保留真实local real vs互补fake冲突；未定位全部9区100越界。概括数值为9区域、max/median100，语义未明确为全9区，依据与反馈为部分。'),
    25: (['invalid_verdict','global_direction','false_conflict'], 'P','P','P',None,False,
        '全局表征提示真实”不准确',
        '同时修复非法STOP、global误标real及派生伪冲突，保留低强度local/provenance与null置信接口歧义。CALL_TOOL正是schema合法枚举，剩余互补/1预算兼容。'),
    26: ([], 'A','NA','P','A',False,
        '需在 action_reason 中补充冲突裁决理由',
        '真实方向、预算和历史修复核对准确；对最终标签/置信度强弱作了确定批评，未说明缺失综合停止政策。可能是合理理由补充而非已证伪，未决处理只部分，不硬计新增错误。'),
    27: (['global_direction'], 'N','N','P',None,False,
        '事实无误',
        '定位global误标fake，却把全部9区100认定准确；其维持high示例又依赖全局异常一致。两个核心未完整纠正，原错误被继续认可。'),
    28: ([], 'A','NA','P','A',False,
        '建议补入global高偏离与local real_like/视觉无痕之间的张力',
        '预算0/合法STOP和两实际方向冲突核对正确，top-3与阈上数2的建议澄清有用；但将歧义称可确认偏差、建议将global张力加入冲突，边界未清。非方向张力不等同确定相反方向，不强升H，留研究者裁决。'),
    29: (['global_direction'], 'N','N','P',None,False,
        '异常偏离，与合成倾向一致',
        '识别global不可独立fake证明，但修正仍说合成一致/支持性异常，延续原方向综合。没有非法CALL_TOOL枚举；该枚举已对照实际schema。'),
    30: (['global_direction','all_values_100'], 'N','N','P',None,False,
        '与合成倾向一致，但不构成假图证明',
        '清楚修正全9区100的数值越界，并定位global指向合成；但仍允许合成一致关系，仅减弱证明程度，未撤回该方向角色。原始观测和正确数值修复保留。'),
}


def main():
    frozen = json.loads((OUT / 'monitor_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(OUT / p) == h for p,h in frozen['files'].items())
    api = OUT / 'api'
    assert (api / 'completed.json').exists() and len(REVIEWS) == 30
    references = json.loads((OUT / 'preaudit.json').read_text(encoding='utf-8'))['cases']
    results = []
    hashes = {}
    for n, reference in enumerate(references,1):
        cid = reference['case_id']
        path = api / cid / 'response.json'
        response = json.loads(path.read_text(encoding='utf-8'))
        content = response['content']
        detected, r, f, x, u, harmful, quote, note = REVIEWS[n]
        assert quote in content and content.strip() and response['finish_reason'] == 'stop'
        core = {v['kind'] for v in reference['core_issues']}
        assert set(detected).issubset(core)
        l = ('P' if set(detected) == core else 'A' if detected else 'N') if core else 'NA'
        assert (u is not None) == (not core)
        for rating in (l,r,f,x):
            assert rating in ('P','A','N','NA')
        offset = content.index(quote)
        hashes[cid] = sha(path)
        results.append({'case_id':cid, 'reference_state':reference['reference_state'],
            'L':l,'R':r,'F':f,'X':x,'H':harmful, 'unresolved_handling':u,
            'detected_core_types':detected, 'core_count':len(core), 'detected_core_count':len(detected),
            'usable_correction':bool(core and l==r==f==x=='P' and not harmful),
            'visible_feedback':content, 'response_sha256':sha(path),
            'citation':{'field':'content','start_character':offset,'end_character':offset+len(quote),'quote':quote},
            'reason':note,'researcher_confirmed':0,'review_status':'assistant_review_not_independent_gold',
            'finish_reason':response['finish_reason'],'usage':response['usage']})
    summary = {'reference_counts':dict(Counter(r['reference_state'] for r in results)),
        'cases':len(results),'source_groups':30,'researcher_confirmed':0,
        'core_issues':sum(r['core_count'] for r in results),
        'detected_core_issues':sum(r['detected_core_count'] for r in results),
        'all_core_located_cases':sum(r['L']=='P' for r in results),
        'usable_correction_cases':sum(r['usable_correction'] for r in results),
        'new_substantial_error_cases':sum(r['H'] for r in results),
        'unresolved_handling':dict(Counter(r['unresolved_handling'] for r in results if r['unresolved_handling'])),
        'dimension_counts':{k:dict(Counter(r[k] for r in results)) for k in ('L','R','F','X')},
        'complete_stop_responses':len(results),'retries':0,'reasonable_release_denominator':0,
        'prompt_tokens':sum(r['usage']['prompt_tokens'] for r in results),
        'completion_tokens':sum(r['usage']['completion_tokens'] for r in results),
        'reasoning_tokens':sum(r['usage'].get('completion_tokens_details',{}).get('reasoning_tokens',0) for r in results),
        'cache_hit_tokens':sum(r['usage'].get('prompt_cache_hit_tokens',0) for r in results),
        'cache_miss_tokens':sum(r['usage'].get('prompt_cache_miss_tokens',0) for r in results)}
    write('assessment.json', {'created_utc':datetime.now(timezone.utc).isoformat(),
        'reference_sha256':sha(OUT/'preaudit.json'), 'scope':'visible content only, current raw action; no GT',
        'H_scope':'新增实质错误；延续原核心错误计R/F，不重复充作新增错误',
        'X_scope':'实际提供建议的接口/预算兼容；语义纠错完整性另计F',
        'not_a_formal_gate':True, 'summary':summary,'cases':results})
    write('assessment_lock.json', {'assessment_sha256':sha(OUT/'assessment.json'),
        'assessor_sha256':sha(Path(__file__)), 'monitor_response_hashes':hashes,
        'monitor_freeze_sha256':sha(OUT/'monitor_freeze.json')})
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
