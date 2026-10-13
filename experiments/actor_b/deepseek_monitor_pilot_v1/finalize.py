"""Freeze unedited completed API content for Actor; no semantic filtering."""
import json
import shutil
from pathlib import Path
from prepare import ROOT, PRIVATE, DEPENDENCIES, load, dump, sha256, canonical_hash, no_evaluation_fields


def main():
    freeze=load(PRIVATE/'freeze.json')
    assert all(sha256(PRIVATE/n)==h for n,h in freeze['files'].items())
    assert all(sha256(ROOT/n)==h for n,h in {**freeze['scripts'],**freeze['dependencies']}.items())
    package=load(PRIVATE/'monitor_inputs.json')
    complete=load(PRIVATE/'api/completed.json')
    assert complete['requests']==20 and complete['retries']==0
    delivery={}
    for cid in package['order']:
        folder=PRIVATE/'api'/cid
        request=load(folder/'request.json')
        assert request==dict(package['config'],messages=package['messages'][cid])
        response=load(folder/'response.json')
        state=load(folder/'state.json')
        assert state['status']=='complete' and state['response_sha256']==sha256(folder/'response.json')
        refused=False
        for line in (folder/'response.sse').read_bytes().splitlines():
            if line.startswith(b'data:') and line[5:].strip()!=b'[DONE]':
                chunk=json.loads(line[5:])
                refused |= any(bool(c.get('delta',{}).get('refusal')) for c in chunk.get('choices',[]))
        eligible=response['finish_reason']=='stop' and bool(response['content'].strip()) and not refused
        delivery[cid]={'eligible':eligible,'content':response['content'] if eligible else None,'finish_reason':response['finish_reason'],
                       'refusal_field':refused,'response_sha256':sha256(folder/'response.json'),'content_sha256':canonical_hash(response['content'])}
    no_evaluation_fields(delivery)
    dump(PRIVATE/'feedback_delivery.json',delivery)
    shutil.copyfile(ROOT/'experiments/faithbench_monitor_v0/private/binding_table_probe_v1_20261011/expected_protection.json',PRIVATE/'expected_protection.json')
    names=['inputs.json','dispatcher_cache.json','feedback_delivery.json','expected_protection.json']+[p.relative_to(PRIVATE).as_posix() for p in (PRIVATE/'assets').iterdir()]
    dependencies={n:sha256(ROOT/n) for n in DEPENDENCIES}
    for p in Path(__file__).parent.glob('*.py'):
        dependencies[p.relative_to(ROOT).as_posix()]=sha256(p)
    for name in ['experiments/actor_b/feedback_pilot_v1/pilot.py','experiments/faithbench_monitor_v0/monitor_protocol.py']:
        dependencies[name]=sha256(ROOT/name)
    dump(PRIVATE/'execution_freeze.json',{'files':{n:sha256(PRIVATE/n) for n in names},'dependencies':dependencies,
       'api_files':{p.relative_to(PRIVATE).as_posix():sha256(p) for p in (PRIVATE/'api').rglob('*') if p.is_file()},'preparation_freeze_sha256':sha256(PRIVATE/'freeze.json')})
    print('20 API responses locked; eligible='+str(sum(d['eligible'] for d in delivery.values()))+'; no feedback rewriting')


if __name__=='__main__':
    main()
