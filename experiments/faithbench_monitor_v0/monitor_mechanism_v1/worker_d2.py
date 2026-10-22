"""D2: frozen encoding and twelve independent, bounded Actor branches."""
import copy
import gc
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.faithbench_monitor_v0.monitor_mechanism_v1.prepare_d2 import OUT, load, dump, messages
from experiments.actor_b.deepseek_monitor_pilot_v1 import gpu_worker as original
from experiments.actor_b.run_b0 import sha256, canonical_hash
from experiments.actor_b.deepseek_monitor_pilot_v1.prepare import action, tool_message

# The reused encoder reads assets relative to its experiment directory.
original.PRIVATE = OUT


def verify():
    frozen = load(ROOT/'deployment_freeze.json')
    for p, digest in frozen['files'].items():
        assert sha256(ROOT/p) == digest, p
    package = load(OUT/'inputs.json')
    original.protection()
    return package


def tensor_hash(tensor):
    return hashlib.sha256(tensor.numpy().tobytes()).hexdigest()


def cpu_original():
    import torch
    import transformers
    torch.set_num_threads(2)
    assert not torch.cuda.is_available(), 'CPU preparation must hide CUDA'
    assert str(torch.__version__) == '2.12.1+cu130' and transformers.__version__ == '4.57.4'
    package = verify()
    _, encode, limit = original.encoder(package)
    rows = {}
    for cid in package['order']:
        case = package['cases'][cid]
        encoded = encode(case['prefix'][:-1])
        count = int(encoded['input_ids'].shape[1])
        grids = encoded['image_grid_thw'].tolist()
        assert count == case['original_input_tokens'] and len(grids) == case['original_image_grids'] == 4
        rows[cid] = dict(input_tokens=count,image_grids=grids,input_ids_sha256=tensor_hash(encoded['input_ids']),
                         pixel_values_sha256=tensor_hash(encoded['pixel_values']),prefix_sha256=canonical_hash(case['prefix']))
        print(cid + ' original STOP encoding matched: ' + str(count), flush=True)
    dump(ROOT/'cpu_original.json',dict(cases=rows,model_requests=0,weights_loaded=False,truncated=False,
         torch=str(torch.__version__),transformers=transformers.__version__,context_limit=limit,
         deployment_freeze_sha256=sha256(ROOT/'deployment_freeze.json')))


def execution():
    package = verify()
    frozen = load(ROOT/'execution_freeze.json')
    for p, digest in frozen['files'].items():
        assert sha256(ROOT/p) == digest, p
    return package, load(OUT/'feedback_delivery.json'), load(OUT/'dispatcher_cache.json')


def cpu_branches():
    import torch
    torch.set_num_threads(2)
    assert not torch.cuda.is_available()
    package, delivery, cache = execution()
    _, encode, limit = original.encoder(package)
    rows = {}
    for cid in package['order']:
        case = package['cases'][cid]
        for arm in package['arm_order'][cid]:
            key = cid+'_'+arm
            if arm != 'S' and not delivery[cid][arm]['eligible']:
                rows[key] = {'status':'monitor_failure'}
                continue
            trail = messages(package,delivery,cid,arm)
            inputs = encode(trail)
            unused = [t for t in cache[cid] if t not in case['used_tools']]
            assert len(unused) == case['remaining']
            worst = int(inputs['input_ids'].shape[1])
            for sequence in itertools.permutations(unused):
                probe = copy.deepcopy(trail)
                for tool in sequence:
                    probe.append({'role':'assistant','content':'CPU context length placeholder'})
                    probe.append(tool_message(cache[cid][tool]))
                worst = max(worst,int(encode(probe)['input_ids'].shape[1]))
            upper = worst + case['remaining']*768 + 4096 + 768
            assert upper <= limit
            rows[key] = dict(status='ready',input_tokens=int(inputs['input_ids'].shape[1]),
                messages_sha256=canonical_hash(trail),input_ids_sha256=tensor_hash(inputs['input_ids']),
                pixel_values_sha256=tensor_hash(inputs['pixel_values']),image_grids=inputs['image_grid_thw'].tolist(),
                future_context_upper=upper,context_limit=limit,truncated=False)
            print(key+' CPU input ready',flush=True)
    dump(ROOT/'cpu_branches.json',dict(branches=rows,model_requests=0,weights_loaded=False,
         execution_freeze_sha256=sha256(ROOT/'execution_freeze.json')))


def run():
    import torch
    import transformers
    torch.set_num_threads(2)
    assert str(torch.__version__) == '2.12.1+cu130' and transformers.__version__ == '4.57.4'
    assert torch.cuda.is_available()
    package, delivery, cache = execution()
    expected = load(ROOT/'cpu_branches.json')
    assert expected['execution_freeze_sha256'] == sha256(ROOT/'execution_freeze.json')
    assert package['request_limit'] == 18 and package['cache_call_limit'] == 6
    assert package['generation']['max_new_tokens'] == 768 and package['generation']['seed'] == 20261006
    assert package['generation']['max_format_repairs_per_step'] == 0
    assert package['adapter'] is None and package['training_steps'] == 0
    dump(ROOT/'protection_before.json',original.protection())
    processor, encode, _ = original.encoder(package)
    output = ROOT/'output'
    output.mkdir()
    torch.manual_seed(20261006)
    torch.cuda.manual_seed_all(20261006)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(original.BASE,
        dtype=torch.bfloat16,device_map='cuda',local_files_only=True).eval()
    requests, returns = 0,0
    try:
        for cid in package['order']:
            case = package['cases'][cid]
            for arm in package['arm_order'][cid]:
                folder = output/(cid+'_'+arm)
                folder.mkdir()
                if arm != 'S' and not delivery[cid][arm]['eligible']:
                    dump(folder/'terminal.json',dict(case=cid,arm=arm,status='monitor_failure',
                        requests=0,new_tool_returns=0,parsed=None))
                    continue
                trail = messages(package,delivery,cid,arm)
                used = set(case['used_tools'])
                generated_count = 0
                terminal = None
                for i in range(case['remaining']+1):
                    assert requests < 18
                    cpu_inputs = encode(trail)
                    n = int(cpu_inputs['input_ids'].shape[1])
                    if i == 0:
                        frozen = expected['branches'][cid+'_'+arm]
                        assert canonical_hash(trail) == frozen['messages_sha256']
                        assert tensor_hash(cpu_inputs['input_ids']) == frozen['input_ids_sha256']
                        assert tensor_hash(cpu_inputs['pixel_values']) == frozen['pixel_values_sha256']
                        assert cpu_inputs['image_grid_thw'].tolist() == frozen['image_grids']
                    inputs = {k:v.to('cuda') for k,v in cpu_inputs.items()}
                    dump(folder/f'input_{i+1}.json',dict(messages=trail,messages_sha256=canonical_hash(trail),
                         used_tools=sorted(used),remaining=4-len(used),input_tokens=n))
                    torch.cuda.synchronize()
                    started = time.perf_counter()
                    with torch.inference_mode():
                        generated = model.generate(**inputs,max_new_tokens=768,do_sample=False,repetition_penalty=1.05)
                    torch.cuda.synchronize()
                    ids = generated[0,n:].tolist()
                    eos = model.generation_config.eos_token_id
                    eos = eos if isinstance(eos,list) else [eos]
                    ended = bool(ids and ids[-1] in eos)
                    raw = processor.decode(ids,skip_special_tokens=True)
                    result = dict(raw=raw,output_ids=ids,input_tokens=n,output_tokens=len(ids),
                        seconds=time.perf_counter()-started,ended_with_eos=ended,hit_token_budget=len(ids)>=768,
                        parsed=None,error=None)
                    requests += 1
                    generated_count += 1
                    try:
                        if not ended and len(ids)>=768:
                            raise ValueError('generation truncated at token budget')
                        result['parsed'] = action(raw,used,4-len(used))
                    except (ValueError,TypeError,json.JSONDecodeError) as exc:
                        result['error'] = str(exc)
                    dump(folder/f'raw_{i+1}.json',result)
                    print(cid+' '+arm+' raw saved; valid='+str(result['parsed'] is not None),flush=True)
                    if result['parsed'] is None:
                        terminal = dict(status='actor_failure',parsed=None,error=result['error'])
                        break
                    parsed = result['parsed']
                    if parsed['next_action'] == 'STOP':
                        terminal = dict(status='legal_stop',parsed=parsed)
                        break
                    tool = parsed['selected_tool']
                    assert tool in cache[cid] and tool not in used and returns < 6
                    observation = copy.deepcopy(cache[cid][tool])
                    dump(folder/f'return_{i+1}.json',dict(tool_observation=observation,sha256=canonical_hash(observation)))
                    used.add(tool)
                    returns += 1
                    trail.append({'role':'assistant','content':json.dumps(parsed,ensure_ascii=False)})
                    trail.append(tool_message(observation))
                assert terminal is not None, 'bounded branch ended without STOP or recorded failure'
                dump(folder/'terminal.json',dict(case=cid,arm=arm,**terminal,requests=generated_count,
                     new_tool_returns=len(used)-len(case['used_tools'])))
                del inputs,generated,cpu_inputs
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
        dump(ROOT/'protection_after.json',original.protection())
    dump(ROOT/'worker_completed.json',dict(branches=12,requests=requests,new_tool_returns=returns,
         new_format_retries=0,verdict_projection=False,training_steps=0,adapter=None,
         execution_freeze_sha256=sha256(ROOT/'execution_freeze.json')))
    print('D2 worker completed; no additional experiments',flush=True)


if __name__ == '__main__':
    {'cpu-original':cpu_original,'cpu-branches':cpu_branches,'run':run}[sys.argv[1]]()
