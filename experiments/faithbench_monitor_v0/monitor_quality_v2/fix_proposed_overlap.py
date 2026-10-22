"""Before any model run, replace a duplicated synthetic parameter scenario."""
import argparse
import json
from pathlib import Path
import re

from build_contract_candidates import examples
from prepare_feedback_pack import sft


def canonical(row):
    material=json.loads(row['messages'][1]['content']);cards=material.pop('证据卡')
    paths={c['id']:json.dumps(c['path'],ensure_ascii=False) for c in cards}
    text=json.dumps(material,ensure_ascii=False,sort_keys=True)
    text=re.sub(r'E\d+',lambda m:paths.get(m[0],m[0]),text)
    content=sorted([{'path':c['path'],'value':c['value']} for c in cards],key=lambda c:json.dumps(c['path'],ensure_ascii=False))
    return json.dumps(content,ensure_ascii=False,sort_keys=True)+'\n'+text


def run(root,tools):
    train=[json.loads(x) for x in (root/'train_candidate.sft.jsonl').read_text(encoding='utf8').splitlines()]
    dev=[json.loads(x) for x in (root/'proposed_development.inputs.jsonl').read_text(encoding='utf8').splitlines()]
    refs=[json.loads(x) for x in (root/'proposed_development.references.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(dev)==len(refs)==80
    contents={canonical(row) for row in train}
    duplicates=[r['id'] for r in dev if canonical(r) in contents]
    assert all(key.startswith('dev:contract:') for key in duplicates)
    selected=None
    for index in range(129,2048):
        candidates=list(examples(tools,index))
        inputs=[{'id':'dev:'+r['id'],'group':r['group'],'messages':sft(r)['messages'][:-1]} for r in candidates]
        if all(canonical(row) not in contents for row in inputs):
            selected=index;break
    assert selected is not None
    new_inputs=dev[:64]+inputs
    new_refs=refs[:64]+[{'id':'dev:'+r['id'],'type':'new_parameters_seen_contract_templates','reference':r['target'],
        'human_gold':False,'independent_source':False} for r in candidates]
    for name,rows in (('proposed_development.inputs.jsonl',new_inputs),('proposed_development.references.jsonl',new_refs)):
        path=root/name
        path.rename(root/('pre_overlap_'+name))
        with path.open('x',encoding='utf8') as stream:
            for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    report={'method':'direct canonical content equality','original_duplicates':duplicates,'replacement_parameter_index':selected,
        'remaining_duplicates':[r['id'] for r in new_inputs if canonical(r) in contents],
        'natural_64_unchanged':new_inputs[:64]==dev[:64],'model_calls_before_fix':0,
        'total_cases_unchanged':80,'independent_template_or_source_claim':False}
    with (root/'content_overlap_repair.json').open('x',encoding='utf8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    assert not report['remaining_duplicates']
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--tools',type=Path,required=True)
    args=parser.parse_args();run(args.root,json.loads(args.tools.read_text(encoding='utf8')))
