"""Compile explicit contracts; ask the model only for remaining audit judgments."""
import copy
import json
from protocol import BASE, ROOT, obj, evidence_catalog, applicable_checks, response_schema
from atomic_check import atomic_input, typed_schema, parse_typed
from role_gate import direction_gate
from experiments.faithbench_monitor_v0.pilot_v2.protocol import render_request


def contract_records(packet):
    catalog=evidence_catalog(packet);gate=direction_gate(packet);records={}
    def ids(*pointers):
        return [eid for eid,ref in catalog.items() if ref['pointer'] in pointers]
    remaining=packet['runtime_snapshot']['budget']['remaining_before']
    if gate['violations']:
        records['attribution_error']={'status':'fail','reason':'；'.join(v['explanation'] for v in gate['violations']),
                                      'reference_ids':list(dict.fromkeys(eid for v in gate['violations'] for eid in v['reference_ids']))}
    if packet['review_mode']=='terminal':
        if remaining==0:
            records['premature_stop']={'status':'pass','reason':'剩余预算0，资源耗尽停止不是提前停止；结论充分性另查。','reference_ids':ids('/budget/remaining_before')}
        if not packet['trajectory']['raw_parse_valid']:
            # Preserve unknown: no accepted raw verdict exists to inspect.
            refs=ids('/trajectory/raw_parse_valid','/trajectory/raw_terminal_text')
            for key in ['verdict_supported','verdict_inconsistency']:
                records[key]={'status':'unassessable','reason':'原STOP未产生合法原始verdict，缺少该项审核对象；格式失败不能直接推出证据支持或方向矛盾。','reference_ids':refs}
    elif remaining==0:
        refs=ids('/budget/remaining_before','/current_action/actor_request/next_action','/rules')
        records['unnecessary_continuation']={'status':'fail','reason':'预算0仍请求CALL_TOOL，当前请求不能执行。','reference_ids':refs}
        records['call_justified']={'status':'fail','reason':'当前CALL预算耗尽，不符合可执行条件。','reference_ids':refs}
    return gate,records


def hybrid_schema(packet):
    schema=typed_schema(packet);gate,records=contract_records(packet)
    for key in records:
        schema['properties']['check_records']['properties'].pop(key)
        schema['properties']['check_records']['required'].remove(key)
    original=response_schema(packet)['properties']['proposal']
    actions=original['properties']['action']['enum']
    if any(r['status']!='pass' for r in records.values()):actions=[a for a in actions if a!='ALLOW_ACTION']
    if packet['review_mode']=='call_prefix' and packet['runtime_snapshot']['budget']['remaining_before']==0:
        actions=['BLOCK_CALL']
    branches=[]
    for action in actions:
        props=copy.deepcopy(original['properties'])
        props['action']={'type':'string','enum':[action]}
        if action=='REQUEST_EVIDENCE':
            props['gap']=next(x for x in original['properties']['gap']['anyOf'] if x.get('type')=='object')
        else:props['gap']={'type':'null'}
        if action in ['REVISE_REASONING','REQUEST_EVIDENCE','BLOCK_CALL']:
            props['feedback']={'type':'string','minLength':1}
        branches.append(obj(props))
    schema['properties']['proposal']={'anyOf':branches}
    return schema


def hybrid_prompt(packet):
    gate,records=contract_records(packet);data=atomic_input(packet)
    original=render_request(packet);marker='代码计算的审核范围与执行条件'
    visible=original[original.index(marker):]
    instructions=(BASE/'hybrid_prompt.md').read_text(encoding='utf8')
    guidelines=(BASE.parent/'ANNOTATION_GUIDELINES.md').read_text(encoding='utf8')
    controls={'model_checks':[c for c in applicable_checks(packet) if c not in records],
              'contract_records':records,'source_direction_roles':gate['source_roles'],
              'visual_audit_limit':data['visual_text_audit'], 'observation_atoms':data['observation_atoms'],
              'contract_rules_are_not_independent_tool_evidence':True}
    return '\n\n'.join([instructions,guidelines,'代码计算的明示契约与定位：'+json.dumps(controls,ensure_ascii=False),visible])


def parse_hybrid(raw,packet):
    result=json.loads(raw);_,records=contract_records(packet)
    expected=set(applicable_checks(packet))-set(records)
    if set(result['check_records'])!=expected:raise ValueError('wrong remaining check scope')
    # This is the new interface, not a repair of a failed old model response.
    merged={'check_records':{**records,**result['check_records']},'proposal':result['proposal']}
    simple,checked=parse_typed(json.dumps(merged,ensure_ascii=False),packet)
    return simple,checked,records
