"""Source rendering ablation; unchanged G prompt, schema and parser."""
import copy,json
from compact import focused_input,verifier_prompt,compact_schema,compile_relations
from protocol import evidence_catalog


def grouped_input(packet):
 data=focused_input(packet);pool=data['source_pool'];ledger=packet['runtime_snapshot']['evidence_ledger']
 contexts=[];covered=set()
 for entry in ledger:
  prefix=entry['observation_ref'];fields={eid:{'field':r['pointer'][len(prefix):],'quote':r['quote']} for eid,r in pool.items() if r['pointer'].startswith(prefix+'/')}
  if not fields:continue
  # Only groups already required by G; per-atom prior_return references are unchanged.
  contexts.append({'source':entry['source'],'returned_after_step':entry['returned_after_step'],
                   'observation_pointer':prefix,'original_return':copy.deepcopy(entry['observation']),
                   'field_references':{r['field']:eid for eid,r in fields.items()}})
  covered.update(fields)
 rest={eid:r for eid,r in pool.items() if eid not in covered}
 data['source_pool']={'actor_and_capability_fields':rest,'grouped_tool_returns':contexts}
 return data


def grouped_prompt(packet):
 # Reuse the exact original instruction prefix; change only input representation.
 old=verifier_prompt(focused_input(packet));prefix=old.split('\n输入：\n',1)[0]
 return prefix+'\n输入：\n'+json.dumps(grouped_input(packet),ensure_ascii=False)
