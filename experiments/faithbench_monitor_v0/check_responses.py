#!/usr/bin/env python3
"""Check supplied responses against visible inputs; does not call a model."""
import argparse
import json
from pathlib import Path

from monitor_protocol import parse_review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True,
                        help='JSONL rows: {"case_id": ..., "raw": model response string}')
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists")
    inputs = {r["case_id"]: r for r in map(json.loads, args.inputs.read_text(encoding="utf-8").splitlines())}
    results, seen = [], set()
    for row in map(json.loads, args.responses.read_text(encoding="utf-8").splitlines()):
        cid = row["case_id"]
        if cid in seen or cid not in inputs:
            raise ValueError("duplicate or unknown response case")
        seen.add(cid)
        try:
            review = parse_review(row["raw"], inputs[cid])
            results.append({"case_id": cid, "parse_valid": True, "review": review})
        except (ValueError, TypeError) as exc:
            results.append({"case_id": cid, "parse_valid": False, "error": str(exc)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    print(json.dumps({"supplied": len(results), "valid": sum(r["parse_valid"] for r in results),
                      "semantic_accuracy": "not_evaluated"}))


if __name__ == "__main__":
    main()
