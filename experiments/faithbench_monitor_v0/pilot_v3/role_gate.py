"""Explicit source-direction contract checks; no guesses about image content."""
from protocol import evidence_catalog
from claim_verify import verification_input


def source_role(observation):
    if observation.get('evidence_type') == 'representation_deviation':
        return {'kind':'non_directional','direction':None,'basis':'evidence_type'}
    signal=observation.get('signal')
    if signal in ['real','real_like']:
        return {'kind':'directional','direction':'real','basis':'signal'}
    if signal in ['fake','synthetic_like']:
        return {'kind':'directional','direction':'fake','basis':'signal'}
    if signal=='inconclusive':
        return {'kind':'inconclusive','direction':None,'basis':'signal'}
    return {'kind':'unknown','direction':None,'basis':None}


def direction_gate(packet):
    data=verification_input(packet);catalog=evidence_catalog(packet)
    ledger=packet['runtime_snapshot']['evidence_ledger']
    violations=[];roles=[]
    def ids_for(pointer):
        return [eid for eid,ref in catalog.items() if ref['pointer']==pointer]
    for item in data['claims']:
        source=item['source']
        if source=='visual':continue
        prior=[r for r in ledger if r['source']==source and r['returned_after_step']<item['decision_step']]
        if not prior:continue
        evidence=prior[-1];role=source_role(evidence['observation'])
        declared=item['actor_claim'].get('direction')
        basis=evidence['observation_ref']+'/'+role['basis'] if role['basis'] else None
        refs=list(item['claim_ids'])+ids_for(basis)+item['source_card_ids']
        roles.append({'claim_id':item['claim_id'],'source':source,'decision_step':item['decision_step'],
                      'role':role,'declared_direction':declared,'reference_ids':refs})
        # A source-specific direction contradicts its explicit return role.
        # Inconclusive is allowed as cautious weakening of a directional signal.
        if declared in ['real','fake'] and role['kind']!='unknown' and declared!=role['direction']:
            explanation=(f"Actor在步骤{item['decision_step']}给来源{source}赋予{declared}方向，"
                         f"但该时刻以前实际返回角色为{role['kind']}，方向为{role['direction'] or '无真假方向'}。"
                         "这是来源方向字段与工具返回契约不一致；不据此判断图像真假或视觉内容。")
            violations.append({'claim_id':item['claim_id'],'source':source,'failure_type':'attribution_error',
                               'explanation':explanation,'reference_ids':list(dict.fromkeys(refs))})
    return {'source_roles':roles,'violations':violations,'visual_truth_checked':False,
            'rule':'explicit_visible_source_direction_contract_only','model_calls':0}
