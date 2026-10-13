"""Reuse only the locked eight v1 packets. Never read annotations."""
import argparse
import hashlib
import json
from pathlib import Path
from protocol import BASE, ROOT, evidence_catalog, render_request


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_hashes():
    paths = [BASE / n for n in ("protocol.py", "prompt.md", "prepare.py", "run.py")]
    paths += [BASE.parent / n for n in ("monitor_protocol.py", "ANNOTATION_GUIDELINES.md")]
    paths += [BASE.parent / "pilot_v1/pilot_protocol.py", ROOT / "experiments/actor_b/actor_b_protocol.py"]
    return {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in paths}


def validate(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["protocol_hashes"] != protocol_hashes():
        raise ValueError("v2 protocol changed")
    for name, expected in manifest["artifact_hashes"].items():
        if sha(directory / name) != expected:
            raise ValueError("v2 input changed: " + name)
    packets = [json.loads(line) for line in (directory / "inputs.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(packets) != 8 or [p["case_id"] for p in packets] != manifest["case_ids"]:
        raise ValueError("approved case order changed")
    return manifest, packets


def prepare(source, output):
    if sha(source / "manifest.json") != "b7a0979e90622a01562cd90485f838c83aac8b60e8392c081c145fb49cd61e46":
        raise ValueError("not the frozen v1 manifest")
    if sha(source / "inputs.jsonl") != "a93ed4d266c9848e991c940463c0280b170086c14c8042f56809b613d343bbba":
        raise ValueError("not the frozen eight v1 inputs")
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    packets = [json.loads(line) for line in (source / "inputs.jsonl").read_text(encoding="utf-8").splitlines()]
    if [p["case_id"] for p in packets] != source_manifest["case_ids"]:
        raise ValueError("original case order differs")
    output.mkdir(parents=True, exist_ok=False)
    # Byte-identical packets; only the rendering and response interface change.
    (output / "inputs.jsonl").write_bytes((source / "inputs.jsonl").read_bytes())
    for packet in packets:
        cid = packet["case_id"]
        (output / f"{cid}_request.txt").write_bytes(render_request(packet).encode("utf-8"))
        (output / f"{cid}_evidence.json").write_bytes(json.dumps(evidence_catalog(packet), ensure_ascii=False, indent=2).encode("utf-8"))
    manifest = {"version": "pilot_v2", "purpose": "development_diagnostic_only", "case_ids": source_manifest["case_ids"],
                "source_manifest_sha256": sha(source / "manifest.json"), "source_inputs_sha256": sha(source / "inputs.jsonl"),
                "model_8b": source_manifest["model"], "generation": source_manifest["generation"],
                "protocol_hashes": protocol_hashes(),
                "artifact_hashes": {p.name: sha(p) for p in sorted(output.iterdir())},
                "annotations_read": False, "actor_actions_executed": False, "images_supplied": 0}
    (output / "manifest.json").write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"cases": len(packets), "prepared": True, "model_loaded": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=BASE.parent / "private/pilot_v1")
    parser.add_argument("--output", type=Path, default=BASE.parent / "private/pilot_v2")
    args = parser.parse_args()
    prepare(args.source, args.output)
