"""Verify a small set of explicit field witnesses; never infer prose correctness."""
from copy import deepcopy


def verify(action, cards, proposal):
    def result(status, reason, **data):
        return dict(status=status, reason=reason, patch=None, semantic_coverage='explicit_fields_only', **data)
    if not isinstance(proposal, dict):
        return result('rejected', '异议必须是结构化对象')
    known = {c['id']: c['value'] for c in cards}
    if len(known) != len(cards):
        return result('rejected', '原始证据ID重复')
    rule = proposal.get('rule')
    if rule == 'global_direction':
        if set(proposal) != {'rule', 'evidence_id', 'actor_index', 'observed', 'proposed'}:
            return result('rejected', '字段见证不完整')
        index = proposal['actor_index']
        if type(index) is not int or not 0 <= index < len(action['current_evidence']):
            return result('rejected', 'Actor字段定位无效')
        item = action['current_evidence'][index]
        if not isinstance(proposal['evidence_id'], str):
            return result('rejected', '证据ID必须是字符串')
        evidence = known.get(proposal['evidence_id'])
        if item['source'] != 'global_forensic_analyzer' or not isinstance(evidence, dict) or evidence.get('tool') != item['source']:
            return result('rejected', '引用工具与Actor对象不一致')
        if proposal['observed'] != item['direction']:
            return result('rejected', '声明的原值与Actor记录不一致')
        if proposal['proposed'] not in ('none', 'inconclusive'):
            return result('rejected', '非方向证据不能修成真假方向')
        if item['direction'] in ('none', 'inconclusive'):
            return result('already_valid', '原字段已为非方向值，不证明存在错误')
        if item['direction'] not in ('real', 'fake'):
            return result('unresolved', '原字段取值不在本轮规则覆盖范围')
        return dict(status='verified_repair', reason='global被显式赋予真假方向，与冻结非方向规则冲突',
                    patch={'path': ['current_evidence', index, 'direction'], 'old': item['direction'], 'new': proposal['proposed']},
                    semantic_coverage='explicit_fields_only')
    if rule == 'signal_relation':
        if set(proposal) != {'rule', 'evidence_ids', 'claim'}:
            return result('rejected', '信号关系见证不完整')
        refs = proposal['evidence_ids']
        if not isinstance(refs, list) or len(refs) != 2 or any(not isinstance(r, str) or r not in known for r in refs) or refs[0] == refs[1]:
            return result('rejected', '必须引用两个不同的真实工具返回')
        returns = [known[r] for r in refs]
        if any(not isinstance(v, dict) for v in returns) or {v.get('tool') for v in returns} != {'local_texture_analyzer', 'complementary_forensic_analyzer'}:
            return result('rejected', '仅覆盖局部与互补原始信号比较')
        direction = {'synthetic_like': 'synthetic', 'fake': 'synthetic', 'real_like': 'authentic', 'real': 'authentic'}
        values = [direction.get(v.get('signal')) for v in returns]
        if None in values:
            return result('unresolved', '缺失或未知信号不等于没有冲突')
        actual = 'opposed' if values[0] != values[1] else 'same'
        if proposal['claim'] not in ('opposed', 'same'):
            return result('rejected', '关系只能声明同向或相反')
        if proposal['claim'] != actual:
            return result('rejected_false_assertion', '异议中的信号关系断言与实际返回相反', actual_relation=actual)
        return result('verified_fact_only', '只证明原始信号关系；未证明原稿错误，不授权修改', actual_relation=actual)
    if rule == 'stop_enum':
        if set(proposal) != {'rule', 'observed'} or action.get('next_action') != 'STOP' or proposal['observed'] != action.get('final_verdict'):
            return result('rejected', '终态原值见证不匹配')
        if action['final_verdict'] in ('real', 'fake'):
            return result('already_valid', '枚举合法，不证明真假结论正确')
        return result('unresolved_protected_field', '终态枚举有错，但当前不授权选择或翻转真假标签')
    return result('unresolved', '规则不在当前明确字段覆盖范围，不猜测自由文本语义')


def apply_verified(action, cards, proposal):
    checked = verify(action, cards, proposal)
    candidate = deepcopy(action)
    if checked['status'] == 'verified_repair':
        patch = checked['patch']
        candidate['current_evidence'][patch['path'][1]]['direction'] = patch['new']
    return dict(verification=checked, candidate_action=candidate,
                explanation_synchronized=False, ready_for_publication=False)
