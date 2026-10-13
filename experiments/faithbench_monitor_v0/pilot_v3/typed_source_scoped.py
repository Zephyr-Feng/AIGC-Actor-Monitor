"""Candidate single prompt change: restore R14 source-attribution scope.

No model experiment has run with this candidate; enums and parsing stay fixed.
"""
from typed_source_portable import prompt as portable_prompt
from typed_source_portable import schema, parse, evidence_catalog, validate_against_packet
from prepare_observation_scope import SCOPE


def prompt(data):
    original = portable_prompt(data)
    if data['audit_target'] == 'tool_return':
        marker = '\n待审核数据：\n'
        return original.replace(marker, '\n' + SCOPE + marker, 1)
    return original
