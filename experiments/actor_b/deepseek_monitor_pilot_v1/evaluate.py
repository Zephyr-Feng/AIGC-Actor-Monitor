"""Local selected20 GT evaluation, gated on raw and semantic review locks."""
import collections
import json
import re
from prepare import ROOT, PRIVATE, load, dump, sha256, action


def paired(left,right):
    assert set(left)==set(right)
    cells={'wrong_or_failed_to_correct':0,'correct_to_wrong_or_failed':0,'both_correct':0,'both_wrong_or_failed':0}
    for cid in left:
        a,b=left[cid],right[cid]
        key=('both_correct' if a and b else 'both_wrong_or_failed' if not a and not b
             else 'wrong_or_failed_to_correct' if b else 'correct_to_wrong_or_failed')
        cells[key]+=1
    cells['delta_correct']=sum(right.values())-sum(left.values())
    cells['delta_fraction']=cells['delta_correct']/len(left)
    return cells


def main():
    assert paired({'a':False,'b':True},{'a':True,'b':False})['delta_correct']==0
    rawlock=load(PRIVATE/'raw_output_lock.json')
    semlock=load(PRIVATE/'semantic_review_lock.json')
    assert semlock['complete'] and semlock['gt_read']==False
    assert all(sha256(PRIVATE/n)==h for n,h in semlock['files'].items())
    assert sha256(PRIVATE/'raw_output_lock.json')==semlock['raw_lock_sha256']
    assert all(sha256(PRIVATE/'backup'/n)==h for n,h in rawlock['files'].items())
    mapping=load(PRIVATE/'selected_identity_map.json')
    groups=load(PRIVATE/'group_inventory.json')
    manifest=ROOT/'experiments/actor_b/actor_b0_d/data/diagnostic_manifest.jsonl'
    assert sha256(manifest)==groups['metadata_sha256']
    selected=set(mapping.values())
    metadata={}
    pattern=re.compile(r'"sample_id"\s*:\s*("(?:[^"\\]|\\.)*")')
    for line in manifest.read_text(encoding='utf-8').splitlines():
        match=pattern.search(line)
        assert match
        sid=json.loads(match.group(1))
        if sid in selected:
            item=json.loads(line)
            fields=[item[k] for k in ['gt','label','ground_truth'] if k in item]
            assert fields and len(set(fields))==1 and fields[0] in ['real','fake']
            metadata[sid]={'gt':fields[0],'group':item['source_group']}
    assert set(metadata)==selected and len(selected)==20
    package=load(PRIVATE/'inputs.json')
    rows={}
    for cid,sid in mapping.items():
        c=package['cases'][cid]
        try:
            a=action(c['original_raw'],c['used_tools'],c['remaining'])
            status='legal_stop'
        except (ValueError,TypeError,json.JSONDecodeError):
            a=None
            status='actor_failure'
        assert bool(a)==c['original_parse_valid']
        branches={'A':{'status':status,'parsed':a,'new_tool_returns':0,'requests':0}}
        for arm in ['B','C']:
            branches[arm]=load(PRIVATE/'backup/output'/(cid+'_'+arm)/'terminal.json')
        row={'gt':metadata[sid]['gt'],'group':groups['groups'][cid],'arms':{}}
        for arm,b in branches.items():
            valid=b['status']=='legal_stop'
            verdict=b['parsed']['final_verdict'] if valid else None
            row['arms'][arm]={'valid':valid,'verdict':verdict,'confidence':b['parsed']['final_confidence'] if valid else None,
               'status':b['status'],'valid_correct':valid and verdict==row['gt'],'new_tool_returns':b['new_tool_returns'],'requests':b['requests']}
        rows[cid]=row
    metrics={}
    for arm in ['A','B','C']:
        valid=sum(r['arms'][arm]['valid'] for r in rows.values())
        hits=sum(r['arms'][arm]['valid_correct'] for r in rows.values())
        metrics[arm]={'n':20,'legal_stops':valid,'valid_correct':hits,'valid_correct_fraction':hits/20,
              'failed':20-valid,'conditional_accuracy':hits/valid if valid else None,
              'status_counts':dict(collections.Counter(r['arms'][arm]['status'] for r in rows.values())),
              'confusion':{gt:{pred:sum(r['gt']==gt and r['arms'][arm]['verdict']==pred for r in rows.values()) for pred in ['real','fake',None]} for gt in ['real','fake']},
              'recall':{gt:sum(r['gt']==gt and r['arms'][arm]['valid_correct'] for r in rows.values())/sum(r['gt']==gt for r in rows.values()) for gt in set(r['gt'] for r in rows.values())}}
    comparisons={}
    for left,right in [('B','C'),('A','C'),('A','B')]:
        comparisons[right+'_vs_'+left]=paired({cid:r['arms'][left]['valid_correct'] for cid,r in rows.items()}, {cid:r['arms'][right]['valid_correct'] for cid,r in rows.items()})
    original_legal={cid:r for cid,r in rows.items() if r['arms']['A']['valid']}
    pure={}
    for left,right in [('B','C'),('A','C'),('A','B')]:
        pure[right+'_vs_'+left]={'original_legal_n':18,'paired_legal_n':sum(r['arms'][left]['valid'] and r['arms'][right]['valid'] for r in original_legal.values()),
            'wrong_to_right':sum(r['arms'][left]['valid'] and r['arms'][right]['valid'] and not r['arms'][left]['valid_correct'] and r['arms'][right]['valid_correct'] for r in original_legal.values()),
            'right_to_wrong':sum(r['arms'][left]['valid'] and r['arms'][right]['valid'] and r['arms'][left]['valid_correct'] and not r['arms'][right]['valid_correct'] for r in original_legal.values()),
            'left_or_right_failure_cases':[cid for cid,r in original_legal.items() if not r['arms'][left]['valid'] or not r['arms'][right]['valid']]}
    group_results={}
    for group in sorted(set(r['group'] for r in rows.values())):
        subset=[r for r in rows.values() if r['group']==group]
        group_results[group]={'n':len(subset),**{a:sum(r['arms'][a]['valid_correct'] for r in subset) for a in ['A','B','C']}}
    result={'n':20,'source_groups':len(group_results),'gt_counts':dict(collections.Counter(r['gt'] for r in rows.values())),
      'metrics':metrics,'paired':comparisons,'original18_pure_verdict_changes':pure,
      'original_invalid_recovery':{cid:r for cid,r in rows.items() if not r['arms']['A']['valid']},'groups':group_results,'cases':rows,
      'evaluation_source':{'file':manifest.relative_to(ROOT).as_posix(),'sha256':sha256(manifest),'selected_rows':20,'unselected_rows_not_decoded':True},
      'semantic_lock_sha256':sha256(PRIVATE/'semantic_review_lock.json'),'raw_lock_sha256':sha256(PRIVATE/'raw_output_lock.json'),
      'not_independent_holdout':True,'no_significance_test':True}
    dump(PRIVATE/'evaluation.json',result)
    print(json.dumps({k:result[k] for k in ['n','source_groups','gt_counts','metrics','paired','original18_pure_verdict_changes','groups']},ensure_ascii=False))


if __name__=='__main__':
    main()
