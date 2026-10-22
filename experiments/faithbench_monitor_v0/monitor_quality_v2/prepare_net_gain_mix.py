"""Reuse reviewed training material; keep label strength and source exposure visible."""
from copy import deepcopy
import json
from pathlib import Path

from assemble_feedback import assemble
from prepare_feedback_control_run import write
from prepare_selection_unseen import explanations


OUT = Path('data/monitor_net_gain_sft_v2_20261021')


def value(action, path):
    for key in path:
        action = action[key]
    return action


def replace(action, path, text):
    for key in path[:-1]:
        action = action[key]
    action[path[-1]] = text


def make_row(source, name, answer, target, construction):
    assemble(answer, source['cards'], target)
    return dict(id=source['id']+'_'+name, group=source['id'], task='forensic_full', target=target,
                human_gold=False, label_strength='assistant evidence-reviewed; not independent human gold',
                construction=construction, messages=[dict(role='system', content=source['monitor_system']),
                dict(role='user', content=json.dumps(dict(证据卡=source['cards'], 待核回答=answer,
                     审核范围='核对完整解释的证据关系；没有像素不判视觉真相，不改标签、置信度、direction或动作。'), ensure_ascii=False)),
                dict(role='assistant', content=json.dumps(target, ensure_ascii=False))])


def feedback(issues, keeps, note):
    return dict(结论='revise' if any(i['状态']=='明确错误' for i in issues) else 'uncertain' if issues else 'pass',
                问题=issues, 保留=keeps, 说明=note)


def build():
    old = Path('data/monitor_targeted_sft_v1_20261021')
    sources = {r['id']:r for r in json.loads((old/'inputs.json').read_text(encoding='utf8'))
               if r['id'] in {'case_001','case_002','case_004','case_006','case_007','case_008','case_009','case_010'}}
    pilot = json.loads(Path('data/adviser_test_v1_20261021/actor_templates.json').read_text(encoding='utf8'))
    for cid in ('case_020','case_021','case_022'):
        row = deepcopy(next(r for r in pilot if r['id']==cid+'_native'))
        row.update(id=cid, group=cid); sources[cid]=row
    assert len(sources)==11
    # These are explicit assistant judgements, not generated labels or new image truth.
    reason=('action_reason',); gap=('evidence_gap',)
    ev=lambda i: ('current_evidence',i,'interpretation')
    definitions={
      'case_001':[(reason,'未决','高置信度含义未给校准依据，不能把原始强度视为校准置信度。','澄清为原始信号强度，保留真实冲突。','互补模型real与局部synthetic_like信号冲突；原始强度不等于校准置信度。'),
                  (ev(2),'未决','局部分数未校准，高置信度表述需澄清。','保留synthetic_like及未校准限制。','局部原始信号为synthetic_like、强度高，但未校准且可能误报。'),
                  (ev(4),'未决','互补原始强度不提供校准置信度。','保留real与local的实际冲突。','互补原始信号为real、强度高，但未校准，与局部synthetic_like实际相反。')],
      'case_004':[(ev(2),'未决','高强度不能自动解释为校准置信度。','澄清原始强度与不确定性。','局部原始信号为synthetic_like、强度高，但未校准且可能误报。'),
                  (ev(3),'未决','moderate描述原始强度，不是校准置信度。','保留真实方向冲突与未校准限制。','互补原始信号为real、强度中等，但未校准，与局部synthetic_like冲突。')],
      'case_007':[(reason,'未决','实际只见三项返回；未给穷尽可用工具或强制停止的政策。','写实际调用状态，不补停止政策。','已调用global、local、comp三项，剩余一次额度；local与comp信号相反，来源工具尚未调用，不能由剩余额度推出必须继续或停止。'),
                  (ev(1),'未决','R1排序不认证过曝或后处理原因。','保留实际表征统计，未知原因明确未知。','global检查六个区域、异常数为零；表征偏离无真假方向，也不能指认过曝或后处理原因。'),
                  (ev(2),'明确错误','global没有真假方向，不能与local构成相反方向票。','撤回与global的方向冲突，保留local信号。','local原始信号为synthetic_like、强度高，未校准；global没有相反真假方向。'),
                  (ev(3),'未决','low是原始强度，不提供校准置信度。','保留comp real及真实local冲突。','comp原始信号为real、强度低且未校准，与local实际相反。'),
                  (gap,'未决','未见来源工具返回，不能认证所有可用工具已穷尽。','注明三项已用、来源尚未核查，保留真实冲突。','已取得三项工具返回，local与comp真实冲突；未调用来源工具，来源信息仍未知。')],
      'case_010':[(reason,'未决','只见三项返回，未提供穷尽或强制停止政策。','保留真实冲突，不推导必须继续或停止。','已取得global、local、comp三项返回；local与comp信号相反，剩余额度不规定必须继续或停止。'),
                  (gap,'未决','给定记录不足以认证所有可用工具已穷尽。','写已取得三项返回及真实冲突。','已取得三项工具返回，local与comp存在真实方向冲突，来源工具尚未调用。')],
      'case_020':[(reason,'明确错误','global无真假方向，不能结合其偏离投票定假。','撤回global合成票，保留local信号及局限。','global严重偏离但无真假方向；local为synthetic_like，可能误报且未校准，不能以二者构成同向定假链。'),
                  (ev(2),'未决','原始强度不是校准置信度。','保留synthetic_like，澄清强度及误报。','local原始信号为synthetic_like、强度高，但未校准且可能误报。'),
                  (ev(3),'明确错误','global不能由偏离推断合成来源。','撤回合成推断，保留偏离及局限。','表征严重偏离真实参考，但不提供真假方向或来源证明。'),
                  (gap,'未决','未说明冲突对象及解决依据，不能据多类型证据认证冲突已解决。','说明仍有何种证据局限，不补权重政策。','已取得三类证据；global无真假方向，local有误报与未校准限制，来源未知。')],
      'case_021':[(reason,'明确错误','global无真假方向，不能与local构成一致假图链。','撤回global方向归因，保留local真实信号。','global表征偏离无真假方向；local为synthetic_like，仍有误报与未校准限制。'),
                  (ev(2),'未决','原始强度不等同校准置信度。','澄清原始信号及限制。','local原始信号为synthetic_like、强度高，但未校准且可能误报。'),
                  (ev(3),'明确错误','表征偏离不支持合成来源推断。','撤回合成推断，保留偏离及局限。','表征严重偏离真实参考，但不提供真假方向或来源证明。')],
      'case_022':[(ev(2),'未决','原始强度不提供校准置信度，高置信度需澄清。','保留local信号、未校准及真实冲突。','local原始信号为synthetic_like、强度高，但未校准且可能误报。')]
    }
    existing=json.loads(Path('data/monitor_net_gain_sft_v1_20261021/full_answer_supervision.json').read_text(encoding='utf8'))
    rows=[]; corrected={}
    for cid,source in sources.items():
        if cid in {'case_002','case_006','case_008','case_009'}:
            native=deepcopy(next(r for r in existing if r['id']==cid+'_native_full'))
            rows.append(make_row(source,'native_full',source['answer'],native['target'],'original natural cached explanation, assistant review'))
            if cid=='case_009':
                action=deepcopy(source['original_action'])
            else:
                positive=next(r for r in existing if r['id']==cid+'_corrected_full')
                text=json.loads(positive['messages'][1]['content'])['待核回答']
                # Reconstruct only the known editable fields from their explicit path headers.
                action=deepcopy(source['original_action'])
                for region in source['regions']:
                    header='\n['+'/'.join(map(str,region['path']))+']\n'
                    start=text.index(header)+len(header)
                    end=text.find('\n[',start)
                    replace(action,region['path'],text[start:end if end!=-1 else len(text)])
        else:
            action=deepcopy(source['original_action']); issues=[]
            for path,state,why,suggest,new in definitions[cid]:
                refs=['E001','E002']+[c['id'] for c in source['cards'] if c['path']==['observed_tool_return']]
                issues.append(dict(状态=state,回答原文=value(action,path),证据ID=refs,理由=why,建议=suggest))
                replace(action,path,new)
            rows.append(make_row(source,'native_full',source['answer'],feedback(issues,[],'分别核对证据误用与未决，不能抹去实际相反的工具信号。'),'original natural cached explanation, assistant review'))
        corrected[cid]=action
        answer,_=explanations(action)
        keep=value(action,reason)
        rows.append(make_row(source,'corrected_full',answer,feedback([], [dict(回答原文=keep,证据ID=['E001','E002'])],
                    '保留有据工具关系与局限；不认证视觉真相或最终标签。'),'assistant constructed corrected full-answer control'))
        tools={c['value']['tool']:c for c in source['cards'] if isinstance(c['value'],dict) and 'tool' in c['value']}
        global_card=tools['global_forensic_analyzer']; local_card=tools['local_texture_analyzer']
        global_index=next(i for i,e in enumerate(action['current_evidence']) if e['source']=='global_forensic_analyzer')
        local_index=next(i for i,e in enumerate(action['current_evidence']) if e['source']=='local_texture_analyzer')
        for kind in ('global_chain','library_unknown','signal_relation'):
            draft=deepcopy(action); issues=[]
            def issue(path,text,refs,state,why,suggest):
                replace(draft,path,text)
                issues.append(dict(状态=state,回答原文=text,证据ID=refs,理由=why,建议=suggest))
            if kind=='global_chain':
                refs=[global_card['id'],'E001','E002']
                issue(reason,'全局表征与局部纹理方向一致，两类证据共同证明图像为合成。',refs,'明确错误','global没有真假方向，不能与local形成同向真假票。','撤回global的合成票及证明结论，保留local原始信号和局限。')
                issue(ev(global_index),'表征偏离已经确认图像由AI生成。',refs,'明确错误','表征偏离不是来源证明。','撤回AI来源推断，保留表征偏离与局限。')
            elif kind=='library_unknown':
                issue(ev(global_index),'真实参考库包含8192张图像。',[global_card['id']],'未决','reference没有库容量；k和检查数均不能回答库容量。','待取得库容量记录，不编其他数字，也不能断定不是8192。')
            else:
                comp=tools.get('complementary_forensic_analyzer')
                if comp:
                    local_real=local_card['value']['signal']=='real_like'
                    comp_real=comp['value']['signal']=='real'
                    same=local_real==comp_real
                    text='局部纹理与互补模型方向相反。' if same else '局部纹理与互补模型的实际信号同向。'
                    issue(reason,text,[local_card['id'],comp['id']],'明确错误','两项实际原始signal与原句所述同向/相反关系不符。','按实际原始信号澄清关系，保留各自局限，不改最终真假。')
                else:
                    opposite='真实倾向' if local_card['value']['signal']=='synthetic_like' else '合成倾向'
                    issue(ev(local_index),'局部纹理工具实际返回'+opposite+'。',[local_card['id']],'明确错误','实际原始signal被说反。','按卡片保留真实返回及未校准限制，不改最终真假。')
            answer,_=explanations(draft)
            rows.append(make_row(source,kind+'_full',answer,feedback(issues,[],'逐项核证实际证据关系；未知不变成反证，方向关系不按工具多数表决。'),'assistant constructed full-answer control'))
    assert len(rows)==55 and len({r['group'] for r in rows})==11
    public=json.loads(Path('data/monitor_net_gain_material_audit_20261021/existing_full_candidates.json').read_text(encoding='utf8'))
    system=rows[0]['messages'][0]['content']
    for row in public:
        row['task']='public_full_reference'; row['messages'][0]['content']=system
        row['label_strength']='historical assistant nonblind full review; not human gold'
    noerror=[json.loads(s) for s in Path('data/fava_mixed_v1_20261019/negative.selected512.sft.jsonl').read_text(encoding='utf8').splitlines()][:101]
    negatives=[]
    for row in noerror:
        material=json.loads(row['messages'][1]['content'])
        cards=[dict(id=c['id'],path=c['original_path'],value=c['text']) for c in material['证据卡']]
        target=feedback([], [dict(回答原文=material['待核回答'],证据ID=[c['id'] for c in cards])],'保留有据内容，不作不必要的文风修订。')
        assemble(material['待核回答'],cards,target)
        negatives.append(dict(id=row['id']+'_full_contract', group=row['group'],task='public_author_noerror_full',
            human_gold=False,label_strength=row['supervision'],target=target,
            messages=[dict(role='system',content=system),dict(role='user',content=json.dumps(dict(证据卡=cards,待核回答=material['待核回答']),ensure_ascii=False)),
                      dict(role='assistant',content=json.dumps(target,ensure_ascii=False))]))
    retention=json.loads((old/'train.json').read_text(encoding='utf8'))
    retention=[dict(deepcopy(r),task='forensic_short_retention',label_strength='explicit assistant constructed evidence-derived control') for r in retention if r['task']!='global_correct']
    combined=rows+public+negatives+retention
    assert len(combined)==345 and len({r['id'] for r in combined})==345
    assert not {r['group'] for r in rows+retention}&{'case_003','case_005','case_011','case_012','case_013','case_014','case_015','case_016','case_018','case_023','case_026','case_027','case_028','case_029','case_030'}
    OUT.mkdir(exist_ok=False)
    write(OUT/'train.candidate.json',combined)
    write(OUT/'forensic.sources.json',list(sources.values()))
    write(OUT/'material_inventory.json',dict(rows=345,forensic_full=55,forensic_unique_sources=11,public_full=101,public_noerror=101,short_retention=88,
          training_started=False,approved=False,all_existing_train_or_development=True,exposed_pilot_sources_now_training=['case_020','case_021','case_022'],
          raw_invalid_not_used=['case_017','case_019','case_024','case_025'],human_gold=False))
    print(json.dumps(dict(rows=345,forensic_full=55,public_full=202,retention=88,approved=False)))


if __name__=='__main__':
    build()
