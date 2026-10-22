"""Lock D2 API bytes and deliver raw text; transport checks never grade semantics."""
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.faithbench_monitor_v0.monitor_mechanism_v1.prepare_d2 import OUT,CASES,load,dump,sha256
from experiments.actor_b.deepseek_monitor_pilot_v1.api_runner import collect


def transport_feedback(response, state):
    content = response.get('content') or ''
    eligible = state.get('status') == 'complete' and response.get('finish_reason') == 'stop' and bool(content.strip())
    return dict(content=content,eligible=eligible,finish_reason=response.get('finish_reason'),
                status=state.get('status','unattempted'),semantic_quality_checked=False)


def finalize():
    assert not (OUT/'api_raw_lock.json').exists(), 'exclusive finalization'
    data = load(OUT/'monitor_inputs.json')
    for manifest in [OUT/'freeze.json',OUT/'evaluation_freeze.json']:
        for name,h in load(manifest)['files'].items(): assert sha256(ROOT/name)==h,name
    for name,h in load(OUT/'protected_sources.json').items(): assert sha256(ROOT/name)==h,name
    states = [load(p) for p in (OUT/'api').glob('*/state.json')]
    assert all(s['status'] != 'submitted_no_retry' for s in states), 'API still running or uncertain; verify live handle first'
    raw = {p.relative_to(ROOT).as_posix():sha256(p) for p in (OUT/'api').rglob('*') if p.is_file()}
    dump(OUT/'api_raw_lock.json',dict(files=raw,semantic_assessment_before_Actor_lock=False))
    delivery = {cid:{} for cid in CASES}
    attempted = complete = eligible = prompt = hit = miss = completion = reasoning = 0
    seconds = 0
    for rid in data['order']:
        folder = OUT/'api'/rid
        state = load(folder/'state.json') if (folder/'state.json').exists() else {}
        response = load(folder/'response.json') if (folder/'response.json').exists() else {}
        if (folder/'request.json').exists():
            assert load(folder/'request.json') == dict(data['config'],messages=data['messages'][rid])
            attempted += 1
        if state.get('status') == 'complete':
            assert sha256(folder/'response.json') == state['response_sha256']
            with tempfile.TemporaryDirectory() as tmp:
                rebuilt = collect(io.BytesIO((folder/'response.sse').read_bytes()),Path(tmp)/'sse',{})
            assert all(response[k] == v for k,v in rebuilt.items())
            complete += 1
            usage = response['usage']
            prompt += usage['prompt_tokens']
            hit += usage['prompt_cache_hit_tokens']
            miss += usage['prompt_cache_miss_tokens']
            completion += usage['completion_tokens']
            reasoning += usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)
            seconds += response['seconds']
        item = transport_feedback(response,state)
        eligible += int(item['eligible'])
        item['response_sha256'] = sha256(folder/'response.json') if response else None
        idx = data['request_index'][rid]
        delivery[idx['case_id']][idx['condition']] = item
    assert attempted <= 8 and prompt == hit + miss
    peak = (0.006*hit+0.30*miss+1.20*completion)/1e6
    assert peak <= 0.30
    dump(OUT/'feedback_delivery.json',delivery)
    summary = dict(planned_requests=8,attempted_requests=attempted,complete_responses=complete,
        transport_eligible=eligible,requests_retried=0,prompt_tokens=prompt,cache_hit_tokens=hit,
        cache_miss_tokens=miss,completion_tokens=completion,reasoning_tokens=reasoning,
        summed_request_seconds=seconds,peak_usd_estimate=peak,billing_verified=False,
        semantic_quality_assessed=False,feedback_edited=False,old_scores_changed=False)
    dump(OUT/'api_summary.json',summary)
    dump(OUT/'feedback_lock.json',dict(files={p.relative_to(ROOT).as_posix():sha256(p)
        for p in [OUT/'feedback_delivery.json',OUT/'api_summary.json',OUT/'api_raw_lock.json',Path(__file__)]}))
    print(summary)


if __name__ == '__main__':
    finalize()
