"""CPU-only checks; no project data, models, network, or child processes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('research_loop', Path(__file__).with_name('loop.py'))
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


def proposal(name='r1', candidate='format-only'):
    return {
        'id': name, 'mode': 'mock', 'candidate': candidate,
        'hypothesis': '格式改善可能仍伴随语义损害。',
        'alternative': '问题来自证据方向绑定，而非格式。',
        'change': '只改变模拟反馈策略。',
        'prediction': '修复数上升且有据内容无损害才支持候选。',
        'falsifier': '有害修改增加则否定当前候选。',
        'next_if_pass': '另行冻结独立验证。',
        'next_if_fail': '测试证据绑定，不追加相同策略。',
        'budget_units': 1,
    }


class LoopChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = {'objective': 'mock', 'default_monitor': '00373',
                      'best_validated': None, 'status': 'mock_only'}
        (self.root / 'state.json').write_text(json.dumps(self.state), encoding='utf8')

    def test_feedback_changes_next_experiment_and_never_promotes_mock(self):
        bad = loop.run_mock(self.root, proposal())
        good = loop.run_mock(self.root, proposal('r2', 'evidence-bound'))
        self.assertEqual(bad['decision'], 'reject')
        self.assertGreater(bad['metrics']['harmful_edits'], 0)
        self.assertEqual(good['decision'], 'candidate_needs_independent_validation')
        self.assertEqual(good['metrics']['harmful_edits'], 0)
        self.assertFalse(good['baseline_promoted'])
        self.assertEqual(loop.read_json(self.root / 'state.json'), self.state)
        ctx = loop.context(self.root, 1, 'mock')
        self.assertEqual(len(ctx['recent']), 1)
        self.assertEqual(ctx['best_observed']['id'], 'r2')
        self.assertIsNone(ctx['state']['best_validated'])
        self.assertEqual(loop.context(self.root, 2, 'project')['recent'], [])

    def test_denies_real_commands_protected_writes_and_bad_numbers(self):
        attacks = [dict(mode='train'), dict(mode='inference'), dict(mode='api'),
                   dict(command='python train.py'), dict(output='../frozen'),
                   dict(candidate='../../baseline'), dict(budget_units=100),
                   dict(budget_units=float('nan')), dict(budget_units=True),
                   dict(id='../frozen'), dict(id='FULL20'), dict(id='GT44'),
                   dict(promote=True)]
        for attack in attacks:
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                loop.run_mock(self.root, proposal() | attack)
        self.assertFalse((self.root / 'mock').exists())

    def test_budget_duplicate_ids_corrupt_history_fail_closed(self):
        loop.run_mock(self.root, proposal())
        with self.assertRaises(ValueError):
            loop.run_mock(self.root, proposal())
        for i in range(2, loop.MOCK_LIMIT + 1):
            loop.run_mock(self.root, proposal(f'r{i}'))
        with self.assertRaises(ValueError):
            loop.run_mock(self.root, proposal('over-budget'))
        ledger = self.root / 'experiments.jsonl'
        with ledger.open('a', encoding='utf8') as out:
            out.write('{partial')
        with self.assertRaises(ValueError):
            loop.context(self.root, 2, 'mock')

    def test_strict_metrics_pairing_and_source_isolation(self):
        rows = loop.simulate('evidence-bound')
        result = loop.metrics(rows)
        self.assertEqual(result['source_groups'], 4)
        self.assertEqual(result['repairs'], 2)
        for key, value in [('id', rows[0]['id']), ('correct_after', 'yes')]:
            broken = [dict(row) for row in rows]
            broken[1][key] = value
            with self.assertRaises(ValueError):
                loop.metrics(broken)
        broken = [dict(row) for row in rows]
        broken[0]['split'] = 'train'
        with self.assertRaises(ValueError):
            loop.metrics(broken)
        with self.assertRaises(ValueError):
            loop.metrics(rows, ['missing'])
        broken = [dict(row) for row in rows]
        broken[1]['source_group'] = broken[0]['source_group']
        broken[1]['split'] = 'independent'
        with self.assertRaises(ValueError):
            loop.metrics(broken)

    def test_analysis_record_preserves_state_and_rejects_promotion(self):
        record = dict(id='audit-1', track='project', hypothesis='输入关系可能有误。',
                      change='只读已有证据。', result='尚未检验。', validation='CPU开发审阅',
                      evidence=['AGENTS.md'], decision='continue', next='核对原始案例。')
        loop.record_analysis(self.root, record)
        self.assertEqual(loop.context(self.root)['recent'][0]['id'], 'audit-1')
        self.assertEqual(loop.read_json(self.root / 'state.json'), self.state)
        for change in [dict(decision='promote'), dict(evidence=['../outside']),
                       dict(approved=True), dict(id='audit-1')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                loop.record_analysis(self.root, record | change)

    def test_interrupted_writer_and_orphan_output_stop_without_overwrite(self):
        lock = self.root / '.writer.lock'
        lock.write_text('interrupted', encoding='utf8')
        with self.assertRaises(ValueError):
            loop.run_mock(self.root, proposal())
        self.assertEqual(lock.read_text(encoding='utf8'), 'interrupted')
        lock.unlink()
        orphan = self.root / 'mock' / 'r1'
        orphan.mkdir(parents=True)
        marker = orphan / 'partial.json'
        marker.write_text('original', encoding='utf8')
        with self.assertRaises(ValueError):
            loop.run_mock(self.root, proposal())
        self.assertEqual(marker.read_text(encoding='utf8'), 'original')

    def test_context_detects_new_research_without_replaying_history(self):
        original_repo, original_store = loop.REPO, loop.STORE
        try:
            loop.REPO = loop.STORE = self.root
            (self.root / 'docs').mkdir()
            marker = '**新研究状态** 当前结果，非历史运行指令。'
            (self.root / 'docs/PROJECT_PROGRESS.md').write_text(
                '# 进度\n**research-loop 交付**\n' + marker + '\n**旧运行中**\n', encoding='utf8')
            self.assertFalse(loop.context(self.root)['snapshot_current'])
            self.state['progress_marker'] = marker
            (self.root / 'state.json').write_text(json.dumps(self.state), encoding='utf8')
            self.assertTrue(loop.context(self.root)['snapshot_current'])
            self.assertNotIn('progress_marker', loop.context(self.root)['state'])
        finally:
            loop.REPO, loop.STORE = original_repo, original_store

    def test_symlink_output_and_existing_artifacts_are_not_followed(self):
        target = self.root / 'mock'
        external = self.root / 'protected'
        external.mkdir()
        try:
            target.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest('OS does not permit symlink creation')
        with self.assertRaises(ValueError):
            loop.run_mock(self.root, proposal())
        self.assertEqual(list(external.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
