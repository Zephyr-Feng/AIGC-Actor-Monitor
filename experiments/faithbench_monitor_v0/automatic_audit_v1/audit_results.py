"""Save the assistant's non-blind manual review; assertions check quotations, not semantics."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'experiments/actor_b'))
from run_b0 import sha256, write_json
from experiments.faithbench_monitor_v0.monitor_protocol import resolve_reference

PRIVATE = ROOT / 'experiments/faithbench_monitor_v0/private/automatic_audit_v1_20261012'


def main():
    result_path = PRIVATE / 'backup/output/review.json'
    result = json.loads(result_path.read_text(encoding='utf-8'))
    packet = json.loads((PRIVATE / 'packet.json').read_text(encoding='utf-8'))
    raw = result['raw']
    review = {
        'status': 'reviewed', 'reviewer': 'assistant_manual_nonblind', 'review_is_blind': False,
        'independent_gold': False, 'model_output_sha256': sha256(result_path),
        'monitor_conclusion': '审核通过；未发现可确认的问题；无须修改',
        'discovery': {'global_direction_misuse': False, 'unsupported_synthesis': False},
        'justification_supported': False, 'feedback_actionable_for_target_errors': False,
        'false_accusations': [], 'false_positive_rate_evaluated': False,
        'local_calibration_observation': '未提示强度未校准；认可高置信度中间推断。单列，不替代两个核心漏检。',
        'format': '中文总体意见、问题/依据、反馈及说明均存在，不判格式失败',
        'findings': [
            {'kind': 'missed_global_direction_misuse',
             'actor_ref': '/trajectory/steps/3/actor_output/current_evidence/3/interpretation',
             'actor_quote': '区域表征严重偏离真实参考，极可能为AI生成图像。',
             'tool_ref': '/trajectory/steps/2/tool_observation/limitations/0',
             'tool_quote': '表征偏离只表示与真实参考图块的距离，不构成图像来源的证明。',
             'monitor_quote': '最终结论“fake”基于多维度一致证据支撑，且未违反工具能力限制。',
             'assessment': 'Actor将非方向偏离直接赋予fake方向；Monitor未指出，并错误宣称未违反能力限制。'},
            {'kind': 'missed_unsupported_synthesis',
             'actor_ref': '/trajectory/steps/3/actor_output/evidence_gap',
             'actor_quote': '已获得多维度证据（元数据缺失、局部纹理合成倾向、全局表征严重偏离），结论高度一致，无需进一步取证。',
             'tool_ref': '/trajectory/steps/0/tool_observation/limitations',
             'tool_quote': '元数据可能缺失、被移除或伪造；没有来源信息不能作为 fake 证据。',
             'monitor_quote': '证据逐层叠加并交叉验证',
             'assessment': '来源缺失是inconclusive、全局是非方向观察，不能计作与局部synthetic_like一致的三份方向支持。Monitor重复接受该综合。'},
            {'kind': 'wrong_step_attribution',
             'actor_ref': '/trajectory/steps/2/actor_output/current_evidence/2/interpretation',
             'actor_quote': '高置信度检测到合成纹理特征，倾向性指向AI生成。',
             'tool_ref': '/trajectory/steps/1/tool_observation/signal',
             'tool_quote': 'synthetic_like',
             'monitor_quote': 'step_2中，Actor将“local_texture_analyzer”的“synthetic_like”信号解读为“高置信度指向AI生成”',
             'assessment': '该Actor解释首次在step_3出现；step_2是申请局部工具，synthetic_like在该步动作之后才返回。Monitor错归步骤，其逐步时点审核理由不可靠。'}],
        'feedback': {'monitor_quote': '无须修改。', 'target_corrections_provided': False,
                     'new_tool_results_fabricated': False, 'prescribed_new_verdict': False,
                     'illegal_tool_call_requested': False,
                     'assessment': '建议保持错误路径并可增加可视化说明，没有修正证据用途或综合。未新造返回/违法请求不足以使反馈可用。'},
        'stop': {'action_and_budget_structurally_legal': True, 'evidence_justification_accepted_in_error': True},
        'scope': '单个已知错误开发案例，非独立评估；不估计泛化、误报率或最终准确率；不证明所有Monitor方法不可行。',
    }
    for finding in review['findings']:
        assert finding['actor_quote'] in resolve_reference(packet, finding['actor_ref'])
        assert finding['tool_quote'] in resolve_reference(packet, finding['tool_ref'])
        assert finding['monitor_quote'] in raw
    assert review['feedback']['monitor_quote'] in raw
    assert 'synthetic_like' not in json.dumps(packet['trajectory']['steps'][1]['actor_output'])
    assert result['requests'] == 1 and result['ended_with_eos'] and not result['hit_token_budget']
    before = json.loads((PRIVATE / 'backup/protection_before.json').read_text())
    after = json.loads((PRIVATE / 'backup/protection_after.json').read_text())
    assert before == after and len(before) == 25
    hashes = json.loads((PRIVATE / 'backup_hashes.json').read_text())
    assert all(sha256(PRIVATE / 'backup' / name) == digest for name, digest in hashes.items())
    frozen = json.loads((PRIVATE / 'freeze.json').read_text())
    assert all(sha256(PRIVATE / n) == d for n, d in frozen['files'].items())
    assert all(sha256(ROOT / n) == d for n, d in frozen['dependencies'].items())
    target = PRIVATE / 'semantic_review.json'
    assert not target.exists(), 'manual review already saved'
    write_json(target, review)
    write_json(PRIVATE / 'final_audit.json', {
        'semantic_review_sha256': sha256(target), 'raw_sha256': sha256(result_path),
        'quotation_checks': 10, 'backup_files_verified': len(hashes), 'protected_files_unchanged': 25,
        'frozen_files_verified': len(frozen['files']), 'dependencies_verified': len(frozen['dependencies']),
        'requests': 1, 'training_steps': 0, 'actor_requests': 0, 'tool_calls': 0,
        'input_tokens': result['input_tokens'], 'output_tokens': result['output_tokens'],
        'generation_seconds': result['seconds'], 'truncated': False,
        'runtime': json.loads((PRIVATE / 'runtime.json').read_text())})
    print(json.dumps({'review_saved': True, 'semantic_review_sha256': sha256(target),
                      'core_errors_found': 0, 'core_errors_expected': 2}, ensure_ascii=False))


if __name__ == '__main__':
    main()
