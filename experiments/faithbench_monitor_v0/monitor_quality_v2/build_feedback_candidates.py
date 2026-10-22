"""CPU-only, rule-derived feedback candidates from already allocated train sources."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random
import re

DAY={'Monday':'周一','Tuesday':'周二','Wednesday':'周三','Thursday':'周四','Friday':'周五','Saturday':'周六','Sunday':'周日'}
BOOL={'OutdoorSeating':'户外座位','RestaurantsTakeOut':'外带服务','RestaurantsReservations':'预约','RestaurantsGoodForGroups':'团体用餐'}


def leaves(value,path=()):
    if isinstance(value,dict) and value:
        return [item for key,part in value.items() for item in leaves(part,path+(key,))]
    if isinstance(value,list) and value:
        return [item for index,part in enumerate(value) for item in leaves(part,path+(index,))]
    return [(path,deepcopy(value))]


def evidence_cards(source,seed):
    entries=leaves(source)
    ids=list(range(1,len(entries)+1));random.Random(seed).shuffle(ids)
    cards=[{'id':f'E{i:03d}','path':list(path),'value':value} for i,(path,value) in zip(ids,entries)]
    random.Random(seed+1).shuffle(cards)
    assert len(cards)==len({c['id'] for c in cards})
    return cards


def restore(cards):
    root=[c for c in cards if not c['path']]
    if root:
        if len(cards)!=1:raise ValueError('root value conflicts with nested cards')
        return deepcopy(root[0]['value'])
    result={}
    for card in cards:
        cursor=result
        for index,key in enumerate(card['path']):
            if isinstance(cursor,list):
                while len(cursor)<=key:cursor.append(None)
            if index==len(card['path'])-1:
                cursor[key]=deepcopy(card['value'])
            else:
                next_key=card['path'][index+1]
                if isinstance(cursor,list):
                    if cursor[key] is None:cursor[key]=[] if isinstance(next_key,int) else {}
                else:cursor.setdefault(key,[] if isinstance(next_key,int) else {})
                cursor=cursor[key]
    return result


def pair(source,group,origin,cards,family,correct,wrong,refs,reason,fix,retain,retain_id):
    prefix=f'feedback:{origin}:{family}'
    lookup={tuple(c['path']):c for c in cards}
    extra=[]
    for path,description in ((('business_stars',),'商家总体评分'),(('review_info',0,'review_stars'),'所列第1条评论的评分')):
        card=lookup.get(path)
        if card and type(card['value']) in (int,float):
            extra.append({'回答原文':f'资料中{description}为{card["value"]}星。','证据ID':[card['id']]})
    for bad,claim in ((False,correct),(True,wrong)):
        answer=claim+' '+retain+' '+''.join(item['回答原文'] for item in extra)
        preserved=[{'回答原文':retain,'证据ID':[retain_id]},*deepcopy(extra)]
        if not bad:preserved.insert(0,{'回答原文':claim,'证据ID':refs[:1]})
        target={'结论':'revise' if bad else 'pass',
            '问题':[{'状态':'明确错误','回答原文':claim,'证据ID':refs,'理由':reason,'建议':fix}] if bad else [],
            '保留':preserved,'说明':'只修正有依据的具体错误，保留其余有据主张。' if bad else '两项主张均与所引资料相符。'}
        row={'id':prefix+(':wrong' if bad else ':supported'),'pair_id':prefix,'group':group,'family':family,
            'input':{'证据卡':cards,'待核回答':answer},'target':target,
            'provenance':{'source_dataset':'RAGTruth','existing_split':'train','existing_example_id':origin,
                'source_preserved':True,'source_form':'lossless_leaf_cards','annotation':'program_constructed_claim_pair',
                'natural_actor_output':False,'human_reviewed':False,'independent_evaluation':False}}
        check_row(row,source)
        yield row


def check_row(row,source):
    cards=row['input']['证据卡'];known={c['id']:c for c in cards}
    assert restore(cards)==source
    target=row['target'];answer=row['input']['待核回答']
    assert target['结论'] in ('pass','revise')
    assert bool(target['问题'])==(target['结论']=='revise')
    assert target['保留']
    for item in target['问题']+target['保留']:
        assert item['回答原文'] in answer and item['证据ID']
        assert all(ref in known for ref in item['证据ID'])
    assert all(p['理由'] and p['建议'] for p in target['问题'])


def examples(source,group,origin,seed):
    cards=evidence_cards(source,seed)
    assert restore(cards)==source
    lookup={tuple(c['path']):c for c in cards}
    name=lookup.get(('name',))
    if not name or not isinstance(name['value'],str) or not name['value']:return
    retain=f'资料中的商家名称为“{name["value"]}”。'
    kwargs={'source':source,'group':group,'origin':origin,'cards':cards,'retain':retain,'retain_id':name['id']}
    hours=[]
    for day,value in (source.get('hours') or {}).items():
        if day not in DAY or not isinstance(value,str):continue
        match=re.fullmatch(r'(\d{1,2}):(\d{1,2})-(\d{1,2}):(\d{1,2})',value)
        if not match:continue
        h,m,end,minute=map(int,match.groups())
        if not (0<=h<24 and 0<=end<24 and 0<=m<60 and 0<=minute<60):continue
        if value=='0:0-0:0':continue
        hours.append((day,f'{end:02d}:{minute:02d}',lookup[('hours',day)]))
    if hours:
        day,close,card=hours[seed%len(hours)]
        wrong=next((v for d,v,c in hours if v!=close),f'{(int(close[:2])+1)%24:02d}:{close[3:]}')
        good=f'结构化hours记录显示，{DAY[day]}营业至{close}。'
        bad=f'结构化hours记录显示，{DAY[day]}营业至{wrong}。'
        yield from pair(**kwargs,family='time_binding',correct=good,wrong=bad,refs=[card['id']],
            reason=f'该记录的{DAY[day]}关门值为{close}，不能把其他值{wrong}用于这一天。',fix=f'将{DAY[day]}关门时间改为{close}，保留商家名称及其他有据内容。')
        if len(hours)>1:
            other=next(c for d,v,c in hours if d!=day)
            correct=f'结构化hours记录显示，{DAY[day]}营业至{close}【{card["id"]}】。'
            wrong=f'结构化hours记录显示，{DAY[day]}营业至{close}【{other["id"]}】。'
            yield from pair(**kwargs,family='citation_binding',correct=correct,wrong=wrong,refs=[card['id'],other['id']],
                reason=f'时间值不需要改变，但所引{other["id"]}对应另一天，不能证明{DAY[day]}这一主张；{card["id"]}才对应{DAY[day]}。',fix=f'仅把引用{other["id"]}替换为{card["id"]}，保留时间{close}和其余正确内容。')
    attributes=source.get('attributes') or {}
    booleans=[(key,value) for key,value in attributes.items() if key in BOOL and type(value) is bool]
    if booleans:
        key,value=booleans[seed%len(booleans)];card=lookup[('attributes',key)]
        text='支持' if value else '不支持';opposite='不支持' if value else '支持'
        good=f'结构化{key}字段显示{text}{BOOL[key]}。'
        bad=f'结构化{key}字段显示{opposite}{BOOL[key]}。'
        yield from pair(**kwargs,family='boolean_relation',correct=good,wrong=bad,refs=[card['id']],
            reason=f'该字段明确为{str(value).lower()}，被说成了相反取值。这里只核对结构化字段，不抹去评论中的其他经验。',fix=f'改为“{good}”，保留商家名称；若评论另有信息，单独保留出处。')
    nulls=[key for key in ('Music','BusinessParking','RestaurantsReservations','RestaurantsGoodForGroups','WiFi') if key in attributes and attributes[key] is None]
    if nulls:
        key=nulls[seed%len(nulls)];card=lookup[('attributes',key)]
        good=f'结构化{key}字段为null，不能仅凭此字段断定该项服务不存在。'
        bad=f'结构化{key}字段为null，因此可以仅凭该字段确定该项服务不存在。'
        yield from pair(**kwargs,family='null_to_negative',correct=good,wrong=bad,refs=[card['id']],
            reason='null是该字段缺失信息，不是否定值；其他评论仍可能提供支持，不能用null覆盖评论。',fix=f'撤回仅凭{key}=null认定服务不存在的结论，说明该字段未知，并另核评论；保留商家名称。')


def main(data,output):
    sources={};count=Counter()
    for line in (data/'built_v3/train.primary.sft.jsonl').open(encoding='utf8'):
        row=json.loads(line);assert row['id'].startswith('ragtruth:')
        source=json.loads(row['messages'][1]['content'])['材料']['原始资料']
        if not isinstance(source,dict) or 'hours' not in source:continue
        key=json.dumps(source,ensure_ascii=False,sort_keys=True)
        if key in sources:
            assert sources[key][1]==row['group']
        else:sources[key]=(source,row['group'],row['id'])
    output.mkdir(parents=True,exist_ok=False)
    seen=set();pairs=set();groups=set()
    with (output/'candidates.jsonl').open('x',encoding='utf8') as stream:
        for index,key in enumerate(sorted(sources)):
            source,group,origin=sources[key]
            for row in examples(source,group,origin,20261017+index):
                assert row['id'] not in seen;seen.add(row['id']);pairs.add(row['pair_id']);groups.add(group)
                count[row['family']+'/'+row['target']['结论']]+=1
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    summary={'candidate_rows':len(seen),'claim_pairs':len(pairs),'source_groups':len(groups),'business_sources_available':len(sources),
        'counts':dict(count),'all_sources_from_existing_train':True,'new_split_allocation':False,'new_model_calls':0,
        'human_gold':False,'training_started':False,'uncertain_examples':0,'independent_test':False,
        'limitations':['Constructed auxiliary claims; not natural trajectories or complete Monitor supervision.',
            'Repeated variants share source groups; row count is not independent source count.',
            'No uncertain class or forensic STOP/tool-contract supervision yet. Do not start full training from this component alone.',
            'Repository MIT notice retained; original third-party sources and upstream terms still apply.']}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();main(args.data,args.output)
