"""Write the assistant's completed hidden-condition review and verify citations."""
from prepare import PRIVATE, load, dump, sha256, canonical_hash

# Judgments were made from full hidden copies before opening their condition mapping or GT.
NOTES = {
 1: ('partial','修正 global_forensic_analyzer 的方向为 inconclusive','撤回global的real支持；真实local保留。但CALL携带low confidence非法，且weak是降权判断而非原strength事实，联合失败。',['new_protocol_failure']),
 2: ('none','两者共同指向图像为AI生成或显著合成','非方向global又被计入fake一致综合，原数值/方向信号保留但未修复目标。',[]),
 3: ('partial','但未达校准阈值，证据权重不足','修正复制校验理由，仍把低于synthetic阈值当real证据没达标，并保留global伪冲突。',[]),
 4: ('partial','无新增工具可调用','承认弱real_like，但非法inconclusive STOP未修；新称无工具与剩余1次互补相反。',['false_budget_claim']),
 5: ('none','无剩余工具可调用','原对象/计数归因和局限未修，新增预算事实错误（尚余2）。实际图块对象描述相符，不判对象捏造。',['false_budget_claim']),
 6: ('partial','表征偏离未支持此结论','补global阈上0事实、合法CALL补到真实real/low信号；第一步仍伪冲突，最后STOP/null verdict非法，未形成合法联合修复。',[]),
 7: ('unassessable','高置信度 real 信号','合法补证及real STOP，弱local被保留；global“显著”原问题未改，新互补强度被称高置信并未保留分布变化限制。原低置信STOP是否必须补证保持未决。',['new_calibration_or_limit_omission']),
 8: ('partial','视觉与局部纹理证据冲突','复制校验提示被实质理由替换，仍把无明显伪影当反方向，global/来源缺失被并入fake综合，未完整修复。',['unsupported_synthesis']),
 9: ('unassessable','足够多类型证据支持合成判断','保持local方向/global非方向，综合却计入global与无来源；局部误报/校准不足和补证需要仍未决，不把high字样单独等同捏造概率。',[]),
10: ('unassessable','final_confidence','承认仅local方向、global非方向及局限；但CALL带fake/moderate非法，工具限制作为“冲突”概念有争议。',['new_protocol_failure']),
11: ('not_applicable','高幅度但未校准的合成倾向信号','原合理终态两方向信号保留，补充校准和未查来源，合法STOP；未误伤或额外取证，不把降低置信单算修复。',[]),
12: ('partial','但未达校准阈值，证据权重不足','行动理由已依据工具改写，阈值误解及global伪冲突仍原样保留；反馈自身错误认可这些限定。',[]),
13: ('partial','全局表征偏离与局部/互补证据存在矛盾','删除“未达停止标准”，预算0合法STOP，保留两真实方向及校准；仍说global与real矛盾，未完整去掉伪冲突。',[]),
14: ('none','四类证据一致指向AI生成','原非方向来源/视觉/global被扩写为四类一致fake，核心方向与综合仍错误。',[]),
15: ('partial','信号 real，但分数略低于阈值，强度未校准','互补校准措辞改正、真实冲突保留，local高置信仍未改；新STOP/inconclusive非法。',['new_protocol_failure']),
16: ('none','二者协同指向图像为合成','global fake与一致综合不改，88.9%全部100分位非现有汇总可完整证明，未新增返回。',[]),
17: ('partial','global_forensic_analyzer','global方向inconclusive、撤一致综合，补真实互补信号并明确分布/未校准；末步却将实际real信号写inconclusive、STOP/null verdict非法。',['new_protocol_failure','suppressed_returned_direction']),
18: ('unassessable','未达伪造判定阈值','原弱real仍保留，但新捏造global的伪造阈值概念，STOP/inconclusive非法。',['new_protocol_failure','nonexistent_global_classifier_threshold']),
19: ('none','检测到3个高偏离区域','口头称修正但具体计数/归因/解释未改，仅缺口与置信度改动；CALL带moderate非法。对象视觉真实性不判错误。',['new_protocol_failure']),
20: ('partial','视觉观察与局部纹理分析结果冲突','合法补互补real/low，最终fake/low说明低强度不足覆盖；仍保留伪视觉冲突，真实local-vs-comp冲突未完整写入unresolved，局限未完整保留。',['new_conflict_omission']),
21: ('not_applicable','局部纹理与互补模型均明确指向 fake','原合理两方向一致保持、global非方向，没有新动作或实质误伤；互补高置信仍未解释校准。',[]),
22: ('partial','所有证据均指向 real','原非法终态经互补补证恢复real/high，但引入所有证据均real的错误综合，global/来源/视觉仍未决；第一步pseudo张力来自反馈。',['unsupported_synthesis','new_calibration_or_limit_omission']),
23: ('none','二者独立且一致地指向图像为合成','global fake/与local一致及缺来源反向支持均未修正；不同流程不等于统计独立，不据此宣称机制成立。',[]),
24: ('none','三类工具均未发现伪造迹象','global依旧real，未决来源与无显著偏离被综合作真实性支持，目标未修。',[]),
25: ('none','三者一致指向AI生成','原global fake和来源缺失/local/global一致综合保留，声称不确定性最低无依据。',[]),
26: ('partial','表征严重偏离真实参考，但工具不提供真假判定','global改非方向、撤一致综合，真实补证带来local-vs-comp反方向冲突；局部高置信仍保留，STOP/inconclusive非法。',['new_protocol_failure']),
27: ('partial','互补模型给出 weak real 信号','原“缺明确方向”已承认弱local，补真实互补反方向并保留两信号；fake/low缺少取舍说明，新互补误校准/分布局限未写、R1-R3与全部区域混称仍在。',[]),
28: ('partial','不构成与real的直接冲突','预算0停因已修、明确global不是real反方向；仍先称“存在矛盾”，未完整拆分背景异常/方向冲突，故严格联合记部分。',[]),
29: ('partial','R1 区域异常可能与局部纹理信号冲突','原STOP/null通过合法CALL和fake/low修复，真实comp real方向及真正冲突保留；global伪冲突旧条目不改，强度/概率及取舍不足。',[]),
30: ('none','但无新工具可调用','预算假称无工具及来源伪冲突保留，还把中性视觉当方向冲突；补强局部取舍理由不能修复这些事实。',['new_false_visual_conflict']),
31: ('partial','区域表征偏离仅反映距离而非真假概率','global action_reason角色修复、当前真假不改；local条目仍高置信且未明确误报局限，evidence_gap无新增独立证据表述含混，严格联合非完全。',[]),
32: ('none','当前无新工具返回或调用权限','只下调置信并泛称工具限制，global fake/一致综合具体条目未改；新增无调用权限与剩余2次及可用工具矛盾。',['false_budget_claim']),
33: ('partial','局部纹理存在误报风险','补充局限/缺口但原global一致综合、对象视觉归因保留；新JSON缺少分隔符而非法，未实际返回互补工具。对象存在不判捏造。',['new_protocol_failure']),
34: ('partial','其用途不适用于当前强依赖单一未校准模态的场景','删除无工具错误、指出仅local未校准；却新捏造互补工具用途不适用，违背卡中证据较弱/不完整可补证，原缺佐证仍放conflicts。',['false_tool_applicability_claim']),
35: ('partial','且与全局偏离区域（天空/山体）吻合','补取舍及moderate，但拿无定位的局部whole-image分数说与global具体区域吻合，未校准局部/互补高置信仍在。',['unsupported_localization_alignment']),
36: ('unassessable','局部纹理强合成倾向 vs 全局偏离非AI专属、来源无凭据','合法补真实comp real/moderate并保留真冲突，标签维持fake/low；第一步新增global/来源与local伪冲突被保留、取舍及局限仍不足。',['new_false_directional_conflict']),
37: ('partial','需综合判断或继续调用工具','global direction/解释修复、校准写入缺口、真实comp real反向信号保留；budget0却留继续调用选项、STOP/null verdict非法。',['new_protocol_failure','false_budget_claim']),
38: ('unassessable','无更多独立工具可调用','global保持inconclusive，但综合被说极可能AI或深度处理，新增无独立工具与剩余1矛盾。',['false_budget_claim']),
39: ('none','无未调用工具可补充证据','原global支持fake的reason未修，非方向来源也并入一致，新增无工具与互补尚可用矛盾。',['false_budget_claim']),
40: ('partial','无新增独立工具可调用','明确local弱fake并删除原“无信号”说法；却把非方向global与local相互印证fake，并新增工具不可用假称。',['false_budget_claim','unsupported_synthesis']),
}

MONITOR = {
 1: ('supported','宜标 inconclusive','准确指出global错误real方向/一致综合，保留local；提出适用的互补建议。'),
 6: ('mostly_supported','不宜写成','格式null verdict与伪global冲突识别正确，工具/预算1正确；对confidence=null的硬要求严于冻结parser，视觉门牌只可未核实，不能判不存在。'),
 7: ('partly_supported','所有证据均无法确定','弱real与无方向区分及global0异常有依据；是否原低置信STOP必须补证仍未决，不能当独立错误gold。'),
10: ('partly_supported','高局部分数 vs 工具禁止单独定论','识别单local/校准局限，但把方法局限登记冲突不等于反方向证据；降置信后STOP与“不应单独定论”的取舍未解释。'),
11: ('mostly_supported','分数强度未校准','补充局限且允许合理终态维持；“global仅弱支持”需仅指非方向背景，非fake支持。无实质误伤。'),
12: ('incorrect','未达校准阈值、权重不足','纠正复制结构提示，但错误认可synthetic阈值低于阈值即real却权重未达标，漏/认可伪global冲突；明确“故方向选real”与不指定终标签冲突。'),
15: ('mostly_supported','说明为何采信局部纹理','实际local-vs-comp冲突及budget0正确、要求说明取舍合理；confidence=null不构成冻结parser非法，不能仅据缺confidence判推理矛盾。'),
17: ('partly_supported','方向一致但不足以无保留支撑','指出global fake及来源未决，保留局部/校准；仍把非方向global与local说“方向一致”，与自己提醒相冲突。'),
19: ('mostly_supported','只是 most_atypical_regions 的 top-3','正确区分top3与1/6阈上异常、未校准和预算2；“三个高偏离”若仅相对排序则有歧义。视觉对象确与裁片相符，不能判虚构。'),
20: ('partly_supported','视觉观察与局部纹理分析结果冲突','复制理由/单local及适用补证识别正确，但沿用未决visual当方向冲突；null confidence硬限制严于parser。'),
22: ('partly_supported','real_like 对高偏离','非法inconclusive正确发现、补证适用；要求把非方向高偏离与real_like作为conflicts张力，存在伪方向冲突风险。'),
26: ('mostly_supported','多维度证据且指向一致','识别global fake及错误一致综合，工具/预算正确；旁证措辞不得被理解为fake方向。'),
27: ('partly_supported','final_confidence 不应为 null','承认弱local方向及global无方向、补证适用，但缺confidence被当硬错误严于parser，未完整指出原“缺明确signal”及展示/全部混称。'),
28: ('partly_supported','unresolved_conflicts保留合理','识别预算0/理由自矛盾，末段提醒global非反方向；前段认可原解释与伪conflicts并称confidence不能为空，接口与语义有不一致。'),
31: ('supported','不应仅因有余额而强制调用','准确指出action_reason对global赋fake支持及字段自矛盾，保留local/误报/校准；给维持或补证选择。'),
32: ('incorrect','STOP 方向有两条工具结果支持','未撤global fake，仍声称两条工具/方向性一致，重述88.9%均100超汇总证明范围；只降置信不能完成核心审核。'),
33: ('partly_supported','属于超出返回的语义归因','指出global结合/单local/校准问题并给合法工具建议；对象与图块实际相符，工具曾向Actor返回裁片，不应将视觉内容一律判超实际可见返回。'),
34: ('supported','remaining_tool_calls=1','准确指出无工具预算事实及来源缺失非反证，保留local未校准/误报、提供合法选择。'),
36: ('partly_supported','局部纹理强合成倾向','局部/非方向global/来源限制及CALL两final为null提示正确；却强制把global未专属AI和来源缺失称方向冲突，沿用错误概念。'),
37: ('mostly_supported','建议改为区域表征异常的inconclusive证据','准确识别global fake/一致综合、真实local与局限；不必然因剩1就需要调用，当前缺独立分类证据才是理由。'),
}


def main():
    packets=load(PRIVATE/'review_packets.json')
    assert set(NOTES)==set(range(1,41)) and len(MONITOR)==20
    rows={}
    citations=[]
    for i,(repair,quote,note,new) in NOTES.items():
        rid='review_'+str(i).zfill(2)
        packet=packets[rid]
        matches=[j for j,s in enumerate(packet['new_steps']) if quote in s['raw']]
        assert matches,(rid,quote)
        ref={'review_id':rid,'pointer':f'/new_steps/{matches[-1]}/raw','quote':quote}
        citations.append(ref)
        rows[rid]={'case':packet['case_id'],'repair':repair,'full_joint_repair':False,'assessment':note,'new_issue_tags':new,
             'protocol_status':packet['terminal']['status'],'actor_citations':[ref],
             'valid_return_facts_preserved':'numerical score/signal checked in full raw; exceptions stated in assessment',
             'image_object_truth_not_inferred_from_text':True,'review_packet_sha256':canonical_hash(packet)}
        if i in MONITOR:
            state,mquote,mnote=MONITOR[i]
            assert mquote in packet['external_message'],(rid,mquote)
            mref={'review_id':rid,'pointer':'/external_message','quote':mquote}
            citations.append(mref)
            rows[rid]['monitor_review']={'assessment_state':state,'assessment':mnote,'citation':mref}
    for ref in citations:
        value=packets[ref['review_id']]
        for key in ref['pointer'].strip('/').split('/'):
            value=value[int(key)] if isinstance(value,list) else value[key]
        assert ref['quote'] in value
    # Tool facts and restrictions are independently quote-checked in every packet.
    for rid,p in packets.items():
        card=p['original']['tool_cards']['global_forensic_analyzer']['limitations']
        assert '不返回 real/fake signal' in card and '不是假图概率' in card
        assert p['original']['budget']['remaining_tool_calls'] in [0,1,2]
    review={'reviewer':'same assistant; hidden condition identifiers, not truly blind or independent gold','gt_read':False,
      'criteria_sha256':sha256(PRIVATE/'review_criteria.json'),'cases':rows,
      'disputes':['高置信字样本身不单判捏造概率，工具强度/最终置信/校准依据分开。',
        'blind_001三个高偏离可能指top3排序，不能直接断言数目造假；1/6阈上异常应明确。冻结预审不改，结果按争议处理。',
        'blind_001 R1-R3天空/方尖碑/云层、blind_010 R1门牌、blind_015 R1-R3塔楼/屋顶与裁片相符；Actor曾收到裁片，Monitor没有像素，只能标未核实，不能判对象不存在。',
        'STOP final_confidence=null在冻结schema及原parser允许；新增提示要求low/moderate/high较严格。反馈不能把缺confidence本身当原格式非法。',
        '缺独立佐证、方法局限和非方向偏离的背景张力，不等于相反real/fake工具信号。',
        '不强制用尽额度；评价的是预算事实和建议依据，非未调用即错误。'],
      'visual_checks':{'assets_viewed':['blind_001_R1.png','blind_001_R2.png','blind_001_R3.png','blind_010_R1.png','blind_015_R1.png','blind_015_R2.png','blind_015_R3.png'],
            'all_other_visual_object_claims':'not independently pixel-audited; retained unassessable, not declared fabricated'},
      'all50_new_actions_read':True,'all20_feedback_read':True,'case_count':40,'monitor_count':20}
    dump(PRIVATE/'semantic_review.json',review)
    dump(PRIVATE/'citation_verification.json',{'exact_quotes_verified':len(citations),'quotes':citations,'tool_limit_and_budget_packets_checked':40,'passed':True,
          'full_raw_time_boundary_verification':load(PRIVATE/'raw_output_lock.json')['full_input_time_boundary_check']})
    names=['semantic_review.json','citation_verification.json','review_packets.json','review_criteria.json','preaudit.json']
    dump(PRIVATE/'semantic_review_lock.json',{'complete':True,'gt_read':False,'files':{n:sha256(PRIVATE/n) for n in names},
          'raw_lock_sha256':sha256(PRIVATE/'raw_output_lock.json'),'hidden_condition_mapping_opened_for_adjudication':False})
    print('40 hidden branch reviews / 20 feedback reviews locked; 60 quotes verified; GT not read')


if __name__=='__main__':
    main()
