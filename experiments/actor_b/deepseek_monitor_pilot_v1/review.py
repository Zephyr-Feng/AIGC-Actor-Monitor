"""Lock raw outputs and make condition-hidden review copies; no adjudication here."""
import copy
import json
import random
from pathlib import Path
from prepare import PRIVATE, load, dump, sha256, canonical_hash, action, tool_message
from gpu_worker import messages


def make():
    package=load(PRIVATE/'inputs.json')
    delivery=load(PRIVATE/'feedback_delivery.json')
    cache=load(PRIVATE/'dispatcher_cache.json')
    completed=load(PRIVATE/'backup/worker_completed.json')
    assert completed['requests']<=80 and completed['new_tool_returns']<=40 and completed['training_steps']==0
    backup=load(PRIVATE/'backup_hashes.json')
    assert all(sha256(PRIVATE/'backup'/n)==h for n,h in backup.items())
    rows=[]
    total_requests,total_returns=0,0
    for cid in package['order']:
        for arm in package['arm_order'][cid]:
            folder=PRIVATE/'backup/output'/(cid+'_'+arm)
            terminal=load(folder/'terminal.json')
            trail=messages(package,delivery,cid,arm)
            used=set(package['cases'][cid]['used_tools'])
            raw_files=sorted(folder.glob('raw_*.json'))
            assert len(raw_files)==terminal['requests']<=package['cases'][cid]['remaining']+1
            steps=[]
            for i,path in enumerate(raw_files,1):
                snapshot=load(folder/f'input_{i}.json')
                assert snapshot['messages']==trail and snapshot['messages_sha256']==canonical_hash(trail)
                assert snapshot['remaining']==4-len(used) and set(snapshot['used_tools'])==used
                result=load(path)
                parsed=None
                try:
                    if not result['ended_with_eos'] and result['hit_token_budget']:
                        raise ValueError('generation truncated at token budget')
                    parsed=action(result['raw'],used,4-len(used))
                except (ValueError,TypeError,json.JSONDecodeError):
                    assert result['parsed'] is None
                assert parsed==result['parsed']
                step={'raw':result['raw'],'parsed':parsed,'error':result['error'],'input_tokens':result['input_tokens'],
                      'output_tokens':result['output_tokens'],'seconds':result['seconds'],'ended_with_eos':result['ended_with_eos']}
                if parsed and parsed['next_action']=='CALL_TOOL':
                    tool=parsed['selected_tool']
                    returned=load(folder/f'return_{i}.json')
                    assert returned['tool_observation']==cache[cid][tool] and returned['sha256']==canonical_hash(cache[cid][tool])
                    step['tool_observation']=copy.deepcopy(cache[cid][tool])
                    used.add(tool)
                    trail.append({'role':'assistant','content':json.dumps(parsed,ensure_ascii=False)})
                    trail.append(tool_message(cache[cid][tool]))
                    total_returns+=1
                else:
                    assert i==len(raw_files)
                steps.append(step)
            assert terminal['new_tool_returns']==len(used)-len(package['cases'][cid]['used_tools'])
            assert terminal['parsed']==steps[-1]['parsed'] if terminal['status']=='legal_stop' else terminal['parsed'] is None
            total_requests+=len(raw_files)
            rows.append((cid,arm,steps,terminal))
    assert len(rows)==40 and total_requests==completed['requests'] and total_returns==completed['new_tool_returns']
    dump(PRIVATE/'raw_output_lock.json',{'files':backup,'api_files':load(PRIVATE/'execution_freeze.json')['api_files'],
         'history_sha256':sha256(PRIVATE/'historical_A.json'),'input_sha256':sha256(PRIVATE/'inputs.json'),
         'requests':total_requests,'cache_returns':total_returns,'gt_read':False,'full_input_time_boundary_check':True,'all_return_facts_match':True})
    packets=load(PRIVATE/'monitor_packets.json')
    random.Random(20261012).shuffle(rows)
    mapping={}
    review={}
    for i,(cid,arm,steps,terminal) in enumerate(rows,1):
        rid='review_'+str(i).zfill(2)
        mapping[rid]={'case':cid,'arm':arm}
        review[rid]={'case_id':cid,'original':packets[cid],
            'assets':{'image':'assets/'+cid+'.png','crops':['assets/'+cid+'_'+r+'.png' for r in ['R1','R2','R3']]},
            'external_message':messages(package,delivery,cid,arm)[-1]['content'],
            'new_steps':steps,'terminal':{k:v for k,v in terminal.items() if k not in ['arm','case']}}
    dump(PRIVATE/'review_mapping.json',mapping)
    dump(PRIVATE/'review_packets.json',review)
    dump(PRIVATE/'review_criteria.json',{'criteria':load(PRIVATE/'preaudit.json')['criteria'],
         'reviewer':'same assistant, hidden condition names; style/history may reveal condition',
         'gt_read':False,'independent_gold':False,'preaudit_sha256':sha256(PRIVATE/'preaudit.json'),
         'raw_lock_sha256':sha256(PRIVATE/'raw_output_lock.json')})
    print(json.dumps({'raw_requests':total_requests,'cache_returns':total_returns,'hidden_packets':40,'full_input_and_cache_checks':True,'gt_read':False}))


if __name__=='__main__':
    make()
