from copy import deepcopy
import unittest

from feedback_control import apply_decisions
from feedback_interface_v2 import messages, normalize, prepared


class ExplicitOperationTests(unittest.TestCase):
    def row(self):
        return dict(answer='检查3个区域', cards=[dict(id='E1', value='检查13个区域')], regions=None, prefix=None,
                    feedback={'结论': 'revise', '问题': [{'状态': '明确错误', '回答原文': '检查3个区域',
                    '证据ID': ['E1'], '理由': '来源明确13个', '建议': '改为13个'}], '保留': [], '说明': '计数冲突'})

    def response(self, operation='替换原句', replacement='检查13个区域'):
        return {'复核': [{'问题编号': 1, '操作': operation, '依据': '原始E1写13个',
                '证据摘录': [{'证据ID': 'E1', '原文': '检查13个区域'}],
                '回答原文': '检查3个区域', '替换文本': replacement}]}

    def test_explicit_operations_map_to_actual_changes(self):
        row = self.row()
        for operation, replacement, expected in [('替换原句', '检查13个区域', '检查13个区域'),
                                                ('保留原句', None, '检查3个区域'), ('暂不处理', None, '检查3个区域')]:
            result = apply_decisions(prepared(row), normalize(self.response(operation, replacement), row))
            self.assertEqual(result['answer'], expected)
            self.assertEqual(result['status'] == 'unresolved', operation == '暂不处理')

    def test_invented_source_quote_or_id_rejected(self):
        for key, value in [('证据ID', 'E003'), ('原文', '检查14个区域')]:
            response = self.response(); response['复核'][0]['证据摘录'][0][key] = value
            with self.assertRaises(ValueError):
                normalize(response, self.row())

    def test_keep_with_replacement_rolls_back(self):
        row = self.row()
        result = apply_decisions(prepared(row), normalize(self.response('保留原句', '检查13个区域'), row))
        self.assertEqual(result['status'], 'rolled_back')

    def test_location_arm_removes_monitor_opinion_only(self):
        row = self.row(); snapshot = deepcopy(row)
        full, location = messages(row, 'F'), messages(row, 'L')
        self.assertEqual(full[0], location[0])
        self.assertIn('来源明确13个', full[-1]['content'])
        self.assertNotIn('来源明确13个', location[-1]['content'])
        self.assertIn('检查13个区域', location[-1]['content'])
        self.assertIn('检查3个区域', location[-1]['content'])
        self.assertEqual(row, snapshot)


if __name__ == '__main__':
    unittest.main()
