"""Save transparent non-blind review of three actual outputs; never repairs raw."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pilot


def main():
    package = pilot.verify(pilot.PRIVATE)
    backup = pilot.PRIVATE / 'backup'
    hashes = json.loads((pilot.PRIVATE / 'backup_hashes.json').read_text(encoding='utf-8'))
    for name, digest in hashes.items():
        assert pilot.sha256(backup / name) == digest, name
    before = json.loads((backup / 'protection_before.json').read_text(encoding='utf-8'))
    after = json.loads((backup / 'protection_after.json').read_text(encoding='utf-8'))
    assert before == after and len(before) == 25
    cpu = json.loads((pilot.PRIVATE / 'cpu_preflight.json').read_text(encoding='utf-8'))
    deployed = json.loads((backup / 'deployment_preflight.json').read_text(encoding='utf-8'))
    generated_cpu = json.loads((backup / 'output/preflight.json').read_text(encoding='utf-8'))
    for key in ['branches', 'input_ids_sha256', 'processor_assets', 'blinded_pre_stop_tokens']:
        assert cpu[key] == deployed[key] == generated_cpu[key], key
    original = json.loads((pilot.PRIVATE / 'case.json').read_text(encoding='utf-8'))['steps'][-1]['actor_output']
    outputs = {arm: json.loads((backup / 'output' / (arm + '.json')).read_text(encoding='utf-8')) for arm in ('R', 'G', 'T')}
    reviews = []
    for arm, result in outputs.items():
        parsed = pilot.parse_action(result['raw'], set(package['used_tools']))
        assert parsed == result['parsed'] and result['parse_error'] is None and not result['at_token_limit']
        assert [item['observation'] for item in parsed['current_evidence']] == [item['observation'] for item in original['current_evidence']]
        local = next(item for item in parsed['current_evidence'] if item['source'] == 'local_texture_analyzer')
        global_item = next(item for item in parsed['current_evidence'] if item['source'] == 'global_forensic_analyzer')
        targeted = arm == 'T'
        reviews.append({
            'arm': arm, 'reviewer_type': 'agent', 'review_is_blind': False,
            'target_error_repaired': targeted,
            'target_repair_reason': '全局direction改为inconclusive，interpretation保留替代解释，action_reason/evidence_gap撤回三项一致支持。' if targeted else '全局direction仍fake，action_reason继续把来源缺失与非方向偏离纳入一致真假支持。',
            'valid_evidence_preserved': False,
            'valid_evidence_preservation_status': 'partial',
            'valid_evidence_reason': '真实局部score/signal/observation均保留。T在action_reason保留误报风险，但三臂均未明确保留强度未经校准限制；局部interpretation仍写高置信度。该措辞不单独判为捏造概率，按预设“保留局限”要求判该维度未完整通过。',
            'local_signal_retained': local['direction'] == 'fake',
            'false_positive_risk_retained': targeted,
            'uncalibrated_strength_explicitly_retained': False,
            'no_new_error_detected': True,
            'no_new_error_reason': '四项observation与原提议逐项一致；未新增数值、工具返回、对象或证明真实的推断。T新增解释与已有工具局限一致。仅对本次已审核字段作此判断，不断言原视觉描述正确或完全无旧问题。',
            'action_executable': True,
            'action_reason': '原parser通过。T仅提议未使用互补工具，剩余额度1，final字段null；R/G合法STOP。合法性不等于停止充分性或补证据效果。',
            'complete_local_repair': False,
            'primary_target_only_success': targeted,
            'quotes': {'action_reason': parsed['action_reason'], 'global_interpretation': global_item['interpretation'],
                       'global_direction': global_item['direction'], 'local_interpretation': local['interpretation'],
                       'evidence_gap': parsed['evidence_gap']},
            'next_action': parsed['next_action'], 'selected_tool': parsed['selected_tool'],
            'final_verdict': parsed['final_verdict'], 'final_confidence': parsed['final_confidence'],
            'input_tokens': result['input_tokens'], 'output_tokens': result['output_tokens'], 'seconds': result['seconds']})
    pilot.dump(pilot.PRIVATE / 'semantic_review.json', {'date': '2026-10-11', 'independent_human_reviews': 0,
        'reviewer_type': 'agent', 'review_is_blind': False, 'criteria_source': 'approved plan section 7',
        'reviews': reviews, 'GT_read': False, 'raw_modified': False,
        'conclusion': '具体反馈修复本例主要证据角色错误并改变下一步提议，R/G未修复；局部证据校准限制未完整保留，因此完整联合修复三臂均未通过。不据此断言最终检测收益或自动Monitor有效。'})
    runtime = json.loads((backup / 'output/completed.json').read_text(encoding='utf-8'))
    runtime.update(date='2026-10-11', order=package['order'], model_requests=3,
                   pure_generation_seconds=sum(row['seconds'] for row in outputs.values()),
                   output_tokens=sum(row['output_tokens'] for row in outputs.values()),
                   old_protection_files_unchanged=25, processor_inputs_match_prepared=True,
                   GPU_exit_verified=True, GPU_at_exit='0 MiB, 0 %',
                   semantic_review_type='same agent non-blind', backup_files=len(hashes))
    pilot.dump(pilot.PRIVATE / 'runtime.json', runtime)
    pilot.dump(pilot.PRIVATE / 'transfer_issue.json', {
        'step': 'local backup verification', 'error': 'NameError: hashlib import missing in gpu_control.py',
        'residual_state': 'empty backup/output directory; no output file had been written',
        'resolution': 'Deployed controller preserved as gpu_control_deployed.py; added import and allowed only empty backup directory. Read-only fetch retried and 11 files hash-verified.',
        'additional_model_requests': 0, 'remote_result_modified': False})
    final = {'input_freeze_verified': True, 'old_source_sha256_unchanged': pilot.sha256(pilot.SOURCE) == pilot.EXPECTED['source'],
             '25_protection_files_unchanged': True, 'backup_hashes_verified': 11,
             'files': {p.relative_to(pilot.PRIVATE).as_posix(): pilot.sha256(p) for p in pilot.PRIVATE.rglob('*') if p.is_file()},
             'scripts': {p.name: pilot.sha256(p) for p in Path(__file__).parent.glob('*.py')}}
    pilot.dump(pilot.PRIVATE / 'final_audit.json', final)
    print(json.dumps({'target_error_repaired': {'R': False, 'G': False, 'T': True},
                      'complete_local_repair': {'R': False, 'G': False, 'T': False},
                      'runtime': runtime, 'review_sha256': pilot.sha256(pilot.PRIVATE / 'semantic_review.json')}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
