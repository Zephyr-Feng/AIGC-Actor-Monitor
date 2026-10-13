"""Local, model-free context compatibility check; no execution packet or experiment."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/actor_b/actor_b0_d'))
sys.path.insert(0, str(ROOT / 'experiments/actor_b'))
from contract_replay import reconstruct_stop_context
from run_b0_d_condition import condition_material, canonical_to_visible
from run_b0 import canonical_hash, sha256, write_json

BASE = ROOT / 'experiments/faithbench_monitor_v0/private/natural_actor_monitor_20261013'
D1B = BASE.parent / 'mechanism_d1b_20261013'
OUT = BASE.parent / 'mechanism_d2_readiness_20261013'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))


def main():
    assert not (OUT / 'context_check.json').exists(), 'do not replace a prior check'
    frozen = read(BASE / 'actor_freeze.json')
    assert all(sha256(ROOT / p) == h for p, h in frozen['files'].items())
    freeze = read(D1B / 'freeze.json')
    for group in ('files', 'original_sources_sha256'):
        assert all(sha256(ROOT / p) == h for p, h in freeze[group].items())
    actor = ROOT / 'experiments/actor_b'
    original_prompt = (actor / 'prompts/system_prompt.txt').read_text(encoding='utf-8').strip()
    original_cards, original_schema = read(BASE/'tool_cards.json'), read(actor/'schemas/actor_b_action.schema.json')
    prompt, schema, cards, allowed = condition_material('full', original_prompt, original_schema, original_cards)
    assert (prompt, schema, cards) == (original_prompt, original_schema, original_cards)
    assert all(k == v for k, v in canonical_to_visible('full').items())
    generation = read(actor/'config/generation_config.json')
    assert canonical_hash(dict(system_prompt=prompt,tool_cards=cards,schema=schema,generation=generation)) == read(BASE/'baseline_runtime.json')['prompt_sha256']
    packet = read(D1B/'monitor_packets.json')['M1']
    backup = read(BASE/'actor_backup_hashes.json')
    rows, sources = {}, {}
    for cid in ('case_005','case_016','case_017','case_028'):
        path = BASE/'actor_backup/output/records'/(cid+'.json')
        assert sha256(path) == backup['output/records/'+cid+'.json']
        row = read(path)
        assert row['condition'] == 'full'
        assert all(s['call_status']=='success' for s in row['steps'][:-1])
        prefix, raw = reconstruct_stop_context(row, row['relative_path'], prompt, cards, schema, lambda p:p, 4)
        assert raw == row['raw_terminal_text'] == packet[cid]['current_raw_action']
        prefix.append(dict(role='assistant',content=raw))
        branches = {arm:copy.deepcopy(prefix) for arm in ('S','G','M')}
        branches['S'][0]['content']='isolation fixture'
        assert branches['G'] == branches['M'] == prefix
        image_paths = [part['image'] for message in prefix if isinstance(message['content'],list)
            for part in message['content'] if part.get('type')=='image']
        assert all(p in frozen['assets'] for p in image_paths)
        rows[cid] = dict(prefix_sha256=canonical_hash(prefix),raw_sha256=canonical_hash(raw),
            record_sha256=sha256(path),used_tools=row['tool_calls'],remaining=4-len(row['tool_calls']),
            final_attempts=len(row['steps'][-1]['attempts']),raw_legal=row['raw_parse_valid'],
            image_placeholders=len(image_paths),images_local_at_recorded_paths=sum((ROOT/p).is_file() for p in image_paths),
            original_stop_input_tokens=row['steps'][-1]['attempts'][-1]['input_tokens'],
            original_stop_image_grids=row['steps'][-1]['attempts'][-1]['image_grids'])
        sources[path.relative_to(ROOT).as_posix()] = sha256(path)
    assert sum(r['remaining']+1 for r in rows.values())*3 == 18
    assert sum(r['remaining'] for r in rows.values())*3 == 6
    OUT.mkdir(exist_ok=True)
    report = dict(scope='four previously exposed cases; context structure only, not runtime readiness',
        cases=rows,checks=dict(full_material_identity=True,raw_target_identical=True,format_retry_history_preserved=True,
            deep_copy_isolation=True,old_sources_unchanged=True),sources_sha256=sources,
        proposed_three_intervention_arm_upper=dict(actor_generations=18,cache_returns=6,output_tokens=18*768),
        requests_sent=0,weights_loaded=False,tokenizer_loaded=False,server_contacted=False,
        pending=['original image/crop locations and hashes','real processor input reconstruction','approval of design and runtime budgets'],
        exposure_note='assets index inspection exposed the source-directory category for case_005; these cases are development data, not independently blinded evaluation')
    write_json(OUT/'context_check.json',report)
    write_json(OUT/'context_check_lock.json',dict(files={p.relative_to(ROOT).as_posix():sha256(p)
        for p in [OUT/'context_check.json',Path(__file__),*[(ROOT/p) for p in sources]]}))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
