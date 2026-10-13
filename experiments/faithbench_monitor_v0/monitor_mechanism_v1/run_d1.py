"""Eight approved development requests; reuse the frozen SSE collector."""
import getpass
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.actor_b.deepseek_monitor_pilot_v1.api_runner import collect, self_check
from experiments.actor_b.run_b0 import canonical_hash, sha256, write_json

OUT = ROOT / 'experiments/faithbench_monitor_v0/private/mechanism_d1_20261013'


def package():
    freeze = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
    assert all(sha256(ROOT / path) == h for path, h in freeze['files'].items())
    data = json.loads((OUT / 'monitor_inputs.json').read_text(encoding='utf-8'))
    assert data['request_limit'] == len(set(data['order'])) == len(data['messages']) == 8
    assert data['peak_usd_cost_bound'] <= data['usd_cap'] == 0.30
    assert data['endpoint'] == 'https://api.deepseek.com/chat/completions'
    assert data['config']['model'] == 'deepseek-flash' and data['config']['max_tokens'] == 16384
    return data


def main():
    data = package()
    assert not (OUT / 'api').exists(), 'exclusive batch; no restart or retries'
    warnings.simplefilter('error', getpass.GetPassWarning)
    key = getpass.getpass('API credential (hidden input): ').strip()
    assert key.startswith('sk-') and '\n' not in key and len(key) > 20
    output = OUT / 'api'
    output.mkdir()
    write_json(output / 'execution.json', {'runner_sha256': sha256(Path(__file__)),
        'collector_sha256': sha256(ROOT / 'experiments/actor_b/deepseek_monitor_pilot_v1/api_runner.py'),
        'freeze_sha256': sha256(OUT / 'freeze.json'), 'request_limit': 8, 'usd_cap': 0.30})
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(urllib.request.Request('https://api.deepseek.com/models', headers=headers), timeout=30) as response:
            models = json.load(response)
    except urllib.error.HTTPError as error:
        write_json(output / 'service_error.json', {'stage': 'models', 'http_status': error.code, 'inference_requests': 0})
        print('Model verification failed: HTTP ' + str(error.code), flush=True)
        return
    write_json(output / 'models.json', models)
    assert 'deepseek-flash' in [m['id'] for m in models['data']]
    print('Official model verified; eight requests, no retries', flush=True)
    for rid in data['order']:
        case = output / rid
        case.mkdir()
        body = dict(data['config'], messages=data['messages'][rid])
        write_json(case / 'request.json', body)
        state = {'request': rid, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'messages_sha256': canonical_hash(body['messages']), 'status': 'submitted_no_retry'}
        write_json(case / 'state.json', state)
        request = urllib.request.Request(data['endpoint'], data=json.dumps(body, ensure_ascii=False).encode(), headers=headers, method='POST')
        progress, stop, started = {'chunks': 0}, threading.Event(), time.monotonic()

        def heartbeat():
            while not stop.wait(25):
                print(rid + ' streaming: ' + str(progress['chunks']) + ' chunks, ' + str(round(time.monotonic() - started)) + 's', flush=True)

        watcher = threading.Thread(target=heartbeat, daemon=True)
        watcher.start()
        try:
            with opener.open(request, timeout=180) as response:
                state['request_id_header'] = response.headers.get('x-request-id')
                result = collect(response, case / 'response.sse', progress)
            result['seconds'] = time.monotonic() - started
            assert result['model'] == 'deepseek-flash'
            write_json(case / 'response.json', result)
            state.update(status='complete', finish_reason=result['finish_reason'], response_sha256=sha256(case / 'response.json'))
            write_json(case / 'state.json', state)
            print(rid + ' complete: ' + result['finish_reason'] + ', usage=' + json.dumps(result['usage']), flush=True)
        except Exception as error:
            # Exception text can contain credentials; only type/status are saved.
            state.update(status='failed_or_uncertain_no_retry', error_type=type(error).__name__,
                http_status=getattr(error, 'code', None), seconds=time.monotonic() - started)
            write_json(case / 'state.json', state)
            print(rid + ' failed/uncertain: ' + type(error).__name__ + '; no retry', flush=True)
            return
        finally:
            stop.set()
            watcher.join(timeout=1)
    write_json(output / 'completed.json', {'requests': 8, 'retries': 0, 'request_order': data['order']})
    key = None
    print('API batch completed', flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--self-check' in sys.argv:
        self_check()
        package()
        print('D1 freeze and eight-request boundary verified')
    else:
        main()
