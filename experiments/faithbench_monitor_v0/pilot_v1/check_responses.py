#!/usr/bin/env python3
"""Audit supplied pilot responses without a model or action execution."""
import argparse
import json
from pathlib import Path

from pilot_protocol import parse_pilot_response
from prepare import readl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packets = {p["case_id"]: p for p in readl(args.inputs)}
    seen, results = set(), []
    for row in readl(args.responses):
        cid = row["case_id"]
        if cid not in packets or cid in seen:
            raise ValueError("duplicate or unknown case response")
        seen.add(cid)
        try:
            results.append({"case_id": cid, "parse_valid": True,
                            "checked": parse_pilot_response(row["raw"], packets[cid])})
        except (ValueError, TypeError, KeyError) as exc:
            results.append({"case_id": cid, "parse_valid": False, "error": str(exc)})
    with args.output.open("x", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False)+"\n")
    print(json.dumps({"supplied": len(results), "valid": sum(r["parse_valid"] for r in results),
                      "missing": len(set(packets)-seen), "semantic_accuracy": "not_evaluated",
                      "actor_actions_executed": False}))


if __name__ == "__main__":
    main()
