import json
from pathlib import Path
import tempfile
import unittest

from evaluate_fava_checkpoint import check_authorization, frozen_rows


class EvaluationTests(unittest.TestCase):
    def test_frozen_pair_rejects_reordering_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{'id': str(i), 'input_ids': [1, 2], 'prefix_length': 1} for i in range(16)]
            def save(name, values):
                (root/name).write_text(''.join(json.dumps(r)+'\n' for r in values), encoding='utf8')
            save('development_pool.tokens.jsonl', rows)
            save('before.jsonl', rows)
            self.assertEqual(len(frozen_rows(root)), 16)
            for changed in (list(reversed(rows)), rows[:-1]):
                save('before.jsonl', changed)
                with self.assertRaises(AssertionError):
                    frozen_rows(root)

    def test_expired_unapproved_or_training_budget_is_rejected(self):
        auth = {'approved': True, 'purpose': 'checkpoint373_existing16_only',
                'training_updates': 0, 'training_epochs': 0, 'max_gpu_seconds': 1200,
                'start_epoch': 100, 'deadline_epoch': 1300}
        check_authorization(auth, 101)
        for change in ({'approved': False}, {'training_updates': 1},
                       {'max_gpu_seconds': 1201}, {'purpose': 'other'}):
            with self.assertRaises(AssertionError):
                check_authorization({**auth, **change}, 101)
        for now in (99, 1300):
            with self.assertRaises(AssertionError):
                check_authorization(auth, now)


if __name__ == '__main__':
    unittest.main()
