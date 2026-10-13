"""Separate experimental constraints and time-bound source alignment; no labels."""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from experiments.faithbench_monitor_v0.pilot_v2.protocol import applicable_checks, allowed_actions, evidence_catalog
from experiments.faithbench_monitor_v0.monitor_protocol import FAILURE_TYPES
from experiments.actor_b.actor_b_protocol import extract_object


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def response_schema(packet):
    """Code guarantees are reported separately from semantic judgments."""
    checks = {key: {"type": "string", "enum": ["pass", "fail", "unassessable"]}
              for key in applicable_checks(packet)}
    remaining = packet["runtime_snapshot"]["budget"]["remaining_before"]
    if packet["review_mode"] == "terminal" and remaining == 0:
        checks["premature_stop"]["enum"] = ["pass"]
    actions = allowed_actions(packet)
    if ((packet["review_mode"] == "terminal" and not packet["trajectory"]["raw_parse_valid"])
            or (packet["review_mode"] == "call_prefix" and remaining == 0)):
        actions = [a for a in actions if a != "ALLOW_ACTION"]
    refs = {"type": "array", "minItems": 1,
            "items": {"type": "string", "enum": list(evidence_catalog(packet))}}
    text = {"type": "string", "minLength": 1}
    available = packet["runtime_snapshot"]["available_tools"]
    gap = obj({"description": text, "evidence_type": text,
               "candidate_tools": {"type": "array", "minItems": 1,
                                   "items": {"type": "string", "enum": available}}})
    return obj({
        "checks": obj(checks),
        "findings": {"type": "array", "items": obj({
            "failure_type": {"type": "string", "enum": [k for k in FAILURE_TYPES if k in checks]},
            "assessment": {"type": "string", "enum": ["violated", "unassessable"]},
            "explanation": text, "reference_ids": refs})},
        "uncertainties": {"type": "array", "items": text},
        "proposal": obj({"action": {"type": "string", "enum": actions}, "reason": text,
                         "feedback": {"anyOf": [text, {"type": "null"}]}, "reference_ids": refs,
                         "gap": ({"anyOf": [gap, {"type": "null"}]} if "REQUEST_EVIDENCE" in actions
                                 else {"type": "null"})}),
    })


def source_alignment(packet):
    """Index visible prior returns, never the pending CALL or future outcomes."""
    catalog = evidence_catalog(packet)
    def under(pointer):
        return [eid for eid, ref in catalog.items()
                if ref["pointer"] == pointer or ref["pointer"].startswith(pointer + "/")]
    def esc(value):
        return str(value).replace("~", "~0").replace("/", "~1")
    decisions = []
    for i, step in enumerate(packet["trajectory"]["steps"]):
        if step.get("actor_output"):
            decisions.append((step["step"], step["actor_output"], f"/trajectory/steps/{i}/actor_output", False))
    if packet["review_mode"] == "call_prefix":
        decisions.append((packet["current_action"]["step"], packet["current_action"]["actor_request"],
                          "/current_action/actor_request", False))
    elif not packet["trajectory"]["raw_parse_valid"]:
        try:
            raw = extract_object(packet["trajectory"]["raw_terminal_text"])
            decisions.append((packet["runtime_snapshot"]["decision_step"], raw,
                              "/trajectory/raw_terminal_text", True))
        except (ValueError, TypeError):
            pass
    result = []
    for number, decision, prefix, is_raw in decisions:
        for j, claim in enumerate(decision.get("current_evidence", [])):
            source = claim.get("source")
            prior = [row for row in packet["runtime_snapshot"]["evidence_ledger"]
                     if row["source"] == source and row["returned_after_step"] < number]
            result.append({"decision_step": number, "source": source,
                           "claim_ids": under(prefix if is_raw else prefix + f"/current_evidence/{j}"),
                           "raw_retry_not_accepted": is_raw,
                           "prior_returns": [{"returned_after_step": row["returned_after_step"],
                                              "observation_ids": under(row["observation_ref"]),
                                              "capability_ids": under(row["tool_card_ref"])} for row in prior],
                           "source_card_ids": under("/tool_cards/" + esc(source)) if source in packet["tool_cards"] else [],
                           "pixels_supplied_to_monitor": False})
    return result


def render_request(packet, original, condition):
    if condition == "schema_control":
        return original
    if condition != "role_alignment":
        raise ValueError("unknown condition")
    guide = (BASE / "role_alignment.md").read_text(encoding="utf8")
    return original + "\n\n" + guide + "\n按时间构造的来源定位索引（只定位，不是审核结论）：\n" + json.dumps(source_alignment(packet), ensure_ascii=False)
