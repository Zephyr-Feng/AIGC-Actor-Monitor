"""Persist the assistant's completed item review, with exclusive creation only."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / 'experiments/faithbench_monitor_v0/private/relation_prompt_probe_v1_20261011'


def run():
    # Read-only verification confirmed this new directory has no previous review lock.
    target = OUT / 'first_review_locked.json'
    assert not target.exists(), 'preserve any existing review lock'
    audit = json.loads((OUT / 'review_table.json').read_text(encoding='utf8'))
    issues, citation = {}, {}
    conflicts, implicit = set(), set()

    def add(model, condition, ids, kind, note):
        for ident in ids.split():
            issues[(ident, model, condition)] = (kind, note)

    def cite(model, condition, ids, note):
        for ident in ids.split():
            citation[(ident, model, condition)] = note

    for condition in ['reason_first', 'relation_first']:
        add('base', condition, 'Q02_missing_key', 'missing_value_hallucination', '第三项百分位缺失；重复前两项引用不能补出第三值。')
        add('base', condition, 'Q04_missing_key', 'attribute_swap', '阈值95不是median；100>95不证明max>median。')
        add('base', condition, 'T01_missing_key', 'partial_to_all', 'max100或前三项100不能覆盖受检9区域。')
        add('adapter', condition, 'Q02_evidence_changed', 'label_correct_reason_wrong', '忽略99/98反证，比例1与百分位100比较或受检3推出非全100，均不成立。')
        add('adapter', condition, 'Q02_missing_key', 'missing_value_hallucination', '第三项百分位未给出，却说列表全部100。')
        add('adapter', condition, 'Q04_missing_key', 'attribute_swap', '比较max100与阈值95，没有比较缺失的median。')
        add('adapter', condition, 'Q01_missing_key', 'partial_to_all_or_attribute_wrong', '9与95不是同一属性；前三项100不能覆盖全体。')
        add('adapter', condition, 'T01_missing_key', 'partial_to_all', '用max100或前三项100推出全部9项达到阈值。')
        add('adapter', condition, 'T03_evidence_changed', 'attribution_not_literal', '不能指认物理痕迹，不等于实际字段明确写出来源证明句。')
        cite('adapter', condition, 'A01_evidence_changed', '只引用R7，未覆盖R8/R9以证明不存在R1。')
        cite('adapter', condition, 'Q02_supported Q02_actor_changed', '三项百分位已有，但缺受检总数引用以核全体覆盖。')
        conflicts.update((ident, 'adapter', condition) for ident in ['A04_evidence_changed', 'T04_evidence_changed'])
    add('base', 'reason_first', 'Q01_missing_key', 'partial_to_all', '从前三项100推出受检9项全部达到阈值。')
    add('base', 'reason_first', 'T03_evidence_changed', 'attribution_not_literal', '从物理痕迹局限推成当前返回明示来源证明句，替换了明确归因目标。')
    add('base', 'relation_first', 'A02_evidence_changed T02_evidence_changed', 'comparison_wrong', '实际0.188203却说与待审0.088203一致。')
    add('base', 'relation_first', 'Q02_evidence_changed', 'extra_false_scope_assertion', '99/98反证正确，但附加列表未覆盖受检3区域的错误断言。')
    add('base', 'relation_first', 'Q02_supported', 'label_correct_extra_false_inference', '先由异常比例及计数推出偏离100；实际三值100正确但附加连接错误。')
    cite('base', 'reason_first', 'Q02_supported Q02_actor_changed', '未引用受检总数以核三项覆盖全体。')
    add('adapter', 'reason_first', 'A02_evidence_changed', 'comparison_wrong', '0.188203却说与0.088203主张一致。')
    add('adapter', 'reason_first', 'Q01_evidence_changed T01_evidence_changed', 'comparison_wrong', '实际受检9异常8，却说相等。')
    add('adapter', 'reason_first', 'Q04_evidence_changed', 'comparison_wrong', '100与100相等，却说严格高于。')
    add('adapter', 'reason_first', 'Q03_missing_key', 'reason_insufficient_wrong_label', '只说检查数不等于列表数量，未指实际列表缺失，不能支持三项。')
    add('adapter', 'reason_first', 'T01_supported T01_actor_changed', 'label_correct_extra_false_assertion', '比例1正确，但附加阈值95与异常数9一致。')
    add('adapter', 'reason_first', 'T03_missing_key', 'citation_attribute_swap', 'limitations未给出，E0107为max96，却说存在来源证明文本。')
    conflicts.update({('Q03_evidence_changed', 'adapter', 'reason_first'), ('T02_evidence_changed', 'adapter', 'reason_first'),
                      ('Q01_evidence_changed', 'adapter', 'relation_first'), ('Q04_evidence_changed', 'adapter', 'relation_first'),
                      ('T01_evidence_changed', 'adapter', 'relation_first')})
    implicit.add(('T02_evidence_changed', 'adapter', 'relation_first'))
    cite('adapter', 'reason_first', 'Q03_evidence_changed', '列表长度2的理由没有实际条目引用。')
    cite('adapter', 'relation_first', 'A01_missing_key', 'tool名称不能证明列表缺失，应空引用。')
    rows = []
    for item in audit:
        key = (item['id'], item['model'], item['condition'])
        bad, gap = issues.get(key), citation.get(key)
        rows.append({k: item[k] for k in ['id', 'model', 'condition', 'group', 'variant', 'relation_cluster']} | {
            'label_correct': item['label_matches'], 'reason_correct': bad is None,
            'label_reason_consistent': key not in conflicts and key not in implicit,
            'explicit_label_reason_contradiction': key in conflicts, 'implicit_label_reason_conflict': key in implicit,
            'citation_sufficient': bad is None and gap is None and item['references_exist'],
            'references_exist': item['references_exist'], 'output_order_compliant': item['requested_order_compliant'],
            'citation_coverage_note': gap,
            'failure_type': bad[0] if bad else ('label_reason_contradiction' if key in conflicts else ('implicit_label_reason_conflict' if key in implicit else ('citation_coverage_gap' if gap else None))),
            'review_note': bad[1] if bad else ('理由明确否定主张却支持。' if key in conflicts else ('理由实际值与主张相反但没有显式否定词，隐含矛盾单列。' if key in implicit else (gap or '已核当前主张、必要实际字段及关系，无实质错误。')))})
    assert len(rows) == len({(r['id'], r['model'], r['condition']) for r in rows}) == 192
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'review_type': 'same_assistant_nonblind_first_review_not_independent_human_gold',
              'raw_sha256': digest(OUT / 'backup/relation_prompt_probe_v1_trial/predictions.jsonl'),
              'review_table_sha256': digest(OUT / 'review_table.json'), 'annotation_code_sha256': digest(Path(__file__)),
              'criteria': '沿用前测。正确核心伴随实质错误连接失败；全体覆盖缺引用单列；非穷举字段描述不单独否定正确缺失判断。',
              'sensitivity_cases': [['T01_supported', 'adapter', 'reason_first'], ['T01_actor_changed', 'adapter', 'reason_first'], ['Q02_supported', 'base', 'relation_first']], 'rows': rows}
    with target.open('x', encoding='utf8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'items': 192, 'reason_failures': len(issues), 'explicit_contradictions': len(conflicts),
                      'implicit_conflicts': len(implicit), 'first_review_sha256': digest(target)}))


if __name__ == '__main__':
    run()
