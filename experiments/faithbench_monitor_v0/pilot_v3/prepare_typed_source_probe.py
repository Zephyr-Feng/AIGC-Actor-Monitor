"""Prepare requests from already-approved R14 data, never load review targets."""
import argparse,copy,json
from pathlib import Path
import controlled_claims as c
import typed_source_portable as t
from prepare_reasoned_portable import dump

SELECTION=[('terminal_0041','A010'),('terminal_0005','A006'),('terminal_0005','A007'),
 ('terminal_0001','A005'),('terminal_0001','A006'),('terminal_0001','A007'),
 ('terminal_0001','A008'),('terminal_0001','A009'),('terminal_0002','A006'),
 ('terminal_0061','A006'),('call_0385','A008'),('terminal_0041','A006')]

def prepare(source,target):
    if c.sha(source/'manifest.json')!='423dc70df2ae6ed842dae613339e08618538f227294c772c2e8dde015a895443':
        raise ValueError('wrong R14 parent')
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf8'))
    for name,h in manifest['artifact_hashes'].items():
        if c.sha(source/name)!=h:raise ValueError('input changed '+name)
    for name,h in manifest['protocol_hashes'].items():
        if c.sha(c.ROOT/name)!=h:raise ValueError('protocol changed '+name)
    original=json.loads((source/'records.json').read_text(encoding='utf8'));rows=[]
    for case,atom in SELECTION:
        data=copy.deepcopy(next(r for r in original if (r['case_id'],r['atom_id'])==(case,atom)))
        data['audit_target']='tool_capability' if (case,atom)==('terminal_0041','A010') else 'tool_return'
        rows.append({'name':case+'_'+atom,'kind':'natural_used_development','data':data})
    synthetic=copy.deepcopy(rows[-1])
    synthetic['name']+='_'+'missing_list';synthetic['kind']='synthetic_delete_list_only'
    group=synthetic['data']['prior_source_returns'][0]
    del group['original_return']['most_atypical_regions']
    group['field_references']={p:e for p,e in group['field_references'].items() if not p.startswith('/most_atypical_regions/')}
    rows.append(synthetic)
    target.mkdir(exist_ok=False,parents=True);dump(target/'records.json',rows)
    for row in rows:
        (target/(row['name']+'.txt')).write_bytes(t.prompt(row['data']).encode('utf8'))
        dump(target/(row['name']+'.schema.json'),t.schema(row['data']))
    deps=dict(manifest['protocol_hashes'])
    for name in ['typed_source.py','typed_source_portable.py','prepare_typed_source_probe.py','run_typed_source_probe.py','PLAN_TYPED_SOURCE_PROBE_20261010.md']:
        deps[(c.BASE/name).relative_to(c.ROOT).as_posix()]=c.sha(c.BASE/name)
    dump(target/'manifest.json',{'condition':'typed_source_27b_probe','parent_R14_manifest_sha256':c.sha(source/'manifest.json'),
        'protocol_hashes':deps,'artifact_hashes':{p.name:c.sha(p) for p in sorted(target.iterdir())},
        'schedule':[{'name':r['name'],'kind':r['kind']} for r in rows],
        'model':'Qwen3.5-27B Q4_K_M','backend':'b11517/8a1a9b512',
        'targets_read':False,'targets_in_requests':False,'independent_test':False,'sft':False})
    print(json.dumps({'requests':len(rows),'manifest_sha256':c.sha(target/'manifest.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--prepare',type=Path,required=True)
    args=parser.parse_args();prepare(args.source,args.prepare)
