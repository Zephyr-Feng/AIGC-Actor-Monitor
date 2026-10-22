"""Link existing human span notes to verified source fields for content review."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from build_feedback_candidates import evidence_cards

FIELD=re.compile(r'"([^"\n]+)"\s*:\s*(true|false|null|"[^"\n]*")')


def original_block(meta):
    found=re.search(r'(?im)^\s*Original\s*:',meta or '')
    if not found:return ''
    tail=meta[found.end():]
    end=re.search(r'(?im)^\s*(?:AIGC|Generative|Generated|Response)\s*:',tail)
    return tail[:end.start()] if end else tail


def links(source,meta):
    linked=[]
    for name,encoded in FIELD.findall(original_block(meta)):
        value=json.loads(encoded)
        if value is None:continue
        matches=[]
        if name in ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'):
            if (source.get('hours') or {}).get(name)==value:matches.append(['hours',name])
        attributes=source.get('attributes') or {}
        if name in ('WiFi','OutdoorSeating','RestaurantsTakeOut','RestaurantsReservations') and attributes.get(name)==value and name in attributes:
            matches.append(['attributes',name])
        parking=attributes.get('BusinessParking') or {}
        if name in ('garage','street','validated','lot','valet') and name in parking and parking[name]==value:
            matches.append(['attributes','BusinessParking',name])
        if len(matches)==1 and (matches[0],value) not in linked:
            linked.append((matches[0],value))
    return linked


def excerpt_links(cards,meta):
    block=original_block(meta).strip()
    snippets={block.strip('"'),*re.findall(r'"([^"\n]+)"',block)}
    result=[]
    for snippet in sorted(snippets):
        if len(snippet)<20:continue
        matches=[c for c in cards if isinstance(c['value'],str) and snippet in c['value']]
        if len(matches)==1 and matches[0]['value'].count(snippet)==1:
            result.append({'evidence_id':matches[0]['id'],'source_excerpt':snippet,'path':matches[0]['path']})
    return result


def main(data,output):
    built=data/'built_v3'
    train={r['id']:r for r in map(json.loads,(built/'train.primary.records.jsonl').read_text(encoding='utf8').splitlines())}
    output.mkdir(parents=True,exist_ok=False)
    counts=Counter();groups=set();seen=set()
    with (output/'review_candidates.jsonl').open('x',encoding='utf8') as stream:
        for line in (built/'provenance.jsonl').open(encoding='utf8'):
            match=re.match(r'^\{"id":\s*"([^"]+)"',line)
            if not match or match[1] not in train:continue
            provenance=json.loads(line);row=train[match[1]];source=row['input']['原始资料'];answer=row['input']['待核回答']
            if not isinstance(source,(dict,str)):continue
            cards=None
            for index,label in enumerate(provenance['annotation']['labels']):
                if label['label_type']!='Evident Conflict':continue
                if cards is None:cards=evidence_cards(source,20261017+len(seen))
                found=links(source,label.get('meta')) if isinstance(source,dict) and 'hours' in source else []
                excerpts=excerpt_links(cards,label.get('meta'))
                if not found and not excerpts:continue
                assert answer[label['start']:label['end']]==label['text']
                lookup={tuple(card['path']):card for card in cards}
                refs=list(dict.fromkeys([lookup[tuple(path)]['id'] for path,value in found]+[r['evidence_id'] for r in excerpts]))
                facts=[{'path':path,'value':value} for path,value in found]
                key=f'natural_review:{row["id"]}:{index}'
                assert key not in seen;seen.add(key);groups.add(row['group'])
                counts['by_span']+=1
                counts['task/'+('business' if isinstance(source,dict) and 'hours' in source else 'qa' if isinstance(source,dict) else 'news')]+=1
                counts['exact_excerpt_linked']+=bool(excerpts)
                for path,value in found:counts['field/'+path[-1]]+=1
                candidate={'id':key,'group':row['group'],'origin':row['id'],
                    'input':{'审核范围':'仅核对指定主张；不声称整篇其余内容正确。','证据卡':cards,'待核回答':answer,'指定主张':label['text']},
                    'human_span_annotation':label,'meta_linked_facts':facts,'exact_source_excerpts':excerpts,'evidence_ids':refs,
                    'review_status':'requires_semantic_review','approved_for_training':False,'human_feedback_gold':False,
                    'required_review':['Read the full source and response, including reviews that may conflict with structured fields.',
                        'Confirm the exact subclaim, evidence relationship, Chinese reason and safe correction.',
                        'Do not treat every word of a long author span as wrong or unmarked text as verified.']}
                stream.write(json.dumps(candidate,ensure_ascii=False)+'\n')
    summary={'natural_span_candidates':len(seen),'source_groups':len(groups),'counts':dict(counts),
        'all_from_existing_train':True,'no_null_or_ambience_labels_imported':True,'approved_for_training':0,'new_model_calls':0,
        'note':'Author spans are inherited human annotations; evidence links are field-value matches, not semantic certification or finished Chinese feedback.'}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();main(args.data,args.output)
