"""Resolve model-selected evidence IDs without letting it rewrite source facts."""
from copy import deepcopy
from resolve_quotes import occurrences


def assemble(answer,cards,payload):
    known={card['id']:card for card in cards}
    if len(known)!=len(cards):raise ValueError('duplicate evidence id')
    if not isinstance(payload,dict) or set(payload)!={'结论','问题','保留','说明'}:
        raise ValueError('invalid feedback contract')
    if payload['结论'] not in ('pass','revise','uncertain'):
        raise ValueError('invalid conclusion')
    if not isinstance(payload['说明'],str) or not payload['说明'].strip():
        raise ValueError('missing explanation')
    if not isinstance(payload['问题'],list) or not isinstance(payload['保留'],list):
        raise ValueError('invalid item lists')
    if payload['结论']=='pass' and (payload['问题'] or not payload['保留']):
        raise ValueError('pass requires supported content and no accusations')
    if payload['结论']=='revise' and not payload['问题']:
        raise ValueError('revise requires specific problems')
    if payload['结论']=='uncertain' and not payload['问题']:
        raise ValueError('uncertain requires a specific unresolved claim')
    result=deepcopy(payload)
    for field in ('问题','保留'):
        for item in result[field]:
            expected={'状态','回答原文','证据ID','理由','建议'} if field=='问题' else {'回答原文','证据ID'}
            if not isinstance(item,dict) or set(item)!=expected:
                raise ValueError('invalid item contract')
            positions=occurrences(answer,item['回答原文'])
            refs=item['证据ID']
            if not positions or not isinstance(refs,list) or not refs or not all(isinstance(r,str) for r in refs):
                raise ValueError('missing exact answer quote or evidence id')
            if len(set(refs))!=len(refs) or any(ref not in known for ref in refs):
                raise ValueError('unknown or repeated evidence id')
            if field=='问题' and any(not isinstance(item[k],str) or not item[k].strip() for k in ('理由','建议')):
                raise ValueError('missing reason or correction')
            if field=='问题' and item['状态'] not in ('明确错误','未决'):
                raise ValueError('invalid issue state')
            item['定位候选']=[list(p) for p in positions]
            item['定位唯一']=len(positions)==1
            item['来源']=deepcopy([known[ref] for ref in refs])
    states={p['状态'] for p in result['问题']}
    if payload['结论']=='revise' and '明确错误' not in states:
        raise ValueError('revise requires a confirmed error')
    if payload['结论']=='uncertain' and states!={'未决'}:
        raise ValueError('uncertain requires unresolved issues only')
    # IDs and quotations can be real while the claimed relationship is wrong.
    return {'feedback':result,'source_anchors_verified':True,'semantic_verified':False}
