import unittest
from evaluate_fava_next import authorize


class AuthorizationTests(unittest.TestCase):
    def test_bounded_evaluation_only(self):
        auth = dict(approved=True, purpose='fava_next_development_comparison', training_updates=0,
                    training_epochs=0, max_gpu_seconds=7200, max_generations=384,
                    start_epoch=100, deadline_epoch=7300)
        authorize(auth, 101)
        for field, value in [('training_updates', 1), ('approved', False), ('max_generations', 385), ('max_gpu_seconds', 7201)]:
            with self.assertRaises(AssertionError):
                authorize({**auth, field: value}, 101)
        with self.assertRaises(AssertionError):
            authorize(auth, 7300)


if __name__ == '__main__':
    unittest.main()
