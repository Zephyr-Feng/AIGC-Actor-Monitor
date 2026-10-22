"""Only the two Monitor content fields may change in the cached paired input."""
import json
import unittest

from proposal_content_ablation import without_feedback


class ContentAblation(unittest.TestCase):
    def test_only_feedback_removed(self):
        data = {'原始证据':[{'id':'E001','value':3}], '当前原文':'保留原句', '待核回答':'完整原稿',
                'Monitor质疑':'质疑', 'Monitor建议':'建议'}
        messages = [{'role':'system','content':'固定系统'}, {'role':'user','content':[
            {'type':'image','image':'assets/a.png'}, {'type':'text','text':json.dumps(data,ensure_ascii=False)}]}]
        changed = without_feedback(messages)
        self.assertEqual(changed[0], messages[0])
        self.assertEqual(changed[1]['content'][0], messages[1]['content'][0])
        self.assertEqual(json.loads(changed[1]['content'][1]['text']),
                         {k:v for k,v in data.items() if k not in ('Monitor质疑','Monitor建议')})
        self.assertEqual(json.loads(messages[1]['content'][1]['text']), data)


if __name__ == '__main__':
    unittest.main()
