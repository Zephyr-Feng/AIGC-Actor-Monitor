import importlib.util
import json
import unittest
from pathlib import Path


module_path = Path(__file__).resolve().parents[1] / 'experiments/faithbench_monitor_v0/retraining_v1/prepare_a0.py'
spec = importlib.util.spec_from_file_location('retraining_a0', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runner_spec = importlib.util.spec_from_file_location('retraining_a1', module_path.with_name('run_a1.py'))
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)
minimal_spec = importlib.util.spec_from_file_location('retraining_minimal', module_path.with_name('prepare_minimal.py'))
minimal = importlib.util.module_from_spec(minimal_spec)
minimal_spec.loader.exec_module(minimal)


class ReducedPromptTests(unittest.TestCase):
    def test_reduction_preserves_missing_fields_evidence_and_claim(self):
        data = {'actor_claim_context': {'source': 'tool', 'observation': '三个值均100',
                    'interpretation': '因此为假', 'direction': 'fake'},
                'text': '三个值均100', 'prior_source_returns': [{'values': [100, 100, None]}],
                'source_capability_fields': {'E1': '分数无真假方向'}, 'claim_reference_ids': ['E2']}
        prompt = '原指令' + module.MARKER + json.dumps(data, ensure_ascii=False)
        reduced = module.reduced_prompt(prompt)
        instruction, encoded = reduced.split(module.MARKER, 1)
        actual = json.loads(encoded)
        self.assertEqual(instruction, '原指令')
        self.assertEqual(actual['actor_claim_context'], {'source': 'tool', 'observation': '三个值均100'})
        self.assertEqual(actual['prior_source_returns'], data['prior_source_returns'])
        self.assertEqual(actual['source_capability_fields'], data['source_capability_fields'])
        self.assertEqual(actual['text'], data['text'])
        self.assertEqual(json.loads(prompt.split(module.MARKER, 1)[1]), data)

    def test_source_reference_cannot_be_replaced_by_capability_reference(self):
        data = {'audit_target': 'tool_return',
                'prior_source_returns': [{'field_references': {'/score': 'E1'}}],
                'source_capability_fields': {'E2': {'quote': '规则'}}}
        prompt = '原指令' + module.MARKER + json.dumps(data)
        answer = {'audit_target': 'tool_return', 'status': 'supported_by_source',
                  'reason': '理由', 'return_reference_ids': ['E2'], 'capability_reference_ids': []}
        self.assertFalse(runner.structural_review(json.dumps(answer), prompt)['parse_valid'])
        answer['return_reference_ids'] = ['E1']
        self.assertTrue(runner.structural_review(json.dumps(answer), prompt)['parse_valid'])

    def test_duplicate_requests_are_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            request = {'id': 'same', 'model': 'base', 'view': 'test', 'user_text': 'unused'}
            (destination / 'parameters.json').write_text(json.dumps({'new_generations_limit': 30,
                'max_new_tokens': 384}), encoding='utf-8')
            (destination / 'requests.json').write_text(json.dumps([request] * 26), encoding='utf-8')
            (destination / 'anchors.json').write_text(json.dumps([request] * 4), encoding='utf-8')
            with self.assertRaises(ValueError):
                runner.validate_bundle(destination)

    def test_projection_preserves_actual_values_and_complete_negative_return(self):
        item = {'original_return': {'scope': {'n': 9}, 'observations': {'count': 9},
                'regions': [{'region_id': 'R1', 'value': 100}]},
                'field_references': {'/scope/n': 'E1', '/observations/count': 'E2',
                                     '/regions/0/region_id': 'E3'}}
        projected = minimal.project_return(item, ['/scope/n', '/observations/count'])
        self.assertEqual(projected['original_return'], {'scope': {'n': 9}, 'observations': {'count': 9}})
        region = minimal.project_return(item, ['/regions/0/region_id'])
        self.assertEqual(region['original_return'], {'regions': [{'region_id': 'R1'}]})
        self.assertEqual(minimal.project_return(item, None), item)
        self.assertIn('regions', item['original_return'])


if __name__ == '__main__':
    unittest.main()
