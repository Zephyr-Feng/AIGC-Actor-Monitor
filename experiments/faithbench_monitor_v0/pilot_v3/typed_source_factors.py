"""Two separately identifiable prompt changes; no inference at import."""
from typed_source_portable import prompt as original_prompt
from typed_source_scoped import prompt as scoped_prompt

STATE_CONTRACT = '''已确认的状态边界：实际可见返回中关键结构字段缺失，导致无法核实声明中的成员或数量时，status为unassessable。列表缺失时，不能把其他计数当列表项数；没有实际列表不能直接认定项数声明矛盾。实际可见返回包含区域的编号/坐标/数值等字段，却未提供声明中的物体语义时，status为not_returned_by_source。未知与具体语义未返回分别处理，不因某个字段缺失就一概认定所有声明未知。'''


def prompt(data, restore_scope, clarify_state):
    text = scoped_prompt(data) if restore_scope else original_prompt(data)
    if clarify_state and data['audit_target'] == 'tool_return':
        marker = '\n待审核数据：\n'
        text = text.replace(marker, '\n' + STATE_CONTRACT + marker, 1)
    return text
