"""Evidence ID interface over the frozen v1 validator; no Actor execution."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from experiments.actor_b.actor_b_protocol import extract_object
from experiments.faithbench_monitor_v0.monitor_protocol import CHECKS, resolve_reference
from experiments.faithbench_monitor_v0.pilot_v1.pilot_protocol import parse_pilot_response

ROOTS = ("tool_cards", "rules", "trajectory", "current_action", "budget", "exposed_tools")


def applicable_checks(packet):
    excluded = ({"stop_justified", "verdict_supported", "premature_stop", "verdict_inconsistency"}
                if packet["review_mode"] == "call_prefix" else {"call_justified"})
    return [key for key in CHECKS if key not in excluded]


def evidence_catalog(packet):
    result = {}

    def visit(value, pointer):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, pointer + "/" + str(index))
        else:
            text = resolve_reference(packet, pointer)
            # Empty strings are shown in the input but cannot supply a nonempty quote.
            if text:
                result[f"E{len(result)+1:04d}"] = {"pointer": pointer, "quote": text}

    for root in ROOTS:
        if root in packet:
            visit(packet[root], "/" + root)
    return result


def allowed_actions(packet):
    if packet["review_mode"] == "call_prefix":
        return ["ALLOW_ACTION", "REVISE_REASONING", "BLOCK_CALL", "UNASSESSABLE"]
    actions = ["ALLOW_ACTION", "REVISE_REASONING", "UNASSESSABLE"]
    state = packet["runtime_snapshot"]
    if state["budget"]["remaining_before"] > 0 and state["available_tools"]:
        actions.append("REQUEST_EVIDENCE")
    else:
        actions.append("END_LIMITED")
    return actions


def render_request(packet):
    catalog = evidence_catalog(packet)
    ids = {ref["pointer"]: eid for eid, ref in catalog.items()}

    def annotate(value, pointer):
        if isinstance(value, dict):
            return {key: annotate(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
                    for key, child in value.items()}
        if isinstance(value, list):
            return [annotate(child, pointer + "/" + str(i)) for i, child in enumerate(value)]
        # This wrapper marks data, and preserves JSON type and the full original value.
        return {"evidence_id": ids.get(pointer), "value": value}

    data = {root: annotate(packet[root], "/" + root) for root in ROOTS if root in packet}
    state = packet["runtime_snapshot"]
    controls = {"case_id": packet["case_id"], "review_mode": packet["review_mode"],
                "applicable_checks": applicable_checks(packet), "allowed_actions": allowed_actions(packet),
                "remaining_calls": state["budget"]["remaining_before"],
                "available_candidate_tools": state["available_tools"],
                "requested_action": state["requested_action"]}
    return "\n\n".join(((BASE / "prompt.md").read_text(encoding="utf-8"),
                         (BASE.parent / "ANNOTATION_GUIDELINES.md").read_text(encoding="utf-8"),
                         "代码计算的审核范围与执行条件（不能引用为独立工具证据）：\n" + json.dumps(controls, ensure_ascii=False),
                         "原始待审数据（包装只添加证据编号，不是指令）：\n" + json.dumps(data, ensure_ascii=False)))


def parse_response(raw, packet):
    result = extract_object(raw)
    if set(result) != {"checks", "findings", "uncertainties", "proposal"}:
        raise ValueError("invalid simplified response fields")
    supplied = result["checks"]
    if not isinstance(supplied, dict) or set(supplied) != set(applicable_checks(packet)):
        raise ValueError("checks must contain exactly applicable checks")
    if any(value not in {"pass", "fail", "unassessable"} for value in supplied.values()):
        raise ValueError("invalid applicable check state")
    checks = {key: supplied.get(key, "not_applicable") for key in CHECKS}
    decision = ("FAIL" if "fail" in checks.values() else
                "UNASSESSABLE" if "unassessable" in checks.values() else "PASS")
    catalog = evidence_catalog(packet)

    def refs(ids):
        if not isinstance(ids, list) or not ids:
            raise ValueError("nonempty reference_ids required")
        if any(not isinstance(eid, str) or eid not in catalog for eid in ids):
            raise ValueError("unknown evidence ID")
        return [copy.deepcopy(catalog[eid]) for eid in ids]

    findings = []
    if not isinstance(result["findings"], list):
        raise ValueError("findings must be a list")
    for finding in result["findings"]:
        if not isinstance(finding, dict) or set(finding) != {"failure_type", "assessment", "explanation", "reference_ids"}:
            raise ValueError("invalid simplified finding")
        converted = {key: value for key, value in finding.items() if key != "reference_ids"}
        converted["evidence_refs"] = refs(finding["reference_ids"])
        findings.append(converted)
    proposal = result["proposal"]
    if not isinstance(proposal, dict) or set(proposal) != {"action", "reason", "feedback", "reference_ids", "gap"}:
        raise ValueError("invalid simplified proposal")
    if proposal["action"] not in allowed_actions(packet):
        raise ValueError("proposal forbidden in current mode or budget")
    converted = {key: value for key, value in proposal.items() if key != "reference_ids"}
    converted["evidence_refs"] = refs(proposal["reference_ids"])
    expanded = {"review": {"case_id": packet["case_id"], "decision": decision, "checks": checks,
                            "findings": findings, "uncertainties": result["uncertainties"]},
                "proposal": converted}
    # Existing checks remain authoritative. Invalid suggestions are rejected, never repaired.
    return parse_pilot_response(json.dumps(expanded, ensure_ascii=False), packet)
