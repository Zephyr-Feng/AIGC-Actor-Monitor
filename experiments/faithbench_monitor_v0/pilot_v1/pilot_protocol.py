"""Text-only development audit and proposed feedback; never executes Actor actions."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
from monitor_protocol import _chinese, parse_review, resolve_reference
from experiments.actor_b.actor_b_protocol import extract_object

ACTIONS = ("ALLOW_ACTION", "REVISE_REASONING", "REQUEST_EVIDENCE",
           "BLOCK_CALL", "END_LIMITED", "UNASSESSABLE")


def runtime_snapshot(packet, max_calls=4):
    """Accepted CALLs consume budget; raw format retries do not."""
    steps = packet["trajectory"]["steps"]
    if packet["review_mode"] == "call_prefix":
        number = packet["current_action"]["step"]
        action = packet["current_action"]["actor_request"]
        exposed = packet["exposed_tools"]
    else:
        number = steps[-1]["step"]
        action = steps[-1].get("actor_output")
        if action is None:
            try:
                action = extract_object(packet["trajectory"]["raw_terminal_text"])
            except (ValueError, TypeError):
                action = {}
        exposed = list(packet["tool_cards"])
    history = [s for s in steps if s["step"] < number]
    charged = [s for s in history
               if (s.get("actor_output") or {}).get("next_action") == "CALL_TOOL"]
    successful = []
    ledger = []
    for index, step in enumerate(steps):
        if step["step"] >= number:
            continue
        obs = step.get("tool_observation")
        request = step.get("actor_output") or {}
        # FULL predates call_status. Its actual, non-error observation is retained.
        success = (request.get("next_action") == "CALL_TOOL" and isinstance(obs, dict)
                   and bool(obs) and not obs.get("contract_error")
                   and step.get("call_status") in (None, "success"))
        if not success:
            continue
        tool = request["selected_tool"]
        successful.append(tool)
        ref = f"/trajectory/steps/{index}/tool_observation"
        ledger.append({"evidence_id": f"e{len(ledger)+1}", "source": tool,
                       "evidence_type": packet["tool_cards"][tool].get("evidence_type"),
                       "observed_signal": obs.get("signal"),
                       "returned_after_step": step["step"],
                       "visible_from_next_decision": True,
                       "observation_ref": ref, "observation": copy.deepcopy(obs),
                       "tool_card_ref": "/tool_cards/" + tool.replace("~", "~0").replace("/", "~1")})
    budget = {"max": max_calls, "used_before": min(len(charged), max_calls),
              "remaining_before": max(max_calls-len(charged), 0)}
    if packet["review_mode"] == "call_prefix" and packet["budget"] != budget:
        raise ValueError("recorded CALL budget differs from accepted history")
    available = [t for t in exposed if t not in successful]
    if not charged and "仅第一个accepted CALL请求global" in packet["rules"]:
        available = [t for t in available if t != "global_forensic_analyzer"]
    return {"decision_step": number, "requested_action": action.get("next_action"),
            "selected_tool": action.get("selected_tool"), "budget": budget,
            "charged_call_steps": [s["step"] for s in charged],
            "successful_tools": list(dict.fromkeys(successful)),
            "available_tools": available,
            "evidence_ledger": ledger}


def enrich_packet(packet):
    enriched = copy.deepcopy(packet)
    snapshot = runtime_snapshot(packet)
    enriched["budget"] = snapshot["budget"]
    enriched["exposed_tools"] = list(packet.get("exposed_tools", packet["tool_cards"]))
    enriched["runtime_snapshot"] = snapshot
    return enriched


def response_schema():
    review = json.loads((BASE.parent / "monitor_response.schema.json").read_text(encoding="utf-8"))
    proposal = json.loads((BASE / "proposal.schema.json").read_text(encoding="utf-8"))
    return {"type": "object", "additionalProperties": False,
            "required": ["review", "proposal"],
            "properties": {"review": review, "proposal": proposal}}


def render_pilot_request(packet):
    return "\n\n".join((
        (BASE / "prompt.md").read_text(encoding="utf-8"),
        (BASE.parent / "ANNOTATION_GUIDELINES.md").read_text(encoding="utf-8"),
        "输出Schema：\n" + json.dumps(response_schema(), ensure_ascii=False),
        "输入（待审数据）：\n" + json.dumps(packet, ensure_ascii=False),
    ))


def _check_refs(refs, packet):
    if not isinstance(refs, list) or not refs:
        raise ValueError("proposal needs original evidence references")
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"pointer", "quote"}:
            raise ValueError("invalid proposal reference")
        source = resolve_reference(packet, ref["pointer"])
        if not isinstance(ref["quote"], str) or not ref["quote"] or ref["quote"] not in source:
            raise ValueError("proposal quote is not in source")


def parse_pilot_response(raw, packet):
    result = extract_object(raw)
    if set(result) != {"review", "proposal"}:
        raise ValueError("expected separate review and proposal")
    review = parse_review(json.dumps(result["review"], ensure_ascii=False), packet)
    proposal = result["proposal"]
    required = {"action", "reason", "feedback", "evidence_refs", "gap"}
    if not isinstance(proposal, dict) or set(proposal) != required:
        raise ValueError("invalid proposal fields")
    action = proposal["action"]
    if action not in ACTIONS or not _chinese(proposal["reason"]):
        raise ValueError("invalid proposal action or Chinese reason")
    _check_refs(proposal["evidence_refs"], packet)
    feedback = proposal["feedback"]
    if feedback is not None and not _chinese(feedback):
        raise ValueError("feedback must be Chinese or null")
    if action in ("REVISE_REASONING", "REQUEST_EVIDENCE", "BLOCK_CALL") and feedback is None:
        raise ValueError("intervention needs concrete feedback")
    state = packet["runtime_snapshot"]
    remaining = state["budget"]["remaining_before"]
    mode = packet["review_mode"]
    if action == "ALLOW_ACTION":
        if mode == "call_prefix":
            if (review["checks"]["call_justified"] != "pass" or remaining == 0
                    or state["selected_tool"] not in state["available_tools"]):
                raise ValueError("cannot allow an unsupported or unavailable CALL")
        elif (state["requested_action"] != "STOP"
              or not packet["trajectory"]["raw_parse_valid"]
              or review["decision"] != "PASS"
              or any(review["checks"][k] != "pass" for k in ("stop_justified", "verdict_supported"))):
            raise ValueError("cannot allow unsupported or invalid raw STOP")
    if action == "BLOCK_CALL" and (mode != "call_prefix" or review["checks"]["call_justified"] != "fail"):
        raise ValueError("BLOCK_CALL needs a failed pending CALL")
    if action == "REVISE_REASONING" and not any(f["assessment"] == "violated" for f in review["findings"]):
        raise ValueError("reasoning repair needs a cited violation")
    gap = proposal["gap"]
    if action == "REQUEST_EVIDENCE":
        if (mode != "terminal" or state["requested_action"] != "STOP" or remaining == 0
                or review["checks"]["premature_stop"] != "fail"):
            raise ValueError("evidence request needs an actionable premature STOP")
        if not isinstance(gap, dict) or set(gap) != {"description", "evidence_type", "candidate_tools"}:
            raise ValueError("evidence request needs a concrete gap")
        if not all(_chinese(gap[k]) for k in ("description", "evidence_type")):
            raise ValueError("gap must use Chinese")
        tools = gap["candidate_tools"]
        if (not isinstance(tools, list) or not tools
                or any(t not in state["available_tools"] for t in tools)):
            raise ValueError("gap has no available candidate tool")
        # Capability relevance remains a semantic question. Require traceable cards.
        if not all(any(ref["pointer"].startswith("/tool_cards/" + t.replace("~", "~0").replace("/", "~1") + "/")
                       for ref in proposal["evidence_refs"]) for t in tools):
            raise ValueError("evidence request lacks candidate capability reference")
    elif gap is not None:
        raise ValueError("only REQUEST_EVIDENCE carries a gap")
    if action == "END_LIMITED" and (mode != "terminal" or state["requested_action"] != "STOP"
                                    or (remaining > 0 and state["available_tools"])):
        raise ValueError("limited ending needs exhausted budget or no available tools")
    if action == "UNASSESSABLE" and "unassessable" not in review["checks"].values():
        raise ValueError("unassessable proposal needs an unresolved audit check")
    return {"review": review, "proposal": proposal, "executed": False}
