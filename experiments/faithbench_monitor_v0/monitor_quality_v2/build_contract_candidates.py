"""Hypothetical tool-contract feedback candidates, never actual image trajectories."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import statistics

from assemble_feedback import assemble
from build_feedback_candidates import restore

POLICY={
 'NON_DIRECTIONAL_GLOBAL':'global表征偏离不是真假概率或方向票；无异常也不能据此证明真实。',
 'SUMMARY_LIMIT':'检查总数、阈上异常数和top-3成员分别核对；异常阈值为95。没有全量值时，不能捏造未返回均值。',
 'ACTION_BUDGET':'当前剩余调用额度为0时不能追加CALL，但可根据已有材料修正说明。',
 'TOOL_FACT':'只核实际提供的返回。工具卡不是文字/字段白名单；部分节选不足以证明完整返回从未包含某内容。',
 'UNSPECIFIED':'没有冻结综合权重、置信度充分性或冲突下STOP政策，不因此强定哪种最终标签或必须继续调用。'}


def context(tool_cards,index):
    rng=random.Random(20261017+index)
    n=7+2*(index%4);k=index%4
    top=([94,93,92],[99,94,93],[99,97,94],[99,98,97])[k]
    lower=sorted(rng.sample(range(5,85),n-3))
    values=lower+sorted(top)
    other=values.copy();other[0]+=.5
    assert statistics.median(values)==statistics.median(other)
    assert sum(values)!=sum(other) and values[-3:]==other[-3:]
    assert sum(v>=95 for v in values)==sum(v>=95 for v in other)==k
    signal='synthetic_like' if index%2 else 'real_like'
    complement='real' if signal=='synthetic_like' else 'fake'
    source={
      'rules':{'tool_cards':deepcopy(tool_cards),'review_contract':POLICY},
      'global_return':{'tool':'global_forensic_analyzer','scope':{'num_regions_examined':n},
        'observations':{'max_deviation_percentile':max(values),'median_deviation_percentile':statistics.median(values),'num_atypical_regions':k},
        'most_atypical_regions':[{'region_id':f'R{i+1}','deviation_percentile':v,'bbox':[i*32,0,(i+1)*32,32]} for i,v in enumerate(top)]},
      'local_return':{'tool':'local_texture_analyzer','signal':signal,'strength':'moderate','limitations':tool_cards['local_texture_analyzer']['limitations']},
      'complementary_return':{'tool':'complementary_forensic_analyzer','signal':complement,'strength':'moderate','limitations':tool_cards['complementary_forensic_analyzer']['limitations']},
      'budget':{'remaining_calls':index%3,'available_tools':['provenance_inspector'],'used_tools':['global_forensic_analyzer','local_texture_analyzer','complementary_forensic_analyzer']},
      'visibility':{'global_return':'完整返回'}}
    return source,{'values_a':values,'values_b':other,'mean_a':statistics.mean(values),'mean_b':statistics.mean(other),
        'purpose':'Two possible hidden value arrays with identical returned summary and different means; not model input.'}


def cards_for(source,index):
    keys=list(source);ids=list(range(1,len(keys)+1));rng=random.Random(17000+index);rng.shuffle(ids)
    cards=[{'id':f'E{i:03d}','path':[key],'value':deepcopy(source[key])} for i,key in zip(ids,keys)]
    rng.shuffle(cards)
    assert restore(cards)==source
    return cards,{card['path'][0]:card['id'] for card in cards}


def record(source,index,family,variant,claim,status,refs,reason='',fix='',witness=None,scope=None):
    cards,ids=cards_for(source,index)
    retain=f'当前剩余工具调用额度为{source["budget"]["remaining_calls"]}次。'
    signal=f'局部工具实际返回的原始signal是{source["local_return"]["signal"]}。'
    limit='局部工具可能对真实图像误报，分数强度不代表校准概率。'
    issues=[] if status=='pass' else [{'状态':'未决' if status=='uncertain' else '明确错误','回答原文':claim,
        '证据ID':[ids[key] for key in refs],'理由':reason,'建议':fix}]
    preserved=[{'回答原文':retain,'证据ID':[ids['budget']]},
        {'回答原文':signal,'证据ID':[ids['local_return']]},{'回答原文':limit,'证据ID':[ids['rules']]}]
    if status=='pass':preserved.insert(0,{'回答原文':claim,'证据ID':[ids[key] for key in refs]})
    target={'结论':status,'问题':issues,'保留':preserved,'说明':
        '该归因仍待完整返回核对，预算事实可以保留。' if status=='uncertain' else
        '只纠正明确违反所给事实或契约的主张，不替Actor指定真假结论。' if status=='revise' else '主张符合本例给定事实与契约，保留相关局限。'}
    row={'id':f'contract:{index:03d}:{family}:{variant}','pair_id':f'contract:{index:03d}:{family}',
        'group':f'hypothetical_scenario_{index:03d}','family':family,'input':{'证据卡':cards,'待核回答':claim+' '+retain+signal+limit},'target':target,
        'provenance':{'annotation':'program_constructed_contract_case','hypothetical':True,'natural_actor_output':False,
           'actual_images':0,'human_reviewed':False,'split':None,'independent_evaluation':False,
           'rule_sources':['private/natural_actor_monitor_20261013/tool_cards.json','pilot_v3/region_field_contract.md','monitor_mechanism_v1/CONTRACT_CANDIDATE.md']}}
    if scope:row['input']['审核范围']=scope
    if witness:row['provenance']['hidden_value_witness']=witness
    assemble(row['input']['待核回答'],cards,target)
    return row


def examples(tool_cards,index):
    source,witness=context(tool_cards,index)
    g=source['global_return'];n=g['scope']['num_regions_examined'];k=g['observations']['num_atypical_regions'];maximum=g['observations']['max_deviation_percentile']
    families=[
      ('non_directional_vote',f'global最大偏离为{maximum}，它不是真假概率，也不能作为真假方向票。',
       f'global最大偏离为{maximum}，所以图像为fake的概率就是{maximum}%。',
       ['global_return','rules'],'把参考分布中的偏离百分位误当假图概率，违反所给非方向证据定义。',
       f'保留最大偏离{maximum}及其参考分布含义，撤回假图概率与方向推断，继续保留其他真实信号及局限。'),
      ('count_binding',f'global检查了{n}个区域，其中{k}个达到异常阈值；top-3与这两个计数分别记录。',
       f'global只检查了{k}个区域，却有{n}个区域达到异常阈值。',
       ['global_return','rules'],'检查总数与阈上异常数被互换；不能把不同统计当同一数量。',
       f'改为检查{n}个、阈上异常{k}个，列表成员仍按原top-3保留。'),
      ('missing_mean','global返回了最大值、中位数、异常计数和top-3，但这些值不能唯一确定全区域均值。',
       f'global明确返回了全区域平均偏离值{g["observations"]["median_deviation_percentile"]}。',
       ['global_return','visibility','rules'],'完整返回没有全区域均值；同样的摘要可以对应不同均值，不能把中位数或top-3改称全区均值。',
       '撤回全区域均值断言，保留实际返回的最大值、中位数、计数与top-3，不填造缺失逐项值。'),
      ('signal_conflict',f'局部原始信号为{source["local_return"]["signal"]}，互补原始信号为{source["complementary_return"]["signal"]}，两者方向有冲突。',
       '局部与互补工具的原始真假方向完全一致，没有冲突。',
       ['local_return','complementary_return','rules'],'局部与互补实际给出的方向相反；强度与校准限制不使原始信号消失。',
       f'保留局部{source["local_return"]["signal"]}和互补{source["complementary_return"]["signal"]}的真实冲突及各自局限，不将global加入方向投票。')]
    for family,good,bad,refs,reason,fix in families:
        yield record(source,index,family,'supported',good,'pass',refs)
        yield record(source,index,family,'wrong',bad,'revise',refs,reason,fix,witness if family=='missing_mean' else None)
    budget=deepcopy(source);budget['budget']['remaining_calls']=0
    yield record(budget,index,'call_budget','supported','预算已耗尽，不能追加来源工具调用，但仍可修正已有解释。','pass',['budget','rules'])
    yield record(budget,index,'call_budget','wrong','请立即再CALL provenance_inspector补充一次来源证据。','revise',['budget','rules'],
        '当前预算为0，没有追加CALL额度；不能用补证建议突破明确预算。','撤回追加调用建议，基于已有证据修正或说明未决，不编造新返回，也不替Actor选择最终真假。')
    claim='global完整返回的文字中出现了“云层”二字。'
    yield record(source,index,'source_completeness','complete',claim,'revise',['global_return','visibility','rules'],
        '当前声明提供完整返回，其中没有该文字；归因无依据。这不判断图片里有没有云层。',
        '撤回该工具文字归因；如果只是视觉推断，需另行说明来源，不能冒充工具报告。')
    partial=deepcopy(source);partial['visibility']['global_return']='部分节选，不保证包含原完整返回的全部文字或字段'
    yield record(partial,index,'source_completeness','excerpt',claim,'uncertain',['global_return','visibility','rules'],
        '只提供节选，当前未见该文字不足以证明原完整返回从未包含；工具卡也不是文字白名单，不能强判归因错误。',
        '将这项归因保留未决；如可合法取得既有完整返回则补核，不凭外观替代归因核查，不强制额外CALL。')
    interface=deepcopy(source)
    interface['parser_contract']={'STOP_final_verdict':['real','fake']}
    scope='仅核对拟议STOP的final_verdict接口是否合法；不评图像真假，不补未提供的接口规则。'
    claim='Actor拟输出STOP，final_verdict=inconclusive。'
    yield record(interface,index,'stop_enum_visibility','provided',claim,'revise',['parser_contract','rules'],
        '本例明示STOP终态只允许real或fake，inconclusive不合法；这与证据direction允许哪些值是不同规则。',
        '要求Actor按给定STOP接口修订最终字段并说明不确定性；不由Monitor替它选real或fake，也不伪造新证据。',scope=scope)
    missing=deepcopy(source);missing['parser_visibility']='未提供STOP终态枚举，不能从通常设置补规则。'
    yield record(missing,index,'stop_enum_visibility','missing',claim,'uncertain',['parser_visibility','rules'],
        '当前没有提供STOP终态枚举，不能据工具signal或证据direction的枚举推定这个接口是否合法。',
        '保留接口合法性未决，先明确实际STOP解析契约；不能臆定标签集合，也不替Actor选择真假。',scope=scope)
    mapping=deepcopy(source)
    actual=mapping['local_return']['signal'];opposite='real_like' if actual=='synthetic_like' else 'synthetic_like'
    mapping['actor_evidence']={'observation':f'local原始signal为{actual}','direction':'inconclusive'}
    mapping['mapping_policy']='未提供原始signal到Actor证据direction的强制映射规则。'
    scope='核对原始信号归因及direction记法是否违反给定映射规则；事实错误与缺规则分别处理。'
    for variant,signal,status in (('faithful',actual,'uncertain'),('misreported',opposite,'revise')):
        claim=f'local原始signal为{signal}；Actor保留这个原始信号，并将direction记为inconclusive。'
        draft=record(mapping,index,'mapping_policy_boundary',variant,claim,status,['local_return','mapping_policy','actor_evidence'],
            '未提供强制映射，不能仅凭direction=inconclusive判其违反映射规则；但仍须按实际返回核对原始signal。',
            '映射是否合规保持未决，明确实际规则；保留原始信号与证据局限，不强迫机械复制标签。',scope=scope)
        ids={c['path'][0]:c['id'] for c in draft['input']['证据卡']}
        undecided={'状态':'未决','回答原文':'将direction记为inconclusive','证据ID':[ids['mapping_policy'],ids['actor_evidence']],
            '理由':'实际direction确为inconclusive，但未提供强制映射规则，不能单凭字段不同判错。',
            '建议':'保留该映射判断未决，先明确规则，不擅自规定必须抄原始signal。'}
        if status=='uncertain':
            draft['target']['问题']=[undecided]
            draft['target']['保留'].append({'回答原文':f'local原始signal为{actual}','证据ID':[ids['local_return']]})
        else:
            draft['target']['问题']=[{'状态':'明确错误','回答原文':f'local原始signal为{signal}','证据ID':[ids['local_return']],
                '理由':f'原返回为{actual}，此处却抄成相反的{signal}。映射规则未定不使这个原始事实错误变成未决。',
                '建议':f'把原始signal改回{actual}并保留局限；direction映射另列未决，不强改字段。'},undecided]
        assemble(draft['input']['待核回答'],draft['input']['证据卡'],draft['target'])
        yield draft


def main(tool_cards_path,output):
    from collections import Counter
    tool_cards=json.loads(tool_cards_path.read_text(encoding='utf8'))
    output.mkdir(parents=True,exist_ok=False)
    counts=Counter();seen=set()
    with (output/'candidates.jsonl').open('x',encoding='utf8') as stream:
        for index in range(128):
            for row in examples(tool_cards,index):
                assert row['id'] not in seen;seen.add(row['id'])
                counts[row['family']+'/'+row['target']['结论']]+=1
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    report={'candidate_rows':len(seen),'parameter_scenarios':128,'template_families':8,'independent_image_sources':0,'counts':dict(counts),
        'natural_actor_output':False,'human_gold':False,'training_started':False,'new_split_allocation':False,'new_model_calls':0,
        'limitations':['Numeric variations do not create independent real trajectories or template generalization evidence.',
            'Only supplied tool rules are exercised; STOP enum is visibility-controlled, while STOP sufficiency and model weights remain unspecified.',
            'No image truth labels, no actor execution, no isolated validation; not enough to claim a complete Monitor.']}
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--tool-cards',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();main(args.tool_cards,args.output)
