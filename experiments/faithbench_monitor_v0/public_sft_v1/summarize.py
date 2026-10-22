"""Audit saved outputs on CPU, preserving the original frozen scoring."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import random
import struct

from train import read_rows, score


def relaxed_decision(raw):
    """Supplemental format sensitivity only: allow one explicit schema wrapper."""
    try:
        value = json.loads(raw)
        if isinstance(value, dict) and '输出结构' in value:
            value = value['输出结构']
        if (isinstance(value, dict) and isinstance(value.get('问题片段'), list)
                and value.get('判定') in ('存在来源忠实性问题', '未标注来源忠实性问题')):
            return value['判定']
    except (ValueError, TypeError):
        pass
    return None


def quote_matches(response, quote):
    if not isinstance(quote, str) or not quote:
        return 0
    count, start = 0, 0
    while (position := response.find(quote, start)) >= 0:
        count += 1
        start = position + 1
    return count


def run(root, data):
    before, after = read_rows(root/'before.jsonl'), read_rows(root/'after.jsonl')
    expected_ids = json.loads((root.parent/'development_ids.json').read_text(encoding='utf8'))
    assert [r['id'] for r in before] == [r['id'] for r in after] == expected_ids
    validation = {r['id']:r for r in read_rows(data/'validation.primary.sft.jsonl')}
    assert len(expected_ids) == len({validation[i]['group'] for i in expected_ids}) == 64
    result = {'development_rows':64, 'independent_test':False, 'new_model_calls':0,
              'original_scoring_preserved':True, 'phases':{}}
    for phase, rows in [('before',before), ('after',after)]:
        nonempty, nonempty_valid = [], []
        quotes = {'absent':0, 'unique':0, 'repeated':0}
        decisions = []
        for row in rows:
            original = validation[row['id']]
            target = json.loads(original['messages'][-1]['content'])
            response = json.loads(original['messages'][1]['content'])['材料']['待核回答']
            checked = score(row['raw'], target, response)
            assert all(row.get(k) == v for k,v in checked.items()), (phase,row['id'])
            decisions.append(relaxed_decision(row['raw']))
            if row['json_valid']:
                spans = json.loads(row['raw'])['问题片段']
                if spans:
                    nonempty.append(row['id'])
                    if row['span_offsets_valid']:
                        nonempty_valid.append(row['id'])
                    for span in spans:
                        matches = quote_matches(response, span.get('原文'))
                        quotes['absent' if matches == 0 else 'unique' if matches == 1 else 'repeated'] += 1
        summary = json.loads((root/f'{phase}.summary.json').read_text())
        for key in ('json_valid','status_correct','exact_spans','span_offsets_valid','hit_token_cap'):
            assert summary[key] == sum(r[key] for r in rows)
        assert abs(summary['mean_sequence_loss']-sum(r['loss'] for r in rows)/64)<1e-12
        error = [r for r in rows if r['gold_has_error']]
        clean = [r for r in rows if not r['gold_has_error']]
        result['phases'][phase] = {**summary,
            'error_rows_exact_spans':sum(r['exact_spans'] for r in error),
            'clean_rows_exact_spans':sum(r['exact_spans'] for r in clean),
            'false_positive_valid_decisions':sum(r.get('predicted_error',False) for r in clean),
            'false_negative_valid_decisions':sum(r['json_valid'] and not r.get('predicted_error',False) for r in error),
            'invalid_outputs_error':sum(not r['json_valid'] for r in error),
            'invalid_outputs_clean':sum(not r['json_valid'] for r in clean),
            'nonempty_span_outputs':len(nonempty), 'nonempty_all_offsets_valid':len(nonempty_valid),
            'predicted_quote_occurrences_in_response':quotes,
            'single_wrapper_sensitivity':{'readable':sum(x is not None for x in decisions),
                'correct':sum(x == json.loads(validation[r['id']]['messages'][-1]['content'])['判定'] for x,r in zip(decisions,rows))}}
    common = [i for i,(b,a) in enumerate(zip(before,after))
              if relaxed_decision(b['raw']) is not None and a['json_valid']]
    result['supplemental_paired_readable'] = {'rows':len(common),
        'before_correct':sum(relaxed_decision(before[i]['raw']) == json.loads(validation[before[i]['id']]['messages'][-1]['content'])['判定'] for i in common),
        'after_correct':sum(after[i]['status_correct'] for i in common),
        'posthoc_not_primary':True}
    train = read_rows(root/'training.jsonl')
    assert len(train) == train[-1]['update'] == 1518
    assert all(r['update']==i+1 and r['samples']==min((i+1)*8,12141) for i,r in enumerate(train))
    assert train[-1]['seen_tokens'] == 11536649
    assert all(math.isfinite(r['loss']) and math.isfinite(r['grad_norm']) for r in train)
    events = []
    for filename in ('worker.log','resume.log'):
        for line in (root/filename).read_text(encoding='utf8').splitlines():
            try:
                value = json.loads(line)
                if 'event' in value:
                    events.append(value)
            except (ValueError,TypeError):
                continue
    micro = [r for r in events if r['event']=='micro_start']
    expected = [r['id'] for r in read_rows(data/'train.primary.sft.jsonl')]
    random.Random(20261016).shuffle(expected)
    assert [r['id'] for r in micro] == expected and len(set(expected)) == 12141
    assert all(r['sample']==i+1 for i,r in enumerate(micro))
    assert sum(r['event']=='evaluation_start' for r in events)==128
    assert sum(r['event']=='load_start' for r in events)==2
    started = next(r['at'] for r in events if r['event']=='load_start')
    ended = [r['at'] for r in events if r['event']=='worker_exit'][-1]
    elapsed = (datetime.fromisoformat(ended)-datetime.fromisoformat(started)).total_seconds()
    assert elapsed < 36000
    result['execution']={'samples':12141,'updates':1518,'unique_training_ids':len(set(expected)),
        'tokens':train[-1]['seen_tokens'],'generation_calls':128,'started_at':started,'ended_at':ended,
        'wall_seconds':elapsed,'epoch_complete':True,'all_loss_gradient_finite':True}
    weights = root/'adapter/adapter_model.safetensors'
    with weights.open('rb') as stream:
        header_length = struct.unpack('<Q',stream.read(8))[0]
        header = json.loads(stream.read(header_length))
    tensors = {k:v for k,v in header.items() if k!='__metadata__'}
    assert all('lora_' in k and 'language_model.layers.' in k for k in tensors)
    assert sum(math.prod(v['shape']) for v in tensors.values())==21639168
    assert max(v['data_offsets'][1] for v in tensors.values())+8+header_length==weights.stat().st_size
    result['adapter']={'parameters':21639168,'tensors':len(tensors),'bytes':weights.stat().st_size,
        'header_and_payload_length_valid':True,'model_reload_not_performed':True}
    with (root/'comparison.json').open('x',encoding='utf8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--data',type=Path,required=True)
    args=parser.parse_args()
    run(args.root,args.data)
