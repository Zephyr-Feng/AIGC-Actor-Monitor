"""Audit reserve membership/file availability; decode only whitelisted metadata."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import sha

OUT = ROOT / 'experiments/faithbench_monitor_v0/private/reserved_metadata_audit_20261013'
FIELDS = ('sample_id', 'source_group', 'generator')


def metadata(path, fields=FIELDS):
    patterns = {key: re.compile(r'"' + key + r'"\s*:\s*("(?:[^"\\]|\\.)*")') for key in fields}
    rows = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            row = {}
            for key, pattern in patterns.items():
                values = {json.loads(match) for match in pattern.findall(line)}
                if key == 'sample_id':
                    assert len(values) == 1, f'Ambiguous metadata in {path}'
                if len(values) == 1:
                    row[key] = values.pop()
            rows.append(row)
    return rows


def main():
    assert not OUT.exists(), 'Do not overwrite a completed metadata audit'
    evaluation = ROOT / 'experiments/actor0/data/actor0_eval_manifest.jsonl'
    heldout = ROOT / 'experiments/actor_b/heldout_confirmation/input/heldout_manifest.jsonl'
    mini = ROOT / 'experiments/mini_faithbench_v0/config/technical_sample_manifest.jsonl'
    old_cards = ROOT / 'experiments/actor0/config/tool_cards.json'
    new_cards = ROOT / 'experiments/actor_b/actor_b0_d/audit_assist/work/full/tools.json'
    qualitative = ROOT / 'experiments/actor0/analysis/qualitative_audit_review/evidence_bundle.md'
    trajectory_paths = [ROOT / path for path in (
        'runs/actor0-bfree-20261002/trajectories/trajectories.jsonl',
        'experiments/actor_b/heldout_confirmation/outputs/trajectories.jsonl',
        'experiments/actor_b/baseline_b0/outputs/trajectories.jsonl',
        'experiments/actor_b/baseline_b0_schema_fixed_v2/outputs/trajectories.jsonl',
        'experiments/actor_b/actor_b0_d/full/trajectories.jsonl',
        'experiments/actor_b/actor_b0_d/probe_mask/trajectories.jsonl',
        'experiments/actor_b/actor_b0_d/probe_delay/trajectories.jsonl',
        'experiments/actor_b/actor_b0_d/tool_rename/trajectories.jsonl',
        'experiments/mini_faithbench_v0/technical_sample/full.jsonl',
        'experiments/mini_faithbench_v0/technical_sample_v2/trajectories/full.jsonl',
        'experiments/mini_faithbench_v0/technical_sample_v3/trajectories/full.jsonl')]
    sources = [evaluation, heldout, mini, old_cards, new_cards, qualitative,
               ROOT / 'experiments/actor_b/prepare_heldout.py',
               ROOT / 'experiments/actor0/scripts/run_actor0.py',
               ROOT / 'experiments/probe_evidence_v1/extract_features.py', Path(__file__), *trajectory_paths]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    assert sha(evaluation) == 'fffd5736418a4cfd36b85f95b571a4347608851d607db9a5b86010f6ce1a857c'
    assert sha(heldout) == 'fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531'
    eval_rows, heldout_rows, mini_rows = metadata(evaluation), metadata(heldout), metadata(mini)
    assert all(set(row) == set(FIELDS) for row in eval_rows + heldout_rows + mini_rows)
    eval_groups = {r['source_group'] for r in eval_rows}
    heldout_groups = {r['source_group'] for r in heldout_rows}
    mini_groups = {r['source_group'] for r in mini_rows}
    assert (len(eval_rows), len(eval_groups), len(heldout_groups), len(mini_groups)) == (300, 100, 20, 6)
    assert not heldout_groups & mini_groups and heldout_groups | mini_groups <= eval_groups
    reserve = eval_groups - heldout_groups - mini_groups
    rows = [r for r in eval_rows if r['source_group'] in reserve]
    assert len(reserve) == 74 and len(rows) == 222
    assert all({r['generator'] for r in rows if r['source_group'] == g} ==
               {'raise', 'flux', 'sd3_5'} for g in reserve)
    ids = {r['sample_id'] for r in rows}
    old = json.loads(old_cards.read_text(encoding='utf-8'))
    current = json.loads(new_cards.read_text(encoding='utf-8'))['cards']
    assert 'signal: real 或 fake' in old['global_forensic_analyzer']['returns']
    assert '不返回 real/fake' in current['global_forensic_analyzer']['limitations']

    coverage = []
    for path in trajectory_paths:
        found = {r['sample_id'] for r in metadata(path, ('sample_id',))}
        coverage.append({'file': path.relative_to(ROOT).as_posix(),
                         'distinct_sample_ids': len(found), 'reserve_id_matches': len(found & ids)})
    assert coverage[0]['distinct_sample_ids'] == 300 and coverage[0]['reserve_id_matches'] == 222
    assert all(entry['reserve_id_matches'] == 0 for entry in coverage[1:])

    # Extract audit headings only; do not use the review prose or its conclusions.
    audited_groups = set()
    with qualitative.open(encoding='utf-8') as stream:
        for line in stream:
            match = re.match(r'^## \d+\. (r[0-9a-f]+t):', line)
            if match:
                audited_groups.add(match.group(1))
    cards_dir = ROOT / 'experiments/probe_evidence_v1/results/output/evidence/cards'
    archive = ROOT / 'runs/actor0-bfree-20261002/trajectories/evaluation/autonomous'
    presence = []
    for row in rows:
        stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', row['sample_id'])
        card_stem = row['sample_id'].replace(':', '__')
        presence.append({**row, 'old_actor0_json_exists': (archive / (stem + '.json')).is_file(),
                         'evidence_only_card_exists': (cards_dir / (card_stem + '.json')).is_file(),
                         'listed_in_old_qualitative_audit': row['source_group'] in audited_groups})
    assert sum(r['old_actor0_json_exists'] for r in presence) == 222
    assert sum(r['evidence_only_card_exists'] for r in presence) == 222
    assert hashes == {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    summary = {
        'date': '2026-10-13', 'scope': 'authorized metadata and existing-file availability only',
        'eval_groups': 100, 'excluded_heldout_groups': 20, 'excluded_mini_groups': 6,
        'reserved_groups': 74, 'reserved_images': 222, 'selected_or_allocated_groups': 0,
        'old_actor0_aggregate_id_coverage': 222, 'old_actor0_individual_file_coverage': 222,
        'evidence_only_card_file_coverage': 222, 'checked_current_actor_b_or_mini_reserve_coverage': 0,
        'trajectory_inventory': coverage,
        'old_qualitative_audit_reserve_group_overlap': len(audited_groups & reserve),
        'old_qualitative_audit_reserve_image_overlap': sum(r['listed_in_old_qualitative_audit'] for r in presence),
        'overlap_means': 'all three generator rows marked at group level; not all were individually reviewed',
        'compatibility': 'Old Actor-0 global has real/fake classifier signal; current global is nondirectional. Do not replace historical evidence or score old directional use as current violation.',
        'independent_monitor_exposure_certified': False,
        'scope_issue': 'Initial broad text search returned old Actor-0 qualitative tool excerpts; subsequent audit restricted to metadata. Full unseen status cannot be claimed.',
        'labels_decoded_from_manifests_or_trajectories': False,
        'trajectory_reasoning_decoded': False, 'image_pixels_read': False,
        'tool_evidence_payloads_decoded_by_this_script': False, 'model_requests': 0, 'gpu_or_server_operations': 0,
        'remaining_decision': 'reuse old Actor-0 with its original protocol, or generate current Actor-B trajectories; approve scope before allocation/reading payloads',
    }
    OUT.mkdir()
    for name, value in [('summary.json', summary), ('metadata_presence.json', presence)]:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT / 'audit_lock.json').write_text(json.dumps({'sources': hashes,
        'artifacts': {p.name: sha(p) for p in OUT.iterdir()}, 'source_unchanged_check': True},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: summary[key] for key in ('reserved_groups', 'reserved_images',
        'old_actor0_individual_file_coverage', 'evidence_only_card_file_coverage',
        'checked_current_actor_b_or_mini_reserve_coverage', 'old_qualitative_audit_reserve_group_overlap',
        'selected_or_allocated_groups', 'model_requests')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
