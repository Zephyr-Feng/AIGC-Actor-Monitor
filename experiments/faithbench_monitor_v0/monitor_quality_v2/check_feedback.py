"""Reject malformed or ungrounded feedback; exact anchors do not prove entailment."""
import json
import re


def check(source, answer, raw):
    failures=[]
    try:
        item=json.loads(raw)
        assert isinstance(item,dict) and set(item)=={'结论','问题','说明'}
        assert item['结论'] in ('pass','revise','uncertain')
        assert isinstance(item['说明'],str) and item['说明'].strip()
        assert isinstance(item['问题'],list)
        assert (item['结论']!='pass' or not item['问题'])
        assert (item['结论']!='revise' or item['问题'])
        for problem in item['问题']:
            assert isinstance(problem,dict) and set(problem)=={'回答原文','来源原文','来源位置','理由','建议'}
            assert all(isinstance(v,str) and v.strip() for v in problem.values())
    except (ValueError,AssertionError,TypeError):
        return {'contract_valid':False,'anchors_valid':False,'failures':['invalid_json_or_contract'],'semantic_verified':False}
    visible=source if isinstance(source,str) else json.dumps(source,ensure_ascii=False)
    passages=source.get('passages','') if isinstance(source,dict) else source
    for index,problem in enumerate(item['问题']):
        if problem['回答原文'] not in answer:
            failures.append({'problem':index,'reason':'answer_quote_not_exact'})
        if problem['来源原文'] not in visible:
            failures.append({'problem':index,'reason':'source_quote_not_exact'})
        ids=re.findall(r'passage\s*(\d+)',problem['来源位置'],re.I)
        for key in ids:
            match=re.search(r'passage\s+'+re.escape(key)+r'\s*:',passages,re.I)
            if not match:
                failures.append({'problem':index,'reason':'passage_id_not_present','id':key})
                continue
            next_match=re.search(r'passage\s+\d+\s*:',passages[match.end():],re.I)
            stop=match.end()+next_match.start() if next_match else len(passages)
            if problem['来源原文'] not in passages[match.start():stop]:
                failures.append({'problem':index,'reason':'quote_not_in_named_passage','id':key})
    # shortcut: free-form JSON paths need content review; adopt explicit source IDs before deployment.
    return {'contract_valid':True,'anchors_valid':not failures,'failures':failures,
            'semantic_verified':False,'source_location_checked':bool(item['问题']) and all(re.search(r'passage\s*\d+',p['来源位置'],re.I) for p in item['问题'])}
