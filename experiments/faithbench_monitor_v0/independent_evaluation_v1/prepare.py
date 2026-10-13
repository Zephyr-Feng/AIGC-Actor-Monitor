"""Prepare existing calibration references and a bounded inventory; no inference."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'experiments/faithbench_monitor_v0/private'
OLD = BASE / 'model_comparison_v1_20261012'
FULL = BASE / 'deepseek_monitor_actor_v1_20261012'
OUT = BASE / 'independent_evaluation_v1_20261013'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    assert not OUT.exists(), 'Existing preparation must not be overwritten'
    sources = [OLD / 'packets.json', OLD / 'criteria.json', OLD / 'freeze.json',
               BASE / 'manifest.json', FULL / 'group_inventory.json',
               FULL / 'exposure_inventory.json', FULL / 'api/blind_027/response.json',
               ROOT / 'experiments/actor_b/actor_b0_d/audit_assist/AGENT_AUDIT_REPORT.md',
               ROOT / 'docs/PROJECT_PROGRESS.md',
               ROOT / 'docs/research/DEEPSEEK_MONITOR_INDEPENDENT_EVALUATION_PLAN_20261013.md',
               Path(__file__)]
    before = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sources}
    frozen = json.loads((OLD / 'freeze.json').read_text(encoding='utf-8'))
    for name in ('packets.json', 'criteria.json'):
        assert sha(OLD / name) == frozen['files'][name]
    packets = json.loads((OLD / 'packets.json').read_text(encoding='utf-8'))
    criteria = json.loads((OLD / 'criteria.json').read_text(encoding='utf-8'))
    manifest = json.loads((BASE / 'manifest.json').read_text(encoding='utf-8'))
    groups = json.loads((FULL / 'group_inventory.json').read_text(encoding='utf-8'))
    exposure = json.loads((FULL / 'exposure_inventory.json').read_text(encoding='utf-8'))
    feedback = json.loads((FULL / 'api/blind_027/response.json').read_text(encoding='utf-8'))

    assert len(groups['groups']) == 20 and len(set(groups['groups'].values())) == 15
    assert groups['labels_read'] is False and exposure['all_current20_previously_observed_by_assistant']
    assert (manifest['call_prefixes'], manifest['terminal_trajectories'],
            manifest['distinct_blind_images']) == (827, 80, 60)
    assert manifest['purpose'] == 'development_only'
    assert '20 个独立来源组' in (ROOT / 'docs/PROJECT_PROGRESS.md').read_text(encoding='utf-8')

    def citation(pointer):
        value = packets
        for token in pointer.strip('/').split('/'):
            value = value[int(token)] if isinstance(value, list) else value[token]
        return {'file': str((OLD / 'packets.json').relative_to(ROOT)).replace('\\', '/'),
                'pointer': pointer, 'value': value}

    locations = {
        'E1': ['/E1/trajectory/steps/3/actor_output/current_evidence/3',
               '/E1/trajectory/steps/3/actor_output/evidence_gap',
               '/E1/tool_cards/global_forensic_analyzer/limitations',
               '/E1/trajectory/steps/1/tool_observation',
               '/E1/trajectory/steps/0/tool_observation'],
        'E2': ['/E2/trajectory/steps/1/actor_output/current_evidence/1',
               '/E2/trajectory/steps/0/tool_observation/most_atypical_regions/0',
               '/E2/trajectory/steps/0/tool_observation/observations',
               '/E2/trajectory/steps/1/tool_observation'],
        'E3': ['/E3/trajectory/steps/3/raw_attempts/1', '/E3/budget',
               '/E3/tool_cards/global_forensic_analyzer/limitations',
               '/E3/tool_cards/complementary_forensic_analyzer/useful_when'],
        'N1': ['/N1/trajectory/steps/4/actor_output', '/N1/budget'],
        'N2': ['/N2/current_action/actor_request', '/N2/budget',
               '/N2/tool_cards/global_forensic_analyzer/purpose'],
        'N3': ['/N3/current_action/actor_request', '/N3/budget', '/N3/exposed_tools',
               '/N3/tool_cards/local_texture_analyzer/purpose'],
    }
    local = packets['E1']['trajectory']['steps'][1]['tool_observation']
    assert local['signal'] == 'synthetic_like' and abs(local['score'] - .9730361700057983) < 1e-12
    assert packets['E1']['trajectory']['steps'][3]['actor_output']['current_evidence'][3]['direction'] == 'fake'
    last = json.loads(packets['E3']['trajectory']['steps'][3]['raw_attempts'][1])
    assert last['next_action'] == 'STOP' and '需继续取证' in last['action_reason']
    assert packets['E3']['budget']['remaining_before'] == 1
    assert packets['N1']['budget']['remaining_before'] == 0
    for cid in ('N2', 'N3'):
        assert not packets[cid]['trajectory']['steps']
        assert packets[cid]['budget']['remaining_before'] == 4
        assert packets[cid]['current_action']['selected_tool'] in packets[cid]['exposed_tools']
    assert 'global_forensic_analyzer' not in packets['N3']['exposed_tools']
    assert 'STOP 方向有两条工具结果支持' in feedback['content']
    assert '方向性一致' in feedback['content']

    cards = []
    for cid, pointers in locations.items():
        cards.append({'id': cid, 'review_state': 'pending_researcher_review',
                      'purpose': 'existing_exposed_calibration_only',
                      'proposal_from_existing_criteria': criteria[cid],
                      'citations': [citation(p) for p in pointers],
                      'researcher_decision': None, 'researcher_reason': None,
                      'new_monitor_request': False})
    counterexample = {'id': 'blind_027_existing_feedback',
                      'review_state': 'pending_researcher_review',
                      'proposal': '承认global无方向却仍称两项方向一致，不能仅凭降置信度判合格。',
                      'source': str((FULL / 'api/blind_027/response.json').relative_to(ROOT)).replace('\\', '/'),
                      'pointer': '/content', 'content': feedback['content'],
                      'new_score': None}
    inventory = {
        'checked_pool': 'existing main FaithBench development library only',
        'existing_call_prefixes': 827, 'existing_terminal_trajectories': 80,
        'existing_distinct_images': 60, 'cohort_groups_documented': 20,
        'cohort_groups_basis': 'docs/PROJECT_PROGRESS.md: held-out cohort record; full mapping not reopened',
        'excluded_full20_groups_verified': 15,
        'remaining_cohort_group_upper_bound': 5,
        'remaining_groups_independent_exposure_verified': False,
        'verified_eligible_independent_cases': 0,
        'zero_means': 'none certified in checked scope; not a claim that all repository data are unusable',
        'other_existing_b0_dev30': 'previously development/audited, exposure not established; not selected',
        'requested_cases': {'error': 12, 'reasonable': 12, 'unresolved': 6},
        'reserved74_read_or_allocated': False, 'gt_read': False,
        'new_actor_requests': 0, 'new_monitor_requests': 0,
        'current_step': 'local calibration preparation completed; independent sampling prerequisite unmet',
        'needed_decisions': ['researcher review of attached calibration references',
                             'authorized sample pool/scan limit or explicit change to development diagnosis'],
        'exposure_record': exposure,
    }
    after = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sources}
    assert before == after, 'Preparation changed a source'
    OUT.mkdir()
    for name, value in [('calibration_cards.json', cards), ('feedback_counterexample.json', counterexample),
                        ('source_inventory.json', inventory)]:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 旧案例判据卡：待研究者复核', '',
             '仅用于新标准校准；不重评旧实验，不发送模型。每张卡请确认/修改/保留未决并写理由。', '']
    for card in cards:
        lines += ['## ' + card['id'], '', '既有判据：',
                  '```json', json.dumps(card['proposal_from_existing_criteria'], ensure_ascii=False, indent=2),
                  '```', '', '原始依据：']
        for ref in card['citations']:
            lines += ['', '- 文件：' + ref['file'] + '；字段：' + ref['pointer'],
                      '```json', json.dumps(ref['value'], ensure_ascii=False, indent=2), '```']
        lines += ['', '研究者决定：待填写。', '理由或修改：待填写。', '']
    (OUT / 'CALIBRATION_REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')
    artifacts = {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}
    (OUT / 'preparation_lock.json').write_text(json.dumps({
        'date': '2026-10-13', 'status': 'local_preparation_only',
        'sources': before, 'artifacts': artifacts, 'researcher_confirmed': 0,
        'source_unchanged_check': True, 'model_requests': 0,
        'not_execution_freeze': 'sample/reference prerequisites unresolved'},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'calibration_cards': len(cards), 'source_hashes_checked': len(before),
                      'new_model_requests': 0, 'remaining_cohort_group_upper_bound': 5,
                      'verified_independent_cases': 0, 'status': 'awaiting_sample_scope'}, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
