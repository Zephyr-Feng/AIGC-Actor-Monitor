"""Minimum Chinese-reason contract, separate from frozen historical parsing.

Passing this check does not establish explanatory quality or evidence support.
All existing parsers, outputs and metrics retain their original definitions.
"""
import re
from single_source import parse

def parse_with_reason_contract(raw,data):
    result=parse(raw,data)
    if not re.search(r'[\u4e00-\u9fff]',result['reason']):
        raise ValueError('reason has no Chinese explanation text')
    return result
