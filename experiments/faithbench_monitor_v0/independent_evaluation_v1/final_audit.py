"""Replay saved streams and verify evidence links, request boundaries and protected files."""
import io
import json
import re
import tempfile
from pathlib import Path

from api_runner import collect, ROOT
from prepare_actor import OUT, sha, write


def main():
    freeze = json.loads((OUT/'monitor_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(OUT/p)==h for p,h in freeze['files'].items())
    backup_hashes = json.loads((OUT/'actor_backup_hashes.json').read_text(encoding='utf-8'))
    assert all(sha(OUT/'actor_backup'/p)==h for p,h in backup_hashes.items())
    actor_freeze = json.loads((OUT/'actor_freeze.json').read_text(encoding='utf-8'))
    assert all(sha(ROOT/p)==h for p,h in actor_freeze['files'].items())
    before = json.loads((OUT/'actor_backup/protection_before.json').read_text())
    after = json.loads((OUT/'actor_backup/protection_after.json').read_text())
    assert before==after
    inputs = json.loads((OUT/'monitor_inputs.json').read_text(encoding='utf-8'))
    refs = json.loads((OUT/'preaudit.json').read_text(encoding='utf-8'))['cases']
    packets = json.loads((OUT/'monitor_packets.json').read_text(encoding='utf-8'))
    assessed = json.loads((OUT/'assessment.json').read_text(encoding='utf-8'))
    assessment_lock = json.loads((OUT/'assessment_lock.json').read_text())
    assert sha(OUT/'assessment.json')==assessment_lock['assessment_sha256']
    assert len(list((OUT/'api').glob('case_*/request.json')))==30
    assert json.loads((OUT/'api/completed.json').read_text())['retries']==0
    with tempfile.TemporaryDirectory() as folder:
        for reference, result in zip(refs, assessed['cases']):
            cid = reference['case_id']
            record = json.loads((OUT/f'actor_backup/output/records/{cid}.json').read_text(encoding='utf-8'))
            assert record['raw_terminal_text']==record['steps'][-1]['attempts'][-1]['raw']
            assert record['raw_terminal_text']==packets[cid]['current_raw_action']
            assert packets[cid]['trajectory']['steps'][-1]['tool_observation'] is None
            assert packets[cid]['budget']['remaining_tool_calls']==reference['remaining_tool_calls']
            case = OUT/'api'/cid
            request = json.loads((case/'request.json').read_text(encoding='utf-8'))
            assert request==dict(inputs['config'],messages=inputs['messages'][cid])
            state = json.loads((case/'state.json').read_text())
            assert state['status']=='complete' and state['response_sha256']==sha(case/'response.json')
            response = json.loads((case/'response.json').read_text(encoding='utf-8'))
            replay = collect(io.BytesIO((case/'response.sse').read_bytes()),Path(folder)/(cid+'.sse'),{})
            assert all(replay[k]==response[k] for k in replay)
            assert result['response_sha256']==sha(case/'response.json')==assessment_lock['monitor_response_hashes'][cid]
            cite = result['citation']
            assert response['content'][cite['start_character']:cite['end_character']]==cite['quote']
            assert sum(response['usage'][k] for k in ('prompt_cache_hit_tokens','prompt_cache_miss_tokens'))==response['usage']['prompt_tokens']
            assert response['usage']['completion_tokens']<=16384
    # A supplied credential must never be present in request/response, states, logs or private artifacts.
    private_files = [p for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log','.sse')]
    assert not any(re.search(rb'sk-[A-Za-z0-9]{20,}',p.read_bytes()) for p in private_files)
    write('final_audit.json', {'monitor_inputs_unchanged':True,'assessment_citations_verified':30,
        'raw_targets_verified':30,'future_last_call_observations':0,'requests_verified':30,
        'SSE_replay_verified':30,'actor_backup_verified':len(backup_hashes),'protected_files_unchanged':len(before),
        'runtime_files_unchanged':len(actor_freeze['files']),'credential_pattern_found':False,
        'researcher_confirmed':0,'GT_used':False,'feedback_executed':False,
        'monitor_freeze_sha256':sha(OUT/'monitor_freeze.json'),
        'assessment_lock_sha256':sha(OUT/'assessment_lock.json'),
        'auditor_sha256':sha(Path(__file__))})
    print('30 SSE/request/raw target/citation checks passed; old protections unchanged; no credential stored')


if __name__=='__main__':
    main()
