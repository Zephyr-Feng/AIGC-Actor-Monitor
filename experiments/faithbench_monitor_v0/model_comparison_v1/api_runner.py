"""Six exclusive API requests; credential stays in memory and responses stay private."""
import getpass
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from experiments.faithbench_monitor_v0.model_comparison_v1.prepare import (
    PRIVATE, canonical_hash, sha256, write_json)


def collect(stream, destination, progress):
    chunks = []
    done = False
    with destination.open('xb') as output:
        for line in stream:
            output.write(line)
            output.flush()
            if not line.startswith(b'data:'):
                continue
            payload = line[5:].strip()
            if payload == b'[DONE]':
                done = True
                break
            chunk = json.loads(payload)
            if 'error' in chunk:
                raise ValueError('service returned an error chunk')
            chunks.append(chunk)
            progress['chunks'] = len(chunks)
    assert done and chunks, 'Incomplete SSE; do not repeat this request'
    content, reasoning = [], []
    finish, usage = None, None
    for chunk in chunks:
        if chunk.get('usage'):
            usage = chunk['usage']
        for choice in chunk.get('choices', []):
            assert choice['index'] == 0
            delta = choice.get('delta', {})
            content.append(delta.get('content') or '')
            reasoning.append(delta.get('reasoning_content') or '')
            if choice.get('finish_reason'):
                finish = choice['finish_reason']
    assert finish is not None and usage is not None, 'Missing finish or usage'
    return {'id': chunks[0]['id'], 'model': chunks[0]['model'],
            'system_fingerprint': chunks[0].get('system_fingerprint'),
            'created': chunks[0].get('created'), 'finish_reason': finish,
            'content': ''.join(content), 'reasoning_content': ''.join(reasoning),
            'usage': usage, 'stream_chunks': len(chunks)}


def self_check():
    import io
    import tempfile
    chunks = [{'id': 'fixture', 'model': 'fixture', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'r'}}]},
              {'id': 'fixture', 'model': 'fixture', 'choices': [{'index': 0, 'delta': {'content': '回答'}, 'finish_reason': 'stop'}],
               'usage': {'prompt_tokens': 2, 'completion_tokens': 3}}]
    data = b': heartbeat\n\n' + b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks) + b'data: [DONE]\n'
    with tempfile.TemporaryDirectory() as folder:
        result = collect(io.BytesIO(data), Path(folder) / 'sse', {})
        assert result['content'] == '回答' and result['reasoning_content'] == 'r'
        assert result['finish_reason'] == 'stop' and result['usage']['completion_tokens'] == 3
        try:
            collect(io.BytesIO(data.replace(b'data: [DONE]\n', b'')), Path(folder) / 'incomplete', {})
        except AssertionError:
            pass
        else:
            raise AssertionError('Incomplete stream must fail')
    print('SSE self-check passed; no network requests', flush=True)


def main():
    freeze = json.loads((PRIVATE / 'freeze.json').read_text(encoding='utf-8'))
    assert all(sha256(PRIVATE / n) == h for n, h in freeze['files'].items())
    package = json.loads((PRIVATE / 'inputs.json').read_text(encoding='utf-8'))
    assert package['b_request_limit'] == 6 and not (PRIVATE / 'api').exists()
    warnings.simplefilter('error', getpass.GetPassWarning)
    key = getpass.getpass('API credential (hidden input): ').strip()
    assert key.startswith('sk-') and '\n' not in key and len(key) > 20
    output = PRIVATE / 'api'
    output.mkdir()
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    # Only official endpoint; no redirects carrying a credential to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    models_request = urllib.request.Request('https://api.deepseek.com/models', headers=headers)
    try:
        with opener.open(models_request, timeout=30) as response:
            models = json.load(response)
    except urllib.error.HTTPError as error:
        write_json(output / 'service_error.json', {'stage': 'models', 'http_status': error.code, 'inference_requests': 0})
        print('Model verification failed, HTTP ' + str(error.code) + '; no inference', flush=True)
        return
    write_json(output / 'models.json', models)
    assert 'deepseek-flash' in [m['id'] for m in models['data']], 'Requested model unavailable; no substitution'
    print('Official model alias verified; six requests only', flush=True)
    for cid in package['b_order']:
        case_dir = output / cid
        case_dir.mkdir()
        body = dict(package['b_config'], messages=package['cases'][cid]['messages'])
        write_json(case_dir / 'request.json', body)
        state = {'case': cid, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 'messages_sha256': canonical_hash(body['messages']), 'status': 'submitted_no_retry'}
        write_json(case_dir / 'state.json', state)
        request = urllib.request.Request(package['endpoint'], data=json.dumps(body, ensure_ascii=False).encode(), headers=headers, method='POST')
        progress = {'chunks': 0}
        stop = threading.Event()
        started = time.monotonic()
        def heartbeat():
            while not stop.wait(25):
                print(cid + ' waiting/streaming: ' + str(progress['chunks']) + ' chunks, ' + str(round(time.monotonic() - started)) + 's', flush=True)
        watcher = threading.Thread(target=heartbeat, daemon=True)
        watcher.start()
        try:
            with opener.open(request, timeout=180) as response:
                state['request_id_header'] = response.headers.get('x-request-id')
                result = collect(response, case_dir / 'response.sse', progress)
            result['seconds'] = time.monotonic() - started
            assert result['model'] == 'deepseek-flash'
            write_json(case_dir / 'response.json', result)
            state.update(status='complete', finish_reason=result['finish_reason'], response_sha256=sha256(case_dir / 'response.json'))
            write_json(case_dir / 'state.json', state)
            print(cid + ' complete: ' + result['finish_reason'] + ', usage=' + json.dumps(result['usage']), flush=True)
        except Exception as error:
            # Do not log exception text or request headers containing credentials.
            state.update(status='failed_or_uncertain_no_retry', error_type=type(error).__name__,
                         http_status=getattr(error, 'code', None), seconds=time.monotonic() - started)
            write_json(case_dir / 'state.json', state)
            print(cid + ' stopped: ' + type(error).__name__ + '; no automatic retry', flush=True)
            return
        finally:
            stop.set()
            watcher.join(timeout=1)
    write_json(output / 'completed.json', {'requests': 6, 'retries': 0, 'case_order': package['b_order']})
    key = None
    print('API batch completed; no further requests', flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--self-check' in sys.argv:
        self_check()
    else:
        main()
