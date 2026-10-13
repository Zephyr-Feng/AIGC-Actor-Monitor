"""Prepare the approved natural cohort, without decoding GT or old trajectories."""
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from audit_reserved_metadata import metadata
from prepare import sha

OUT = ROOT / 'experiments/faithbench_monitor_v0/private/natural_actor_monitor_20261013'
EVIDENCE = ROOT / 'experiments/probe_evidence_v1/results/output/evidence'


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    audited = ROOT / 'experiments/faithbench_monitor_v0/private/reserved_metadata_audit_20261013'
    inventory = json.loads((audited / 'metadata_presence.json').read_text(encoding='utf-8'))
    lock = json.loads((audited / 'audit_lock.json').read_text())
    assert all(sha(audited / p) == h for p, h in lock['artifacts'].items())
    manifest = ROOT / 'experiments/actor0/data/actor0_eval_manifest.jsonl'
    cache = ROOT / 'runs/actor0-bfree-20261002/scores/eval_tool_observations.jsonl'
    assert sha(manifest) == 'fffd5736418a4cfd36b85f95b571a4347608851d607db9a5b86010f6ce1a857c'
    assert sha(cache) == 'fe972dd669256ada81bdf7611917337e0ce8cab5825005293ee36a03bc19e4d7'
    groups = {r['source_group'] for r in inventory if not r['listed_in_old_qualitative_audit']}
    assert len(groups) == 43
    ranked = sorted(groups, key=lambda g: hashlib.sha256(f'20261013:{g}'.encode()).hexdigest())
    by_pair = {(r['source_group'], r['generator']): r for r in inventory}
    by_id = {r['sample_id']: r for r in metadata(manifest, ('sample_id', 'relative_path', 'sha256'))}
    chosen = []
    for i, group in enumerate(ranked[:30]):
        row = by_pair[group, ('raise', 'flux', 'sd3_5')[i % 3]]
        chosen.append({**row, **by_id[row['sample_id']], 'case_id': f'case_{i + 1:03d}'})
    assert len({r['source_group'] for r in chosen}) == 30
    assert Counter(r['generator'] for r in chosen) == {'raise': 10, 'flux': 10, 'sd3_5': 10}
    ids = {r['sample_id'] for r in chosen}
    selection = {'approval': 'user confirmed natural cohort and assistant initial review on 2026-10-13',
        'seed': 20261013, 'selection_rule': 'SHA256 group ranking; cyclic generator assignment, no outcome selection',
        'selected': chosen, 'reserved_groups_remaining': 44, 'independent_exposure_certified': False,
        'gt_decoded': False, 'source_manifest_sha256': sha(manifest), 'source_cache_sha256': sha(cache)}
    if OUT.exists():
        # Resume only the observed preparation failure; never rewrite the allocated selection.
        assert {p.name for p in OUT.iterdir()} == {'selection.json'}
        assert json.loads((OUT / 'selection.json').read_text(encoding='utf-8')) == selection
    else:
        OUT.mkdir()
        write('selection.json', selection)
    # Decode only the tools array on selected rows, never top-level labels or unselected payloads.
    selected_tools = {}
    sid_pattern = re.compile(r'"sample_id"\s*:\s*("(?:[^"\\]|\\.)*")')
    with cache.open(encoding='utf-8') as stream:
        for line in stream:
            sid = json.loads(sid_pattern.search(line).group(1))
            if sid in ids:
                match = re.search(r'"tools"\s*:\s*', line)
                assert match and sid not in selected_tools
                tools, _ = json.JSONDecoder().raw_decode(line, match.end())
                selected_tools[sid] = [t for t in tools if t['tool'] != 'global_forensic_analyzer']
    assert set(selected_tools) == ids
    actor_manifest, observations, assets, sources = [], [], {}, {}
    order = ('global_forensic_analyzer', 'local_texture_analyzer', 'complementary_forensic_analyzer', 'provenance_inspector')
    for row in chosen:
        sid, cid = row['sample_id'], row['case_id']
        card_path = EVIDENCE / 'cards' / (sid.replace(':', '__') + '.json')
        card = json.loads(card_path.read_text(encoding='utf-8'))
        assert card['sample_id'] == sid
        assert card['tool'] == 'global_representation_analyzer'
        assert not any(k in json.dumps(card).lower() for k in
                       ('classifier_score', 'patch_logits', 'image_logit', 'probability', 'prediction', 'verdict'))
        card = copy.deepcopy(card)
        card.pop('sample_id')
        card['tool'] = 'global_forensic_analyzer'
        sources[card_path.relative_to(ROOT).as_posix()] = sha(card_path)
        for index, region in enumerate(card['most_atypical_regions'], 1):
            crop = (EVIDENCE / region['crop_path']).resolve()
            assert crop.is_relative_to(EVIDENCE.resolve()) and crop.is_file()
            dest = f'assets/{cid}_region_{index}.png'
            assets[dest] = {'local_source': crop.relative_to(ROOT).as_posix(), 'sha256': sha(crop)}
            region['crop_path'] = dest
        tools = [card, *copy.deepcopy(selected_tools[sid])]
        assert tuple(t['tool'] for t in tools) == order
        text = json.dumps(tools, ensure_ascii=False)
        assert not any(raw in text for raw in ids), 'Identity leaked into visible tool payload'
        observations.append({'sample_id': cid, 'image_sha256': row['sha256'], 'tools': tools})
        actor_manifest.append({'sample_id': cid, 'relative_path': f'assets/{cid}.png', 'sha256': row['sha256']})
        assets[f'assets/{cid}.png'] = {'remote_source': '/root/autodl-tmp/actor0-bfree-20261002/data/' + row['relative_path'], 'sha256': row['sha256']}
    for name, rows in [('actor_manifest.jsonl', actor_manifest), ('tool_results.jsonl', observations)]:
        with (OUT / name).open('x', encoding='utf-8') as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
    cards = json.loads((ROOT / 'experiments/actor_b/actor_b0_d/audit_assist/work/full/tools.json').read_text(encoding='utf-8'))['cards']
    write('tool_cards.json', cards)
    write('assets.json', assets)
    write('payload_sources.json', sources)
    write('preparation.json', {'images': 30, 'groups': 30, 'crops': len(assets) - 30,
        'gt_decoded': False, 'old_trajectories_read': False, 'selected_tool_cache_rows': 30,
        'classifier_global_replaced_by_original_evidence_only_card': True,
        'files': {p.name: sha(p) for p in OUT.iterdir() if p.is_file()},
        'local_crop_bytes': sum((ROOT / v['local_source']).stat().st_size for v in assets.values() if 'local_source' in v)})
    print(json.dumps({'images': 30, 'groups': 30, 'crops': len(assets) - 30, 'gt_decoded': False}))


if __name__ == '__main__':
    main()
