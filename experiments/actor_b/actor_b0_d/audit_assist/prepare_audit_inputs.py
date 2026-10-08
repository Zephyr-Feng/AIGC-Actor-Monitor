#!/usr/bin/env python3
"""Prepare independent blinded audit inputs, without loading evaluation outcomes."""
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
OUT = BASE / 'audit_assist'
sys.path.insert(0, str(BASE))
from run_b0_d_condition import transform_cards, canonical_to_visible
from evaluate_b0_d import extract_object, call_status_by_step, canonical_tool

CONDITIONS = {'FULL': 'full', 'PROBE-MASK': 'probe_mask', 'PROBE-DELAY': 'probe_delay', 'TOOL-RENAME': 'tool_rename'}
FORBIDDEN = {'diagnostic_category', 'generator', 'source_group', 'relative_path', 'image_relative_path',
             'ground_truth', 'gt', 'final_correct', 'effective_final_correct', 'correct', 'selection_reason',
             'canonical_action', 'selection_policy', 'verdict_log_likelihood', 'scores'}

def read(path):
    # Source trajectories contain unused evaluation metadata. Discard it at decoding.
    drop = lambda pairs: {k:v for k,v in pairs if k.lower() not in {'ground_truth','gt','diagnostic_category','generator','source_group','selection_reason'} and 'correct' not in k.lower() and 'accuracy' not in k.lower()}
    return [json.loads(line, object_pairs_hook=drop) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value, lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in value) if lines else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_text(text, encoding='utf-8')

def main():
    manifest_path = BASE / 'data/actor_input_manifest.jsonl'
    packet_path = BASE / 'evaluation/audit_packet.jsonl'
    human_path = BASE / 'evaluation/human_audit.jsonl'
    csv_path = BASE / 'evaluation/tool_selection_audit.csv'
    cards_path = ROOT / 'experiments/mini_faithbench_v0/config/tool_cards.json'
    source_hashes = {name: sha(path) for name, path in [('manifest', manifest_path), ('audit_packet', packet_path), ('human_audit', human_path), ('call_table', csv_path), ('toolcards', cards_path)]}
    assert source_hashes['toolcards'] == '4bea66b6aad42ff93ed7a4ff128b5094550e81fb72f1b8452fdfb464a98867fb'
    manifest = read(manifest_path)
    identities = {row['sample_id']: f'blind_{i:03d}' for i, row in enumerate(manifest, 1)}
    assert len(manifest) == len(identities) == 60
    packets = read(packet_path)
    packet_keys = {(p['sample_id'], p['condition']) for p in packets}
    assert len(packets) == len(packet_keys) == 80
    human = read(human_path)
    labels = ['tool_selection_quality', 'conflict_handling', 'evidence_sufficient', 'premature_stop', 'reasoning_faithful', 'stop_timing', 'unsupported_claim', 'verdict_consistent']
    human_labels = sum(any(h.get(k) is not None and h.get(k) != '' for k in labels) for h in human)
    assert len(human) == 80
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        calls = list(csv.DictReader(handle))
    assert len(calls) == 827
    assert Counter(c['condition'] for c in calls) == Counter({'FULL':189, 'PROBE-MASK':180, 'PROBE-DELAY':233, 'TOOL-RENAME':225})
    trajs = {}
    for condition, folder in CONDITIONS.items():
        path = BASE / folder / 'trajectories.jsonl'
        source_hashes[folder + '_trajectories'] = sha(path)
        rows = read(path)
        assert [r['sample_id'] for r in rows] == [r['sample_id'] for r in manifest], folder
        for row in rows:
            trajs[row['sample_id'], condition] = row
    assert len(trajs) == 240
    replacements = dict(identities)
    assets = {}
    missing = []
    image_hashes = {}
    crop_hashes = {}
    private_rows = []
    for row in manifest:
        sid, blind = row['sample_id'], identities[row['sample_id']]
        original = ROOT / 'runs/actor0-bfree-20261002/data' / row['relative_path']
        target = OUT / 'review_packets/images' / (blind + original.suffix.lower())
        assets[sid] = str(target.resolve()).replace('\\', '/')
        replacements[row['relative_path']] = assets[sid]
        replacements[str(original)] = assets[sid]
        if not original.is_file():
            missing.append(blind + ':original')
        else:
            assert sha(original) == row['sha256'], blind + ':image_sha'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            image_hashes[blind] = sha(target)
        private_rows.append({'sample_id': sid, 'blind_sample_id': blind, 'image_path': assets[sid]})
    for (sid, condition), traj in trajs.items():
        for step in traj['steps']:
            obs = step.get('tool_observation') or {}
            for i, region in enumerate(obs.get('most_atypical_regions', []), 1):
                source = region['crop_path']
                if source in replacements:
                    continue
                original = ROOT / 'experiments/probe_evidence_v1/results/output/evidence' / source
                # Region IDs are local neutral references; path remains private.
                region_id = re.sub(r'[^A-Za-z0-9_-]', '_', str(region.get('region_id', i)))
                target = OUT / 'review_packets/crops' / (identities[sid] + '_' + region_id + original.suffix.lower())
                replacements[source] = str(target.resolve()).replace('\\', '/')
                if not original.is_file():
                    missing.append(identities[sid] + ':crop:' + region_id)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(original, target)
                    crop_hashes[target.stem] = sha(target)
    def clean(value, condition):
        if isinstance(value, dict):
            return {k: clean(v, condition) for k, v in value.items() if k.lower() not in FORBIDDEN and 'correct' not in k.lower() and 'accuracy' not in k.lower()}
        if isinstance(value, list):
            return [clean(v, condition) for v in value]
        if isinstance(value, str):
            for source in sorted(replacements, key=len, reverse=True):
                value = value.replace(source, replacements[source])
                value = value.replace(source.replace(':', '__'), replacements[source])
            if condition == 'TOOL-RENAME':
                for name, alias in canonical_to_visible('tool_rename').items():
                    value = value.replace(name, alias)
            # Remaining operational image paths are not useful evidence and may expose identity.
            if re.search(r'^(?:/root/|[A-Za-z]:[\\/])', value) and not value.startswith(str(OUT.resolve()).replace('\\', '/')):
                value = 'private_source_reference'
            return value
        return value
    def crops(value):
        result = []
        if isinstance(value, dict):
            if value.get('crop_path'):
                result.append(value['crop_path'])
            for child in value.values(): result.extend(crops(child))
        elif isinstance(value, list):
            for child in value: result.extend(crops(child))
        return sorted(set(result))
    write(OUT / 'identity_map.json', {'private': True, 'blind_to_original': {v:k for k,v in identities.items()}, 'original_to_blind': identities})
    grouped = {condition: [] for condition in CONDITIONS}
    generated_keys = set()
    for i, call in enumerate(calls, 1):
        sid, condition = call['sample_id'], call['condition']
        traj = trajs[sid, condition]
        number, attempt = int(call['step']), int(call['raw_attempt'])
        step = traj['steps'][number - 1]
        assert step.get('step', number) == number
        attempts = step['attempts']
        raw = attempts[attempt]['raw']
        action = extract_object(raw)
        assert action['next_action'] == 'CALL_TOOL'
        assert (canonical_tool(action.get('selected_tool')) or action.get('selected_tool')) == call['selected_tool']
        expected_status = call_status_by_step(traj).get(number, 'rejected_by_parser_or_condition')
        if attempt < len(attempts) - 1: expected_status = 'format_retry'
        assert expected_status == call['call_status'], f'call_{i:04d}:status'
        key = sid, condition, number, attempt
        assert key not in generated_keys
        generated_keys.add(key)
        history = traj['steps'][:number - 1]
        used = sum(bool((s.get('actor_output') or {}).get('next_action') == 'CALL_TOOL') for s in history)
        prior = clean(history, condition)
        record = {'record_id': f'call_{i:04d}', 'sample_id': identities[sid], 'condition': condition,
                  'step': number, 'raw_attempt': attempt, 'selected_tool': action['selected_tool'],
                  'actor_request': clean(action, condition), 'current_raw': clean(raw, condition),
                  'history': prior, 'previous_raw_retries': clean(attempts[:attempt], condition),
                  'budget': {'max': 4, 'used_before': min(used, 4), 'remaining_before': max(4-used, 0)},
                  'exposed_tools': [v for k,v in canonical_to_visible(CONDITIONS[condition]).items() if not (condition == 'PROBE-MASK' and k == 'global_forensic_analyzer')],
                  'call_outcome': call['call_status'], 'image_path': assets[sid],
                  'observed_crop_paths': crops(prior), 'source_status': 'complete' if not missing else 'needs_source'}
        grouped[condition].append(record)
    # Independently enumerate raw CALL requests to ensure the CSV omitted none.
    actual_keys = set()
    for (sid, condition), traj in trajs.items():
        for number, step in enumerate(traj['steps'], 1):
            for attempt, item in enumerate(step['attempts']):
                try: action = extract_object(item['raw'])
                except (ValueError, TypeError, json.JSONDecodeError): continue
                if action.get('next_action') == 'CALL_TOOL': actual_keys.add((sid, condition, number, attempt))
    assert actual_keys == generated_keys
    cards = json.loads(cards_path.read_text(encoding='utf-8'))
    for condition, folder in CONDITIONS.items():
        work = OUT / 'work' / folder
        write(work / 'tools.json', {'condition': condition, 'cards': transform_cards(cards, folder, canonical_to_visible(folder)),
              'rules': '预算最多4次。只有通过格式/枚举校验而接受的CALL请求消耗预算；格式重试不消耗。成功工具不能重复调用。' + ('仅第一个accepted CALL请求global时被阻止一次，阻止仍消耗预算；下一个accepted请求可以选择global。' if folder == 'probe_delay' else '')})
        write(work / 'calls.jsonl', grouped[condition], lines=True)
        reviews = []
        for packet in packets:
            if packet['condition'] != condition: continue
            sid = packet['sample_id']
            traj = trajs[sid, condition]
            selected = {k: traj.get(k) for k in ['steps', 'tool_calls', 'raw_final_output', 'raw_terminal_text', 'raw_parse_valid', 'effective_final_output', 'effective_final_raw', 'effective_parse_valid', 'minimal_stop_policy', 'minimal_stop_projection'] if k in traj}
            record = clean(selected, condition)
            record.update(sample_id=identities[sid], condition=condition, image_path=assets[sid], source_status='complete' if not missing else 'needs_source')
            record['observed_crop_paths'] = crops(record['steps'])
            reviews.append(record)
        assert len(reviews) == 20
        write(work / 'trajectories.jsonl', reviews, lines=True)
        # Check every original ID and filename has disappeared from agent inputs.
        text = (work / 'calls.jsonl').read_text(encoding='utf-8') + (work / 'trajectories.jsonl').read_text(encoding='utf-8')
        assert not any(sid in text or sid.replace(':','__') in text for sid in identities)
        if folder == 'tool_rename':
            assert not any(name in text for name in canonical_to_visible(folder))
    assert source_hashes['human_audit'] == sha(human_path) and source_hashes['call_table'] == sha(csv_path)
    relative_hashes = {}
    for path in [manifest_path, packet_path, human_path, csv_path, cards_path, *[BASE/folder/'trajectories.jsonl' for folder in CONDITIONS.values()]]:
        relative_hashes[path.relative_to(ROOT).as_posix()] = sha(path)
    fingerprint = hashlib.sha256(json.dumps(relative_hashes, sort_keys=True).encode()).hexdigest()
    write(OUT / 'input_fingerprint.json', {'input_fingerprint': fingerprint, 'source_hashes': relative_hashes,
          'call_index': {f'call_{i:04d}': {'row_index': i-1, 'sample_id': identities[r['sample_id']], 'condition': r['condition'], 'step': int(r['step']), 'raw_attempt': int(r['raw_attempt'])} for i,r in enumerate(calls,1)},
          'image_hashes': image_hashes, 'crop_hashes': crop_hashes,
          'counts': {'source_trajectories':240,'audit_trajectories':80,'calls':827,'images':60,'crops':len(crop_hashes)}, 'missing': missing})
    summary = ['# 审计输入完整性核验', '', '日期：2026-10-08', '',
       '源提交：807cbec882c7714e43e7bcaacd53528388f2633e', '',
       f'240 条轨迹：四条件各60条，全部与无GT Actor manifest顺序一致。80条audit packet键唯一，每条件20条。',
       f'827次CALL全部一对一关联正确step/attempt，独立枚举raw CALL集合完全一致。FULL189、MASK180、DELAY233、RENAME225。',
       f'原图{len(image_hashes)}/60已验证源SHA并复制；实际观察crop {len(crop_hashes)}个已逐一验证并复制。',
       f'原human audit 80条，已有非空人工标签{human_labels}条；原human和CALL表SHA未改变。',
       '工具cards精确匹配冻结SHA；重命名条件保留实际visible alias，不给出canonical映射。',
       'CALL材料只包含该请求之前的steps/observations和当前step先前raw重试，未包含当前工具输出、未来裁片或最终STOP。',
       'accepted CALL消耗预算，格式重试不消耗；DELAY仅首个accepted CALL为global时阻止一次，阻止请求仍消耗预算。',
       'identity_map.json仅供恢复原ID，不能提供给独立审计Agent。审计材料不含诊断类别、来源组、生成器或分类正确性。', '',
       '## 缺失输入', '', *(missing or ['无缺失。']), '', '## 源SHA-256', '',
       *[f'- {name}: `{value}`' for name,value in source_hashes.items()], '', '## 中性资产SHA-256', '',
       *[f'- {name}: `{value}`' for name,value in {**image_hashes, **crop_hashes}.items()]]
    (OUT / 'INPUT_VALIDATION.md').write_text('\n'.join(summary) + '\n', encoding='utf-8')
    print(json.dumps({'trajectories':240, 'audit_trajectories':80, 'calls':827, 'images':len(image_hashes), 'crops':len(crop_hashes), 'existing_human_labels':human_labels, 'missing':missing}, ensure_ascii=True))
    if missing: raise RuntimeError('needs_source: see neutral missing IDs in INPUT_VALIDATION.md')

if __name__ == '__main__': main()
