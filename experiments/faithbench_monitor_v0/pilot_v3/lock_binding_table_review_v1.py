"""Persist explicitly reviewed semantic findings; no model-based adjudication."""
import json
from binding_compact_probe_v1 import ROOT, sha, dump, resolve
from prepare_binding_table_probe_v1 import OUT


def main():
    units = json.loads((OUT / 'review_snapshot.json').read_text(encoding='utf-8'))['units']
    materials = {r['id']: r for r in json.loads((OUT / 'materials.json').read_text(encoding='utf-8'))['records']}
    findings = {
        'max_median_P01_evidence_changed__fact_table': (False, True, '99与99.0相等，checks却写严格大于满足；reason及最终拒绝正确，与checks矛盾。'),
        'max_median_P01_evidence_changed__original': (True, True, '值、严格大于不满足、相等理由、引用与最终拒绝一致。'),
        'all_at_max_P01_missing_key__fact_table': (False, False, '明确事实表第三百分位缺失仍称全部100并支持；无missing标记，另有错误binding键，区域值无entity。'),
        'all_at_max_P01_missing_key__original': (False, False, '第三百分位缺失仍称三个条目全部100并支持；重复R12的E1328实际100，不单独指控显式R14=100绑定；区域值无entity。'),
        'all_count_P01_missing_key__fact_table': (False, True, '理由正确指出7个区域未全部给值、最终拒绝正确；未知条件误标不满足，无两缺失字段标记，entity/value独立项格式不符，理由百分位未引用相应叶子。'),
        'all_count_P01_missing_key__original': (False, True, '理由正确指出7项仅见3项、无法全称确认；把受检总数必须等于最异常返回列表长度当必要条件，不成立的机械条件不能替代未知目标条件。无缺失标记，区域值无entity。'),
        'raw_score_P01_evidence_changed__fact_table': (True, True, '实际score精确绑定、六位舍入反证、引用与拒绝一致；理由较短小数表达不改变六位舍入。'),
        'raw_score_P01_evidence_changed__original': (True, True, '实际score精确绑定、六位舍入反证、引用与拒绝一致。'),
        'all_at_max_P01_supported__fact_table': (True, True, 'N3及三条已知100支持主张、条件/理由/标签正确；区域数值未附同对象entity，身份叶子未引用，联合契约失败。'),
        'all_at_max_P01_supported__original': (True, True, 'N3/异常数3/比例1及三个不同区域100支持主张；条件/理由/标签正确，但区域数值无entity，联合契约失败。'),
        'threshold_P01_supported__original': (True, True, '实际observation明确阈值0.25，绑定/条件/理由/引用/标签一致；引用省略数字前空格，不追加字节级原文标准。'),
        'threshold_P01_supported__fact_table': (True, True, '实际observation明确阈值0.25，绑定/条件/理由/引用/标签一致。'),
    }
    rows = []
    for unit in units:
        rid = unit['id']
        material = materials[rid]
        answer = json.loads(unit['raw'])
        evidence = material['input_payload']['source_evidence']
        fact = evidence['actual_returns'][0]['original_return']
        pointers = {v: k for k, v in evidence['return_field_references'][0].items()}
        valid_pairs = [b for b in answer['bindings'] if 'ref' in b and 'value' in b]
        assert all(b['value'] == resolve(fact, pointers[b['ref']]) for b in valid_pairs)
        relations, reason, note = findings[rid]
        structural = unit['structural']
        label = structural['label_matches_target']
        fields = structural['field_audit_pass'] and structural.get('required_binding_coverage', False)
        rows.append(dict(id=rid, case_id=structural['case_id'], condition=structural['condition'],
            format_complete=structural['parse_valid'], output_order_correct=list(answer)==['bindings','checks','reason','return_reference_ids','judgement'],
            source_ref_value_pairs=len(valid_pairs), source_ref_value_pairs_correct=len(valid_pairs),
            relation_checks_semantically_correct=relations, reason_factually_correct=reason,
            label_correct=label, field_and_citation_contract_pass=fields,
            semantic_checks_reason_label_pass=relations and reason and label,
            joint_pass=fields and relations and reason and label, finding=note))
    assert set(findings) == {r['id'] for r in rows}
    dump(OUT / 'first_review_locked.json', dict(reviewer='same_assistant_nonblind', independent_human_gold=False,
        raw_sha256=sha(OUT / 'backup/binding_table_probe_v1_trial/predictions.jsonl'), rows=rows))
    # The separate reread is recorded after inspecting the frozen snapshot again.
    metrics = {}
    for condition in ['original', 'fact_table']:
        group = [r for r in rows if r['condition'] == condition]
        metrics[condition] = {key: sum(r[key] for r in group) for key in
            ['format_complete','label_correct','relation_checks_semantically_correct','reason_factually_correct',
             'field_and_citation_contract_pass','semantic_checks_reason_label_pass','joint_pass']}
    paired = []
    for case_id in dict.fromkeys(r['case_id'] for r in rows):
        pair = {r['condition']: r for r in rows if r['case_id'] == case_id}
        a,b = pair['original'], pair['fact_table']
        paired.append(dict(case_id=case_id, original_joint=a['joint_pass'], fact_table_joint=b['joint_pass'],
            repaired_joint=not a['joint_pass'] and b['joint_pass'], new_joint_failure=a['joint_pass'] and not b['joint_pass']))
    dump(OUT / 'review_metrics.json', dict(conditions=metrics, paired=paired, independent_gold=False,
        source_ref_value_pairs_correct=sum(r['source_ref_value_pairs_correct'] for r in rows),
        model_requests=12, optimizer_steps=0, no_resampling=True))
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == '__main__':
    main()
