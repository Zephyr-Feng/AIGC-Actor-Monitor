import unittest
from resolve_quotes import occurrences, resolve


class QuoteResolutionTests(unittest.TestCase):
    def prediction(self, text, start=0, end=1):
        return {'判定':'存在来源忠实性问题', '问题片段':[{'起点':start,'终点':end,
                '原文':text,'原始错误类型':'Evident Conflict'}]}

    def test_unicode_unique_and_input_preserved(self):
        prediction=self.prediction('蓝色')
        fixed=resolve('苹果是蓝色的。',prediction)
        self.assertTrue(fixed['resolved'])
        self.assertEqual((fixed['adoptable_payload']['问题片段'][0]['起点'],
                          fixed['adoptable_payload']['问题片段'][0]['终点']),(3,5))
        self.assertEqual(prediction['问题片段'][0]['起点'],0)

    def test_repeated_quote_is_not_guessed(self):
        fixed=resolve('abc abc',self.prediction('abc',1,4))
        self.assertFalse(fixed['resolved'])
        self.assertIsNone(fixed['adoptable_payload'])
        self.assertEqual(fixed['span_resolution'][0]['status'],'ambiguous_quote')

    def test_consistent_original_repeat_can_be_preserved(self):
        fixed=resolve('abc abc',self.prediction('abc',4,7))
        self.assertTrue(fixed['resolved'])
        self.assertEqual(fixed['span_resolution'][0]['status'],'original_consistent')

    def test_missing_and_empty_quote_fail(self):
        for text in ('xyz',''):
            self.assertFalse(resolve('abc',self.prediction(text))['resolved'])
        self.assertEqual(occurrences('aaa','aa'),[(0,2),(1,3)])


if __name__=='__main__':
    unittest.main()
