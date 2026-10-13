"""Deterministic prompt serialization; original prepared version is preserved."""
import json
from typed_source import INSTRUCTION, STATUSES, REFERENCE_FIELDS, evidence_catalog, validate_against_packet, schema, parse


def prompt(data):
    from controlled_claims import BASE
    contract = (BASE / 'region_field_contract.md').read_text(encoding='utf8')
    return INSTRUCTION + '\n字段契约：\n' + contract + '\n待审核数据：\n' + json.dumps(data, ensure_ascii=False, sort_keys=True)
