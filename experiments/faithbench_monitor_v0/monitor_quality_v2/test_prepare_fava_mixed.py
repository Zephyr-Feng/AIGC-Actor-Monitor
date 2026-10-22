import unittest
from prepare_fava_mixed import quality_flag, negative


class MixedTests(unittest.TestCase):
    def test_observed_fragments(self):
        for text in ('In organic chemistry, . This is useful.', 'Correct. . More.', 'It was the the site.', 'It is true, but .'):
            self.assertIsNotNone(quality_flag(text))
        self.assertIsNone(quality_flag('U.S. history has had many changes.'))

    def test_explicit_good_label_and_source_required(self):
        row = dict(dataset='ragtruth', split='train', original_split='train', id='ragtruth:1', group='g1',
                   input={'原始资料': 'The sky appears blue.', '待核回答': 'The sky appears blue.'},
                   target={'判定': '未标注来源忠实性问题', '问题片段': []})
        raw = dict(id='1', source_id='s1', quality='good', labels=[], split='train', response='The sky appears blue.')
        self.assertEqual(negative(row, raw)['target'], {'问题': []})
        for bad in ({**raw, 'quality': 'bad'}, {**raw, 'labels': None}, {**raw, 'split': 'test'}, {**raw, 'response': 'Wrong'}):
            with self.assertRaises(AssertionError):
                negative(row, bad)


if __name__ == '__main__':
    unittest.main()
