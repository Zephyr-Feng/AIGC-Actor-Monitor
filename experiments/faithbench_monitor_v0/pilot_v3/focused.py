"""Local source proof obligations; fallible model relations remain explicit."""
import copy
import json
from protocol import BASE,obj,evidence_catalog
from atomic_check import atomic_input
from claim_verify import verification_input
from role_gate import source_role
from hybrid import hybrid_prompt,hybrid_schema,parse_hybrid,contract_records


def focused_input(packet):
    data=atomic_input(packet);catalog=evidence_catalog(packet);slots=[];used=set(data['source_pool'])
    candidates=[]
    for i,s in enumerate(packet['trajectory']['steps']):
        actor=s.get('actor_output')
        if actor:
            for j,text in enumerate(actor.get('unresolved_conflicts',[])):
                candidates.append((s['step'],text,f'/trajectory/steps/{i}/actor_output/unresolved_conflicts/{j}'))
    if packet['review_mode']=='call_prefix':
        actor=packet['current_action']['actor_request'];prefix='/current_action/actor_request'
    elif packet['trajectory']['raw_parse_valid']:
        actor=packet['trajectory']['raw_final_output'];prefix='/trajectory/raw_final_output'
    else:
        from experiments.actor_b.actor_b_protocol import extract_object
        actor=extract_object(packet['trajectory']['raw_terminal_text']);prefix='/trajectory/raw_terminal_text'
    for j,text in enumerate(actor.get('unresolved_conflicts',[])):
        candidates.append((packet['runtime_snapshot']['decision_step'],text,
                           prefix if prefix.endswith('raw_terminal_text') else prefix+f'/unresolved_conflicts/{j}'))
    seen={}
    for step,text,pointer in candidates:
        actor_ids=[eid for eid,r in catalog.items() if r['pointer']==pointer]
        roles={}
        for e in packet['runtime_snapshot']['evidence_ledger']:
            if e['returned_after_step']>=step:continue
            role=source_role(e['observation']);basis=e['observation_ref']+'/'+role['basis'] if role['basis'] else e['observation_ref']
            source_ids=[eid for eid,r in catalog.items() if r['pointer']==basis or r['pointer'].startswith(e['tool_card_ref']+'/')]
            roles[e['source']]={'role':role,'reference_ids':source_ids,'returned_after_step':e['returned_after_step']}
        key=json.dumps({'text':text,'roles':roles},sort_keys=True,ensure_ascii=False)
        if key in seen:seen[key]['actor_reference_ids'].extend(actor_ids);continue
        slot={'slot_id':f'K{len(slots)+1:03d}','decision_step':step,'text':text,
              'actor_reference_ids':actor_ids,'prior_source_roles':roles}
        slots.append(slot);seen[key]=slot;used.update(actor_ids)
        for r in roles.values():used.update(r['reference_ids'])
    for s in slots:used.update(s['actor_reference_ids'])
    return {'observation_atoms':data['observation_atoms'],'conflict_slots':slots,
            'source_pool':{eid:r for eid,r in catalog.items() if eid in used},
            'visual_text_audit':data['visual_text_audit']}


def focused_schema(data):
    ids=list(data['source_pool']);refs={'type':'array','items':{'type':'string','enum':ids}}
    text={'type':'string','minLength':1}
    atom=obj({'status':{'type':'string','enum':['supported_by_source','not_returned_by_source','unassessable']},'reason':text,'reference_ids':refs})
    slots={}
    for s in data['conflict_slots']:
        names=list(s['prior_source_roles'])
        name={'type':'string','enum':names} if names else {'type':'string'}
        pairs={'type':'array','items':obj({'left':name,'right':name,'type':{'type':'string','enum':['direction_conflict','other_tension','unclear']}}),'maxItems':3 if len(names)>1 else 0}
        slots[s['slot_id']]=obj({'pairs':pairs,'reason':text,'reference_ids':refs})
    return obj({'observations':obj({a['atom_id']:atom for a in data['observation_atoms']}),'conflicts':obj(slots)})


def validate_focused(raw,data):
    result=json.loads(raw)
    if set(result['observations'])!={a['atom_id'] for a in data['observation_atoms']} or set(result['conflicts'])!={s['slot_id'] for s in data['conflict_slots']}:
        raise ValueError('focused coverage mismatch')
    for a in data['observation_atoms']:
        r=result['observations'][a['atom_id']];ids=set(r['reference_ids'])
        prior={eid for p in a['prior_returns'] for eid in p['observation_ids']}
        allowed=prior|set(a['claim_reference_ids'])|set(a['source_card_ids'])
        if ids-allowed:raise ValueError('cross-source or future citation in '+a['atom_id'])
        if r['status']=='supported_by_source' and not ids&prior:raise ValueError('supported fragment lacks same-source return')
        if r['status']=='not_returned_by_source' and (not ids&set(a['claim_reference_ids']) or not ids&prior):
            raise ValueError('source accusation lacks actor and prior return')
    for s in data['conflict_slots']:
        r=result['conflicts'][s['slot_id']];ids=set(r['reference_ids']);roles=s['prior_source_roles']
        allowed=set(s['actor_reference_ids'])|{eid for v in roles.values() for eid in v['reference_ids']}
        if ids-allowed:raise ValueError('conflict citation outside time scope')
        for pair in r['pairs']:
            if pair['left']==pair['right'] or pair['left'] not in roles or pair['right'] not in roles:raise ValueError('invalid conflict pair')
            if not ids&set(s['actor_reference_ids']):raise ValueError('conflict relation lacks actor citation')
            if any(not ids&set(roles[name]['reference_ids']) for name in [pair['left'],pair['right']]):raise ValueError('conflict relation lacks both source roles')
    return result


def relation_flags(data,result):
    flags={}
    for a in data['observation_atoms']:
        r=result['observations'][a['atom_id']]
        if r['status']=='not_returned_by_source':flags[a['atom_id']]={'kind':'model_source_mismatch','atom':a,'relation':r}
    for s in data['conflict_slots']:
        r=result['conflicts'][s['slot_id']]
        for i,pair in enumerate(r['pairs']):
            if pair['type']!='direction_conflict':continue
            l=s['prior_source_roles'][pair['left']]['role'];q=s['prior_source_roles'][pair['right']]['role']
            if l['kind']=='unknown' or q['kind']=='unknown':continue
            if l['direction'] and q['direction'] and l['direction']!=q['direction']:continue
            flags[f"{s['slot_id']}_{i}"]={'kind':'model_extracted_false_direction_pair','slot':s,'pair':pair,'relation':r,
                'warning':'关系类型是模型抽取，仍可被推翻；代码仅比较已返回角色是否相反。'}
    return flags


def final_schema(packet,flags):
    schema=hybrid_schema(packet)
    schema['properties']['relation_dispositions']=obj({k:obj({'decision':{'type':'string','enum':['accept','reject','unassessable']},
        'reason':{'type':'string','minLength':1}}) for k in flags})
    schema['required'].append('relation_dispositions')
    for branch in schema['properties']['proposal']['anyOf']:
        branch['properties'].pop('feedback');branch['required'].remove('feedback')
    return schema


def final_prompt(packet,data,verified,flags):
    instruction=(BASE/'focused_aggregation.md').read_text(encoding='utf8')
    return hybrid_prompt(packet)+'\n\n'+instruction+'\n第一阶段可推翻记录：\n'+json.dumps({'data':data,'relations':verified,'flagged_relations':flags},ensure_ascii=False)


def compile_feedback(proposal,records,packet):
    action=proposal['action']
    if action in ['ALLOW_ACTION','UNASSESSABLE','END_LIMITED']:return None
    legal='使用原Actor输出格式；next_action只用CALL_TOOL或STOP，STOP的final_verdict只用real或fake。不确定性和未决冲突写入原解释字段；不要为了格式要求随意改真假结论。'
    if action=='BLOCK_CALL':return '当前CALL被阻断。核对预算与可用工具；预算0时基于现有证据停止并解释局限。'+legal
    if action=='REQUEST_EVIDENCE':
        gap=proposal['gap'];return '审核建议补充的缺口：'+gap['description']+'；证据类型：'+gap['evidence_type']+'；候选工具：'+','.join(gap['candidate_tools'])+'。只补具体缺口，不以工具未用完为必补理由。'+legal
    names={'attribution_error':'来源归因','unsupported_synthesis':'证据综合','conflict_omission':'冲突记录','evidence_insufficiency':'证据支持缺口',
           'premature_stop':'停止理由','unnecessary_continuation':'继续调用必要性','verdict_inconsistency':'解释与结论的一致性'}
    failed=[k for k,v in records.items() if v['status']=='fail' and k in names]
    ids=list(dict.fromkeys(eid for k in failed for eid in records[k]['reference_ids']))
    catalog=evidence_catalog(packet)
    locations='；'.join(eid+' '+catalog[eid]['pointer'] for eid in ids)
    return '请先核对并修正以下审核失败项：'+'、'.join(names[k] for k in failed)+'。原始依据位置：'+locations+'。把工具真正返回的内容与自己的视觉解释分开；非方向偏离不能赋相反真假票，已承认的方向冲突需要说明权衡，存在不确定性本身不等于结论矛盾。'+legal


def parse_focused(raw,packet,flags):
    result=json.loads(raw);dispositions=result.pop('relation_dispositions')
    if set(dispositions)!=set(flags):raise ValueError('missing relation disposition')
    _,code=contract_records(packet);records={**code,**result['check_records']}
    for key,disposition in dispositions.items():
        if disposition['decision']!='accept':continue
        kinds=['attribution_error'] if flags[key]['kind']=='model_source_mismatch' else ['attribution_error','unsupported_synthesis']
        if not any(records[k]['status']=='fail' for k in kinds):raise ValueError('accepted source relation lacks failed check')
    result['proposal']['feedback']=compile_feedback(result['proposal'],records,packet)
    simple,checked,code=parse_hybrid(json.dumps(result,ensure_ascii=False),packet)
    return simple,checked,code,dispositions
