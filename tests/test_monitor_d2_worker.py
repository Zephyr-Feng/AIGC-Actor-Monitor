"""Exercise the actual D2 loop with local fakes, never a real model or GPU."""
import copy
import hashlib
import json
import tempfile
import types
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest.mock import patch

from experiments.faithbench_monitor_v0.monitor_mechanism_v1 import worker_d2 as worker
from experiments.faithbench_monitor_v0.monitor_mechanism_v1.prepare_d2 import messages


class Tensor:
    shape = (1, 3)

    def __init__(self, value=None):
        self.value = value

    def to(self, device):
        return self

    def numpy(self):
        return self

    def tobytes(self):
        return b'local-unit-test-tensor'

    def tolist(self):
        return self.value

    def __getitem__(self, key):
        return self


class D2WorkerTests(unittest.TestCase):
    def run_fixture(self, external_eligible=True):
        cases = ['case_005', 'case_016', 'case_017', 'case_028']
        tools = ['global_forensic_analyzer', 'local_texture_analyzer',
                 'complementary_forensic_analyzer', 'provenance_inspector']
        package = dict(cases={}, order=cases, arm_order={c:['S','G','M'] for c in cases},
            general='S-fixture', review_contract={'known':'共同规则'}, suffix='共同接口',
            request_limit=18, cache_call_limit=6, generation={'max_new_tokens':768,
            'seed':20261006,'max_format_repairs_per_step':0}, adapter=None,training_steps=0)
        delivery = {c:{a:{'content':a+'-fixture','eligible':external_eligible} for a in ('G','M')} for c in cases}
        cache = {c:{t:{'tool':t,'signal':t+'-unrequested-canary'} for t in tools} for c in cases}
        for cid in cases:
            used = tools[:2] if cid == 'case_005' else tools[:]
            package['cases'][cid] = dict(prefix=[{'role':'system','content':cid},
                {'role':'assistant','content':'original raw invalid proposal'}],used_tools=used,remaining=4-len(used))
        pristine = copy.deepcopy((package,delivery,cache))
        digest = hashlib.sha256(Tensor().tobytes()).hexdigest()
        grids = [[1,2,3]]*4
        expected = {'execution_freeze_sha256':'fixture','branches':{}}
        for cid in cases:
            for arm in ('S','G','M'):
                trail = messages(package,delivery,cid,arm)
                expected['branches'][cid+'_'+arm] = dict(messages_sha256=worker.canonical_hash(trail),
                    input_ids_sha256=digest,pixel_values_sha256=digest,image_grids=grids)
        traces, calls, raw_text = [], {}, {}

        def encode(trail):
            cid = trail[0]['content']
            feedback = trail[2]['content']
            arm = next(a for a in ('S','G','M') if a+'-fixture' in feedback)
            key = cid+'_'+arm
            traces.append((key,copy.deepcopy(trail)))
            return {'input_ids':Tensor(),'pixel_values':Tensor(),
                    'image_grid_thw':Tensor(grids),'fixture_branch':Tensor(key)}

        def generate(**kwargs):
            key = kwargs['fixture_branch'].value
            calls[key] = calls.get(key,0)+1
            step = calls[key]
            action = dict(current_evidence=[],unresolved_conflicts=[],evidence_gap='',next_action='STOP',
                selected_tool=None,action_reason='本地测试',final_verdict='real',final_confidence='low')
            if key.startswith('case_005') and step < 3:
                action.update(next_action='CALL_TOOL',selected_tool=tools[step+1],final_verdict=None,final_confidence=None)
            if key == 'case_016_M':
                action['final_verdict'] = 'inconclusive'
            token = len(raw_text)+1
            raw_text[token] = json.dumps(action,ensure_ascii=False)
            ids = [token]*768 if key == 'case_017_G' else [token,999]
            return Tensor(ids)

        model = types.SimpleNamespace(generate=generate,generation_config=types.SimpleNamespace(eos_token_id=999))
        model.eval = lambda:model
        torch = types.SimpleNamespace(__version__='2.12.1+cu130',bfloat16='fixture',set_num_threads=lambda n:None,
            manual_seed=lambda n:None,inference_mode=nullcontext,cuda=types.SimpleNamespace(is_available=lambda:True,
            manual_seed_all=lambda n:None,synchronize=lambda:None,empty_cache=lambda:None))
        transformers = types.SimpleNamespace(__version__='4.57.4',Qwen3VLForConditionalGeneration=
            types.SimpleNamespace(from_pretrained=lambda *args,**kwargs:model))
        processor = types.SimpleNamespace(decode=lambda ids,**kwargs:raw_text[ids[0]])
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            (root/'cpu_branches.json').write_text(json.dumps(expected),encoding='utf8')
            stack.enter_context(patch.object(worker,'ROOT',root))
            stack.enter_context(patch.object(worker,'execution',return_value=(package,delivery,cache)))
            stack.enter_context(patch.object(worker,'sha256',return_value='fixture'))
            stack.enter_context(patch.object(worker.original,'encoder',return_value=(processor,encode,100000)))
            stack.enter_context(patch.object(worker.original,'protection',return_value={}))
            stack.enter_context(patch.dict('sys.modules',{'torch':torch,'transformers':transformers}))
            stack.enter_context(patch('builtins.print'))
            worker.run()
            summary = json.loads((root/'worker_completed.json').read_text(encoding='utf8'))
            terminals = {p.parent.name:json.loads(p.read_text(encoding='utf8')) for p in (root/'output').glob('*/terminal.json')}
            returns = len(list((root/'output').glob('*/return_*.json')))
        self.assertEqual((package,delivery,cache),pristine)
        return summary,terminals,returns,traces,calls

    def test_generation_cap_isolation_and_failures_without_repairs(self):
        summary,terminal,returns,traces,calls = self.run_fixture()
        self.assertEqual(summary['requests'],18)
        self.assertEqual(summary['new_tool_returns'],6)
        self.assertEqual(returns,6)
        self.assertEqual(len(terminal),12)
        for arm in ('S','G','M'):
            self.assertEqual(terminal['case_005_'+arm]['requests'],3)
            self.assertEqual(terminal['case_005_'+arm]['new_tool_returns'],2)
            first = next(trail for key,trail in traces if key == 'case_005_'+arm)
            self.assertNotIn('unrequested-canary',json.dumps(first))
        for key in ('case_016_M','case_017_G'):
            self.assertEqual(terminal[key]['status'],'actor_failure')
            self.assertEqual(calls[key],1)
        self.assertEqual(summary['new_format_retries'],0)
        self.assertFalse(summary['verdict_projection'])

    def test_external_failures_stay_in_denominator_without_generation(self):
        summary,terminal,returns,_,calls = self.run_fixture(external_eligible=False)
        self.assertEqual(len(terminal),12)
        self.assertEqual(sum(v['status']=='monitor_failure' for v in terminal.values()),8)
        self.assertEqual(summary['requests'],6)
        self.assertEqual(returns,2)
        self.assertTrue(all(key.endswith('_S') for key in calls))


if __name__ == '__main__':
    unittest.main()
