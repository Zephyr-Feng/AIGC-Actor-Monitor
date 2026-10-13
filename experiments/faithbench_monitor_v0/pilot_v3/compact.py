"""Compact source relations with per-obligation citation choices."""
import json
from protocol import BASE,obj,evidence_catalog
from focused import focused_input,validate_focused,relation_flags,final_schema,parse_focused
from hybrid import contract_records
from role_gate import source_role
from experiments.faithbench_monitor_v0.pilot_v2.protocol import render_request


def compact_schema(data):
    text={'type':'string','minLength':1};atoms={}
    for a in data['observation_atoms']:
        source_ids=list(dict.fromkeys(eid for p in a['prior_returns'] for eid in p['observation_ids']))
        refs={'type':'array','items':{'type':'string','enum':source_ids},'minItems':1} if source_ids else {'type':'array','items':{'type':'string'},'maxItems':0}
        atoms[a['atom_id']]=obj({'status':{'type':'string','enum':['supported_by_source','not_returned_by_source','unassessable'] if source_ids else ['unassessable']},
            'reason':text,'source_reference_ids':refs})
    slots={}
    for s in data['conflict_slots']:
        names=list(s['prior_source_roles']);name={'type':'string','enum':names} if names else {'type':'string'}
        slots[s['slot_id']]=obj({'pairs':{'type':'array','items':obj({'left':name,'right':name,'type':{'type':'string','enum':['direction_conflict','other_tension','unclear']}}),'maxItems':3 if len(names)>1 else 0},'reason':text})
    return obj({'observations':obj(atoms),'conflicts':obj(slots)})


def compile_relations(raw,data):
    result=json.loads(raw);compiled={'observations':{},'conflicts':{}}
    if set(result['observations'])!={a['atom_id'] for a in data['observation_atoms']} or set(result['conflicts'])!={s['slot_id'] for s in data['conflict_slots']}:
        raise ValueError('compact relation scope mismatch')
    for a in data['observation_atoms']:
        r=result['observations'][a['atom_id']];source_ids=r['source_reference_ids']
        compiled['observations'][a['atom_id']]={'status':r['status'],'reason':r['reason'],
            'reference_ids':list(dict.fromkeys(a['claim_reference_ids']+source_ids))}
    for s in data['conflict_slots']:
        r=result['conflicts'][s['slot_id']];ids=list(s['actor_reference_ids'])
        for pair in r['pairs']:
            for name in [pair['left'],pair['right']]:
                if name not in s['prior_source_roles']:raise ValueError('source absent at conflict time')
                ids.extend(s['prior_source_roles'][name]['reference_ids'])
        compiled['conflicts'][s['slot_id']]={**r,'reference_ids':list(dict.fromkeys(ids))}
    return validate_focused(json.dumps(compiled,ensure_ascii=False),data)


def final_prompt(packet,data,verified,flags):
    original=render_request(packet);marker='代码计算的审核范围与执行条件'
    gate,records=contract_records(packet)
    atoms=[{'atom_id':a['atom_id'],'text':a['text'],'claim_reference_ids':a['claim_reference_ids']} for a in data['observation_atoms']]
    conflicts=[{'slot_id':s['slot_id'],'text':s['text'],'actor_reference_ids':s['actor_reference_ids'],
                'prior_source_roles':{k:v['role'] for k,v in s['prior_source_roles'].items()}} for s in data['conflict_slots']]
    compact_flags={k:{'kind':v['kind'],
                      'location_id':v.get('atom',v.get('slot',{})).get('atom_id',v.get('slot',{}).get('slot_id')),
                      'pair':v.get('pair')} for k,v in flags.items()}
    current_roles={e['source']:source_role(e['observation']) for e in packet['runtime_snapshot']['evidence_ledger']}
    controls={'code_contract_records':records,'latest_visible_source_roles':current_roles,
              'visual_audit_limit':data['visual_text_audit'],'atomic_index':atoms,'conflict_index':conflicts,
              'fallible_relations':verified,'flagged_relations':compact_flags}
    instructions=(BASE/'focused_aggregation.md').read_text(encoding='utf8')
    return '\n\n'.join([instructions,(BASE.parent/'ANNOTATION_GUIDELINES.md').read_text(encoding='utf8'),
        '明示契约及可推翻核验索引（不是独立证据）：\n'+json.dumps(controls,ensure_ascii=False),original[original.index(marker):]])


def verifier_prompt(data):
    instructions=(BASE/'focused_verifier.md').read_text(encoding='utf8')
    override='本轮compact接口：observations仅写status/reason/source_reference_ids，引用只选本片段同源prior_returns的原始编号；Actor片段原始编号由程序绑定。conflicts仅写pairs/reason，来源对的角色字段与Actor原始叶子引用由程序绑定。不生成reference_ids，不引用其他片段来源，不把程序绑定算成模型独立证据。'
    return instructions+'\n'+override+'\n输入：\n'+json.dumps(data,ensure_ascii=False)


def planning_prompt(packet,data):
    # Conservative allowance: relation JSON may use the full 4096-token stage budget.
    empty={'observations':{},'conflicts':{}}
    return final_prompt(packet,data,empty,{})
