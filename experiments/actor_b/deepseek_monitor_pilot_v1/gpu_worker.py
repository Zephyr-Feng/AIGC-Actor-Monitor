"""One frozen BF16 Actor run, independent B/C state and demand-only cache replay."""
import copy
import gc
import hashlib
import io
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from experiments.actor_b.deepseek_monitor_pilot_v1.prepare import PRIVATE, load, dump, action, tool_message
from experiments.actor_b.run_b0 import canonical_hash, sha256

BASE = Path('/root/autodl-tmp/mini-faithbench-v0/model-cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b')


def verify():
    freeze = load(PRIVATE/'execution_freeze.json')
    for name,digest in freeze['files'].items():
        assert sha256(PRIVATE/name) == digest, name
    for name,digest in freeze['dependencies'].items():
        assert sha256(ROOT/name) == digest, name
    return load(PRIVATE/'inputs.json'), load(PRIVATE/'feedback_delivery.json'), load(PRIVATE/'dispatcher_cache.json')


def messages(package,delivery,cid,arm):
    c = package['cases'][cid]
    if arm == 'C':
        assert delivery[cid]['eligible']
        feedback = '外部审核反馈：'+delivery[cid]['content']
    else:
        feedback = package['general']
    return copy.deepcopy(c['prefix']) + [{'role':'user','content':feedback+'\n\n'+package['suffix']}]


def encoder(package):
    import transformers
    from PIL import Image
    config = load(BASE/'config.json')
    assert sha256(BASE/'config.json') == package['model_spec']['model_config_sha256']
    assert BASE.name == package['model_spec']['model_revision']
    processor = transformers.AutoProcessor.from_pretrained(BASE,local_files_only=True)
    def encode(trail):
        hydrated = copy.deepcopy(trail)
        images = []
        for m in hydrated:
            if isinstance(m['content'],list):
                for p in m['content']:
                    if p.get('type') == 'image':
                        spec = package['assets'][p['image']]
                        data = (PRIVATE/spec['file']).read_bytes()
                        assert hashlib.sha256(data).hexdigest() == spec['sha256']
                        with Image.open(io.BytesIO(data)) as source:
                            im = source.convert('RGB')
                        p['image'] = im
                        images.append(im)
        text = processor.apply_chat_template(hydrated,tokenize=False,add_generation_prompt=True)
        inputs = processor(text=[text],images=images,return_tensors='pt',truncation=False)
        assert len(inputs['image_grid_thw']) == len(images)
        n = inputs['input_ids'].shape[1]
        assert n+768 <= config['text_config']['max_position_embeddings']
        return inputs
    return processor,encode,config['text_config']['max_position_embeddings']


def cpu():
    import torch
    import transformers
    torch.set_num_threads(2)
    assert torch.__version__=='2.12.1+cu130' and transformers.__version__=='4.57.4'
    package,delivery,cache = verify()
    _,encode,limit = encoder(package)
    rows = {}
    for cid in package['order']:
        for arm in package['arm_order'][cid]:
            if arm=='C' and not delivery[cid]['eligible']:
                continue
            trail = messages(package,delivery,cid,arm)
            inputs = encode(trail)
            r = package['cases'][cid]['remaining']
            # All unused returns are CPU length probes only, never actual model inputs.
            unused = [t for t in cache[cid] if t not in package['cases'][cid]['used_tools']]
            assert len(unused)==r
            worst = int(inputs['input_ids'].shape[1])
            for sequence in itertools.permutations(unused):
                probe = copy.deepcopy(trail)
                for t in sequence:
                    probe.append({'role':'assistant','content':'CPU context length placeholder'})
                    probe.append(tool_message(cache[cid][t]))
                worst = max(worst,int(encode(probe)['input_ids'].shape[1]))
            upper = worst+r*768+4096+768
            assert upper<=limit
            rows[cid+'_'+arm] = {'input_tokens':int(inputs['input_ids'].shape[1]),'input_ids_sha256':hashlib.sha256(inputs['input_ids'].numpy().tobytes()).hexdigest(),
                 'messages_sha256':canonical_hash(trail),'image_grids':inputs['image_grid_thw'].tolist(),
                 'future_context_upper':upper,'context_limit':limit,'truncated':False}
            print(cid+' '+arm+' CPU checked '+str(rows[cid+'_'+arm]['input_tokens']),flush=True)
    dump(ROOT/'cpu_preflight.json',{'branches':rows,'model_requests':0,'weights_loaded':False,'torch':torch.__version__,'transformers':transformers.__version__,
         'execution_freeze_sha256':sha256(PRIVATE/'execution_freeze.json')})


def protection():
    expected = load(PRIVATE/'expected_protection.json')
    actual = {name:{'size':Path(name).stat().st_size,'sha256':sha256(Path(name))} for name in expected}
    assert actual==expected
    return actual


def run():
    import torch
    import transformers
    torch.set_num_threads(2)
    assert torch.__version__=='2.12.1+cu130' and transformers.__version__=='4.57.4' and torch.cuda.is_available()
    package,delivery,cache = verify()
    expected = load(ROOT/'cpu_preflight.json')
    assert expected['execution_freeze_sha256']==sha256(PRIVATE/'execution_freeze.json')
    assert package['generation']['max_new_tokens']==768 and package['generation']['seed']==20261006
    assert package['adapter'] is None and package['training_steps']==0
    before = protection()
    dump(ROOT/'protection_before.json',before)
    print('25 protection hashes verified',flush=True)
    processor,encode,limit = encoder(package)
    output = ROOT/'output'
    output.mkdir()
    torch.manual_seed(20261006)
    torch.cuda.manual_seed_all(20261006)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(BASE,dtype=torch.bfloat16,device_map='cuda',local_files_only=True).eval()
    requests,returns = 0,0
    try:
        for cid in package['order']:
            case = package['cases'][cid]
            for arm in package['arm_order'][cid]:
                folder = output/(cid+'_'+arm)
                folder.mkdir()
                if arm=='C' and not delivery[cid]['eligible']:
                    dump(folder/'terminal.json',{'case':cid,'arm':arm,'status':'monitor_failure','requests':0,'new_tool_returns':0,'parsed':None})
                    continue
                trail = messages(package,delivery,cid,arm)
                used = set(case['used_tools'])
                r = case['remaining']
                record, terminal = [], None
                for i in range(r+1):
                    assert requests<80
                    cpu_inputs = encode(trail)
                    if i==0:
                        frozen = expected['branches'][cid+'_'+arm]
                        assert canonical_hash(trail)==frozen['messages_sha256']
                        assert hashlib.sha256(cpu_inputs['input_ids'].numpy().tobytes()).hexdigest()==frozen['input_ids_sha256']
                    n = int(cpu_inputs['input_ids'].shape[1])
                    inputs = {k:v.to('cuda') for k,v in cpu_inputs.items()}
                    dump(folder/f'input_{i+1}.json',{'messages':trail,'messages_sha256':canonical_hash(trail),'used_tools':sorted(used),'remaining':4-len(used),'input_tokens':n})
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
                    result = {'raw':raw,'output_ids':ids,'input_tokens':n,'output_tokens':len(ids),'seconds':time.perf_counter()-started,
                              'ended_with_eos':ended,'hit_token_budget':len(ids)>=768,'parsed':None,'error':None}
                    requests += 1
                    try:
                        if not ended and len(ids)>=768:
                            raise ValueError('generation truncated at token budget')
                        result['parsed'] = action(raw,used,4-len(used))
                    except (ValueError,TypeError,json.JSONDecodeError) as exc:
                        result['error'] = str(exc)
                    dump(folder/f'raw_{i+1}.json',result)
                    record.append(result)
                    print(cid+' '+arm+' request '+str(i+1)+' raw saved; '+str(len(ids))+' tokens; valid='+str(result['parsed'] is not None),flush=True)
                    if result['parsed'] is None:
                        terminal={'status':'actor_failure','parsed':None,'error':result['error']}
                        break
                    parsed=result['parsed']
                    if parsed['next_action']=='STOP':
                        terminal={'status':'legal_stop','parsed':parsed}
                        break
                    tool=parsed['selected_tool']
                    assert tool in cache[cid] and tool not in used and returns<40
                    observation=copy.deepcopy(cache[cid][tool])
                    dump(folder/f'return_{i+1}.json',{'tool_observation':observation,'sha256':canonical_hash(observation)})
                    used.add(tool)
                    returns+=1
                    trail.append({'role':'assistant','content':json.dumps(parsed,ensure_ascii=False)})
                    trail.append(tool_message(observation))
                assert terminal is not None, 'r+1 bound reached without legal STOP or protocol failure'
                dump(folder/'terminal.json',{'case':cid,'arm':arm,**terminal,'requests':len(record),'new_tool_returns':len(used)-len(case['used_tools'])})
                del inputs,generated,cpu_inputs
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
    dump(ROOT/'protection_after.json',protection())
    dump(ROOT/'worker_completed.json',{'requests':requests,'new_tool_returns':returns,'training_steps':0,'dtype':'bfloat16','adapter':None,'model_revision':BASE.name,
         'protection_verified':len(before),'execution_freeze_sha256':sha256(PRIVATE/'execution_freeze.json')})
    print('Worker complete; no additional experiments',flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'cpu':cpu,'run':run}[sys.argv[1]]()
