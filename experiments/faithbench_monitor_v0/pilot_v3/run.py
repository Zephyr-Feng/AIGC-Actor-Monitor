"""Paired offline Monitor conditions, bounded HTTP, durable per-request logs."""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from protocol import BASE, ROOT, render_request, response_schema
from experiments.faithbench_monitor_v0.pilot_v2.protocol import parse_response


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(source):
    if sha(source / 'manifest.json') != 'a0cea96066cc0b20f25e5dd57e1b5489b6a302dd6ac720774760016f85b23a17':
        raise ValueError('not frozen v2 manifest')
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf8'))
    for name, expected in manifest['protocol_hashes'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('frozen v2 dependency changed: ' + name)
    for name, expected in manifest['artifact_hashes'].items():
        if sha(source / name) != expected:
            raise ValueError('frozen v2 input changed: ' + name)
    packets = list(map(json.loads, (source / 'inputs.jsonl').read_text(encoding='utf8').splitlines()))
    if [p['case_id'] for p in packets] != manifest['case_ids']:
        raise ValueError('frozen case order changed')
    return manifest, packets


def prepare(source, target):
    original, packets = validate(source)
    target.mkdir(parents=True, exist_ok=False)
    (target / "inputs.jsonl").write_bytes((source / "inputs.jsonl").read_bytes())
    schedule = []
    for i, packet in enumerate(packets):
        cid = packet["case_id"]
        raw = (source / f"{cid}_request.txt").read_text(encoding="utf8")
        for condition in (["schema_control", "role_alignment"] if i % 2 == 0 else ["role_alignment", "schema_control"]):
            name = f"{cid}_{condition}"
            (target / f"{name}.txt").write_text(render_request(packet, raw, condition), encoding="utf8")
            (target / f"{name}.schema.json").write_text(json.dumps(response_schema(packet), ensure_ascii=False), encoding="utf8")
            schedule.append({"case_id": cid, "condition": condition, "name": name})
    manifest = {"source_manifest_sha256": sha(source / "manifest.json"), "schedule": schedule,
                "generation": original["generation"], "purpose": "adaptive_development_not_independent_test",
                "annotations_in_requests": False, "actor_actions_executed": False,
                "protocol_hashes": {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p)
                                    for p in sorted(BASE.iterdir()) if p.is_file()},
                "artifact_hashes": {p.name: sha(p) for p in target.iterdir() if p.is_file()}}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"prepared_requests": len(schedule), "manifest_sha256": sha(target / "manifest.json")}))


def http(path, body, timeout=120):
    req = urllib.request.Request("http://127.0.0.1:8089" + path, data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def run(inputs, output):
    manifest = json.loads((inputs / "manifest.json").read_text(encoding="utf8"))
    for name, wanted in manifest["artifact_hashes"].items():
        if sha(inputs / name) != wanted:
            raise ValueError("input changed: " + name)
    for name, wanted in manifest["protocol_hashes"].items():
        if sha(ROOT / name) != wanted:
            raise ValueError("experimental code changed: " + name)
    packets = {p["case_id"]: p for p in map(json.loads, (inputs / "inputs.jsonl").read_text(encoding="utf8").splitlines())}
    if output.exists():
        raise FileExistsError("new output directory required")
    output.mkdir(parents=True)
    runtime = {"manifest_sha256": sha(inputs / "manifest.json"), "started_at": time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               "generation": manifest["generation"], "http_timeout_seconds": 120, "actor_actions_executed": False,
               "annotations_read": False, "thinking": False, "retries": 0,
               "model": "Qwen3.5-27B-Q4_K_M", "backend": "b11517/8a1a9b512"}
    (output / "runtime.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf8")
    lengths = []
    for item in manifest["schedule"]:
        request = (inputs / (item['name'] + '.txt')).read_text(encoding="utf8")
        template = http('/apply-template', {"messages": [{"role": "user", "content": request}],
                                            "add_generation_prompt": True, "chat_template_kwargs": {"enable_thinking": False}}, 20)
        prompt = template['prompt']
        count = len(http('/tokenize', {"content": prompt, "add_special": False}, 20)['tokens'])
        if count + manifest['generation']['max_new_tokens'] > 24576:
            raise ValueError("context exceeds frozen server limit")
        lengths.append({**item, "native_prompt_tokens": count, "thinking_end_marker": prompt.endswith('</think>\n\n')})
    (output / 'native_preflight.json').write_text(json.dumps(lengths, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({"preflight_requests": len(lengths), "max_input_tokens": max(x['native_prompt_tokens'] for x in lengths)}), flush=True)
    with (output / 'responses.jsonl').open('x', encoding='utf8') as handle:
        for i, item in enumerate(manifest['schedule'], 1):
            print(json.dumps({"event": "request_start", "index": i, "total": len(manifest['schedule']),
                              **item, "at": time.strftime('%Y-%m-%dT%H:%M:%S%z')}), flush=True)
            started = time.monotonic()
            request = (inputs / (item['name'] + '.txt')).read_text(encoding='utf8')
            schema = json.loads((inputs / (item['name'] + '.schema.json')).read_text(encoding='utf8'))
            body = {"messages": [{"role": "user", "content": request}], "temperature": 0, "seed": 42,
                    "repeat_penalty": 1.05, "cache_prompt": False, "max_tokens": 4096,
                    "chat_template_kwargs": {"enable_thinking": False},
                    "response_format": {"type": "json_object", "schema": schema}}
            row = {**item}
            try:
                result = http('/v1/chat/completions', body)
                choice = result['choices'][0]
                row.update(raw=choice['message']['content'], finish_reason=choice['finish_reason'],
                           reasoning_content=choice['message'].get('reasoning_content'), usage=result.get('usage'),
                           timings=result.get('timings'))
                try:
                    row.update(parse_valid=True, checked=parse_response(row['raw'], packets[item['case_id']]))
                except (ValueError, TypeError, KeyError) as exc:
                    row.update(parse_valid=False, parse_error=str(exc))
            except Exception as exc:
                row.update(parse_valid=False, request_error=f'{type(exc).__name__}: {exc}')
            row['seconds'] = round(time.monotonic() - started, 4)
            handle.write(json.dumps(row, ensure_ascii=False) + '\n'); handle.flush()
            print(json.dumps({"event": "request_end", "index": i, "parse_valid": row['parse_valid'],
                              "seconds": row['seconds'], "error": row.get('request_error', row.get('parse_error'))}), flush=True)
            if 'request_error' in row:
                raise RuntimeError('HTTP failed; preserve partial output and inspect server before any new request')
    runtime['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    (output / 'runtime.json').write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding='utf8')
    print('Completed paired conditions. No Actor actions executed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--prepare', type=Path)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.source, args.prepare)
    else:
        run(args.inputs, args.output)
