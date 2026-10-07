"""Actor-B structured trajectory contract.

This module validates structure only. It intentionally does not decide whether
the Actor's forensic interpretation is correct; those errors remain observable
for FaithBench and the future Monitor.
"""

from __future__ import annotations

import json
import re
from typing import Any


TOOLS = (
    "global_forensic_analyzer",
    "local_texture_analyzer",
    "complementary_forensic_analyzer",
    "provenance_inspector",
)
DIRECTIONS = ("none", "real", "fake", "inconclusive")
CONFIDENCE = ("low", "moderate", "high")


def extract_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object found")
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def _string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")


def _validate_evidence(items: Any) -> None:
    if not isinstance(items, list):
        raise ValueError("current_evidence must be a list")
    required = {"source", "observation", "interpretation", "direction"}
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError(f"current_evidence[{index}] has invalid fields")
        if item["source"] not in TOOLS and item["source"] != "visual":
            raise ValueError(f"current_evidence[{index}].source is invalid")
        if not isinstance(item["observation"], str) or not isinstance(item["interpretation"], str):
            raise ValueError(f"current_evidence[{index}] text fields must be strings")
        if item["direction"] not in DIRECTIONS:
            raise ValueError(f"current_evidence[{index}].direction is invalid")


def validate_action(value: dict[str, Any], used_tools: set[str] | None = None) -> dict[str, Any]:
    required = {
        "current_evidence", "unresolved_conflicts", "evidence_gap", "next_action",
        "selected_tool", "action_reason", "final_verdict", "final_confidence",
    }
    if set(value) != required:
        missing, extra = required - set(value), set(value) - required
        raise ValueError(f"invalid fields; missing={sorted(missing)} extra={sorted(extra)}")
    _validate_evidence(value["current_evidence"])
    _string_list(value["unresolved_conflicts"], "unresolved_conflicts")
    for field in ("evidence_gap", "action_reason"):
        if not isinstance(value[field], str):
            raise ValueError(f"{field} must be a string")
    action = value["next_action"]
    if action not in ("CALL_TOOL", "STOP"):
        raise ValueError("next_action must be CALL_TOOL or STOP")
    if action == "CALL_TOOL":
        tool = value["selected_tool"]
        if tool not in TOOLS:
            raise ValueError("selected_tool is not callable")
        if used_tools is not None and tool in used_tools:
            raise ValueError("selected_tool has already been called")
        if value["final_verdict"] is not None or value["final_confidence"] is not None:
            raise ValueError("CALL_TOOL requires null final fields")
    else:
        if value["selected_tool"] is not None:
            raise ValueError("STOP requires selected_tool=null")
        if value["final_verdict"] not in ("real", "fake"):
            raise ValueError("STOP final_verdict must be real or fake")
        # Confidence is ancillary metadata. A missing value must stay missing;
        # it must not invalidate an otherwise explicit real/fake STOP verdict.
        if value["final_confidence"] is not None and value["final_confidence"] not in CONFIDENCE:
            raise ValueError("STOP final_confidence is invalid")
    return value


def parse_action(text: str, used_tools: set[str] | None = None) -> dict[str, Any]:
    return validate_action(extract_object(text), used_tools)

