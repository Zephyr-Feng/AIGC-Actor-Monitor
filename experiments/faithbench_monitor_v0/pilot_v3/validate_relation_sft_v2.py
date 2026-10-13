"""Validate approved abstract materials, their missing-case witnesses and split."""
import copy
import hashlib
import json
import re
import statistics
from pathlib import Path
from decimal import Decimal, ROUND_HALF_EVEN

from relation_probe_v2 import ROOT, remove, resolve, leaves, sha
from prepare_relation_sft_v2 import OUT, KEYS, VARIANTS, assistant_text, dump


def predicate(fact, family, params):
    obs, regions = fact.get('observations', {}), fact.get('most_atypical_regions')
    if family == 'all_count':
        return obs.get('num_atypical_regions') == fact['scope']['num_regions_examined']
    if family == 'all_at_max':
        return regions is not None and len(regions) == fact['scope']['num_regions_examined'] and all(r.get('deviation_percentile') == 100 for r in regions)
    if family == 'max_median':
        return 'median_deviation_percentile' in obs and obs['max_deviation_percentile'] > obs['median_deviation_percentile']
    if family == 'raw_score':
        return 'score' in fact and Decimal(str(fact['score'])).quantize(Decimal('0.000001'), rounding=ROUND_HALF_EVEN) == Decimal(params['target_score'])
    if family == 'threshold':
        match = re.search(r'固定判定阈值为 ([0-9.]+)', fact.get('observation', ''))
        return match is not None and Decimal(match[1]) == Decimal(params['target_threshold'])
    if family == 'limitation_text':
        return any(params['target_literal'] in line for line in fact.get('limitations', []))
    if family == 'region_identity':
        return regions is not None and any(r['region_id'] == params['target_region'] for r in regions)
    if family == 'bbox_coordinate':
        return regions is not None and any(r['region_id'] == params['target_region'] and r.get('bbox', [None])[0] == params['target_coordinate'] for r in regions)
    if family == 'list_length':
        return regions is not None and len(regions) == params['target_count']
    raise ValueError(family)


def check_complete(fact, values, top):
    if values is None:
        score = fact['score']
        assert f'{score:.6f}' in fact['observation']
        threshold = float(re.search(r'固定判定阈值为 ([0-9.]+)', fact['observation'])[1])
        assert fact['signal'] == ('real_like' if score < threshold else 'synthetic_like')
        return
    assert fact['scope']['num_regions_examined'] == len(values)
    obs = fact['observations']
    count = sum(v >= obs['atypical_threshold_percentile'] for v in values)
    assert obs['num_atypical_regions'] == count and obs['atypical_fraction'] == count / len(values)
    assert obs['max_deviation_percentile'] == max(values)
    assert obs['median_deviation_percentile'] == statistics.median(values)
    regions = fact['most_atypical_regions']
    assert len(regions) == min(top, len(values)) and len({r['region_id'] for r in regions}) == len(regions)
    ranked = sorted(enumerate(values), key=lambda pair: (-pair[1], pair[0]))[:top]
    assert [(r['patch_id'], r['deviation_percentile']) for r in regions] == ranked
    for r in regions:
        x1, y1, x2, y2 = r['bbox']
        assert x1 < x2 and y1 < y2


def validate():
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf8'))
    for name, digest in manifest['artifact_hashes'].items():
        assert sha(OUT / name) == digest, name
    for name, digest in manifest['dependency_hashes'].items():
        assert sha(ROOT / name) == digest, name
    cases = json.loads((OUT / 'cases.json').read_text(encoding='utf8'))
    witnesses = json.loads((OUT / 'missing_witnesses.json').read_text(encoding='utf8'))
    by_id = {c['id']: c for c in cases}
    assert len(by_id) == len(cases) == 108
    refs_count = 0
    for w in witnesses:
        group = w['group']
        observed = by_id[group + '_missing_key']['payload']['source_evidence']['actual_returns'][0]['original_return']
        projections = []
        for prefix, should_support in [('positive', True), ('negative', False)]:
            full = w[prefix + '_completion']
            assert predicate(full, w['family'], w['parameters']) == should_support, group
            check_complete(full, w[prefix + '_values'], w[prefix + '_top'])
            projected = remove(full, *w['projection_removed_fields'])
            if w['missing_observation_override'] is not None:
                projected['observation'] = w['missing_observation_override']
            projections.append(projected)
        assert projections[0] == projections[1] == observed, group
        rows = [by_id[group + '_' + v] for v in VARIANTS]
        assert len({r['split'] for r in rows}) == 1
        a, b = rows[0]['payload'], rows[3]['payload']
        assert a['source_evidence'] == b['source_evidence'] and a['source_capability_definitions'] == b['source_capability_definitions']
        assert a['subject_to_review']['claim'] == b['subject_to_review']['claim']
        assert a['subject_to_review']['actor_claim_context'] != b['subject_to_review']['actor_claim_context']
        assert rows[0]['targets'] == rows[3]['targets']
    for c in cases:
        e = c['payload']['source_evidence']
        fact, refs = e['actual_returns'][0]['original_return'], e['return_field_references'][0]
        assert set(refs) == {ptr for ptr, _ in leaves(fact)}
        assert len(set(refs.values())) == len(refs)
        assert set(refs.values()).isdisjoint(c['payload']['source_capability_definitions'])
        for ptr in refs:
            resolve(fact, ptr)
            refs_count += 1
        assert predicate(fact, c['family'], c['parameters']) == (c['judgement'] == '支持'), c['id']
        assert (c['judgement'] == '支持') == (c['variant'] in ('supported', 'actor_changed'))
        assert json.loads(c['prompt'].split('\n输入：\n', 1)[1]) == c['payload']
        assert hashlib.sha256(c['prompt'].encode()).hexdigest() == c['prompt_sha256']
        assert '明确标识的抽象关系诊断fixture' in c['prompt']
        ordinary, relation = c['targets']['ordinary'], c['targets']['relation']
        assert ordinary['judgement'] == relation['judgement'] == c['judgement']
        expected_refs = [refs[p] for p in c['required_reference_pointers']]
        assert ordinary['return_reference_ids'] == relation['return_reference_ids'] == expected_refs
        for answer in c['targets'].values():
            assert tuple(answer) == KEYS and answer['reason']
            assert tuple(json.loads(assistant_text(answer))) == KEYS
            assert set(answer['return_reference_ids']).issubset(refs.values())
    train = [c for c in cases if c['split'] == 'train']
    held = [c for c in cases if c['split'] == 'held']
    train_sources, held_sources = {c['source_component'] for c in train}, {c['source_component'] for c in held}
    train_families, held_families = {c['family'] for c in train}, {c['family'] for c in held}
    assert train_sources.isdisjoint(held_sources) and train_families.isdisjoint(held_families)
    assert train_sources == set(manifest['source_components_train']) and held_sources == set(manifest['source_components_held'])
    for method in ('ordinary', 'relation'):
        rows = json.loads((OUT / ('train_' + method + '.json')).read_text(encoding='utf8'))
        assert len(rows) == 72 and {r['id'] for r in rows} == {c['id'] for c in train}
        for r in rows:
            c = by_id[r['id']]
            assert r['answer'] == c['targets'][method] and r['assistant_text'] == assistant_text(r['answer'])
            assert r['user_text'] == c['prompt']
    ordinary = json.loads((OUT / 'train_ordinary.json').read_text(encoding='utf8'))
    relation = json.loads((OUT / 'train_relation.json').read_text(encoding='utf8'))
    assert [(r['id'], r['user_text']) for r in ordinary] == [(r['id'], r['user_text']) for r in relation]
    assert len(json.loads((OUT / 'evaluation_held.json').read_text(encoding='utf8'))) == 36
    assert len(json.loads((OUT / 'evaluation_regression.json').read_text(encoding='utf8'))) == 48
    report = dict(cases=108, train_records_per_method=72, held_records=36, families=9, parameter_groups=27,
        compatible_missing_witness_pairs=27, complete_witnesses_checked=54, actual_reference_pointers=refs_count,
        same_inputs_labels_references_across_methods=True, source_and_family_split_disjoint=True,
        actor_controls_verified=27, assistant_order_verified=list(KEYS),
        train_supported=36, train_unsupported=36, held_supported=18, held_unsupported=18,
        model_requests=0, optimizer_steps=0, tokenizer_checked=False, independent_human_gold=False,
        manifest_sha256=sha(OUT / 'manifest.json'), cases_sha256=sha(OUT / 'cases.json'))
    dump(OUT / 'input_validation.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    validate()
