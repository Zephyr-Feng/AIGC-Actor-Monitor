"""Replay saved proposals through current guards; never load or call a model."""
import argparse
import json
from pathlib import Path

from feedback_control import apply_decisions
from feedback_interface_v3 import explicit_labels
from feedback_selection_v1 import reconcile_choices
from prepare_feedback_control_run import apply_to_action, write
from selection_unseen_pipeline import candidate_boundary_failure, preparations


def replay(source, output):
    saved = {r['id']:r for r in (json.loads(x) for x in (source/'case_results.jsonl').read_text(encoding='utf8').splitlines())}
    packets = preparations(source)
    assert set(saved)=={row['id'] for row,p in packets}
    records = []
    for row,p in packets:
        details = {d['issue']:d for d in saved[row['id']]['details']}
        decisions, guards = [], []
        for item in p['items']:
            if item['route']!='review':
                continue
            d=details.get(item['number'],{});candidate=d.get('candidate');quote=item['回答原文']
            choice,replacement,reason='未决',None,'保存轨迹没有合法的新候选，保持未决'
            failure=None
            if isinstance(candidate,str) and candidate.strip() and candidate.strip()!=quote.strip():
                failure=candidate_boundary_failure(row,item,candidate)
                if failure:
                    reason='局部位置不能拼入完整旧字段'
                else:
                    choice,replacement,reason=reconcile_choices(d.get('choices',[]),quote,candidate)
            decisions.append({'问题编号':item['number'],'决定':choice,'依据':reason,
                '证据ID':[c['id'] for c in row['cards']],'回答原文':quote,'替换文本':replacement})
            guards.append(dict(issue=item['number'],decision=choice,reason=reason,boundary_failure=failure))
        result=apply_decisions(p,{'复核':decisions} if p['status']=='ready' else None)
        if explicit_labels(result['answer'])!=explicit_labels(row['answer']):
            result=apply_decisions(p,None);result['failure']='explicit_terminal_change_outside_scope'
        action=apply_to_action(row['original_action'],row['regions'],result['edits'])
        for key in ('final_verdict','final_confidence','next_action','selected_tool','unresolved_conflicts'):
            assert action[key]==row['original_action'][key]
        assert result['semantic_verified'] is False
        records.append(dict(id=row['id'],guard_decisions=guards,result=result,candidate_action=action,
            source=str(source),new_model_calls=0,human_gold=False,replay_not_new_model_evaluation=True))
    output.mkdir(parents=True,exist_ok=False)
    with (output/'results.jsonl').open('x',encoding='utf8') as stream:
        for r in records:
            stream.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary=dict(cases=len(records),new_model_calls=0,training_updates=0,source=str(source),
        applied_edits=sum(len(r['result']['edits']) for r in records),semantic_certified=False,
        scope='saved traces under current execution guards; original outputs and scores unchanged')
    write(output/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();replay(args.source,args.output)
