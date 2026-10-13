#!/usr/bin/env python3
"""Validate preparation by default; load the approved local Qwen model only with an explicit flag."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pilot_protocol import BASE, parse_pilot_response
from prepare import ROOT, protocol_hashes, readl, sha


def validate_preparation(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["modality"] != "text_only" or manifest["cases"] != 8:
        raise ValueError("not the approved text-only eight-case preparation")
    if protocol_hashes() != manifest["protocol_hashes"]:
        raise ValueError("pilot protocol changed since preparation")
    for name, expected in manifest["artifact_hashes"].items():
        if sha(directory / name) != expected:
            raise ValueError(f"prepared artifact changed: {name}")
    inputs = readl(directory / "inputs.jsonl")
    if [p["case_id"] for p in inputs] != manifest["case_ids"]:
        raise ValueError("case order changed")
    return manifest, inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=BASE.parent / "private/pilot_v1")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--run-inference", action="store_true", help="use only after the user has enabled the GPU")
    args = parser.parse_args()
    manifest, packets = validate_preparation(args.input_dir)
    if not args.run_inference:
        print(json.dumps({"preparation_valid": True, "cases": len(packets), "model_loaded": False,
                          "max_request_chars": max(len((args.input_dir / f"{p['case_id']}_request.txt").read_text(encoding="utf-8")) for p in packets)}))
        return
    if args.model_dir is None or args.output_dir is None:
        parser.error("inference needs --model-dir and a new --output-dir")
    if args.output_dir.exists():
        raise FileExistsError("result directory already exists; do not repeat or overwrite")
    revision = manifest["model"]["model_revision"]
    if revision not in args.model_dir.resolve().parts:
        raise ValueError("model path must contain the frozen revision")
    if sha(args.model_dir / "config.json") != manifest["model"]["model_config_sha256"]:
        raise ValueError("model configuration differs from frozen model")
    # Deliberately lazy: CPU preparation and dry runs never import/load a model.
    import torch
    import transformers
    if not torch.cuda.is_available():
        raise RuntimeError("approved GPU is unavailable")
    generation = manifest["generation"]
    torch.manual_seed(generation["seed"])
    torch.cuda.manual_seed_all(generation["seed"])
    print("Loading approved local Qwen snapshot", flush=True)
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir, local_files_only=True)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda", local_files_only=True).eval()
    args.output_dir.mkdir(parents=True)
    runtime = {"model": manifest["model"], "generation": generation,
               "input_manifest_sha256": sha(args.input_dir / "manifest.json"),
               "torch": str(torch.__version__), "transformers": transformers.__version__,
               "images_supplied": 0, "actor_actions_executed": False}
    (args.output_dir / "runtime.json").write_text(json.dumps(runtime, indent=2)+"\n", encoding="utf-8")
    with (args.output_dir / "responses.jsonl").open("x", encoding="utf-8") as handle:
        for index, packet in enumerate(packets, 1):
            print(f"Starting case {index}/8", flush=True)
            request = (args.input_dir / f"{packet['case_id']}_request.txt").read_text(encoding="utf-8")
            messages = [{"role": "user", "content": [{"type": "text", "text": request}]}]
            rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            encoded = processor(text=[rendered], return_tensors="pt")
            if "pixel_values" in encoded or "image_grid_thw" in encoded:
                raise ValueError("unexpected pixels in text-only pilot")
            encoded = {key: value.to("cuda") for key, value in encoded.items()}
            count = int(encoded["input_ids"].shape[1])
            torch.cuda.synchronize()
            started = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(**encoded, max_new_tokens=generation["max_new_tokens"],
                                        do_sample=False, repetition_penalty=generation["repetition_penalty"])
            torch.cuda.synchronize()
            tokens = output[0][count:]
            row = {"case_id": packet["case_id"], "raw": processor.decode(tokens, skip_special_tokens=True),
                   "input_tokens": count, "output_tokens": int(tokens.shape[0]),
                   "seconds": round(time.perf_counter()-started, 4)}
            try:
                row.update(parse_valid=True, checked=parse_pilot_response(row["raw"], packet))
            except (ValueError, TypeError, KeyError) as exc:
                row.update(parse_valid=False, parse_error=str(exc))
            handle.write(json.dumps(row, ensure_ascii=False)+"\n")
            handle.flush()
            print(json.dumps({"completed": index, "parse_valid": row["parse_valid"],
                              "seconds": row["seconds"], "output_tokens": row["output_tokens"]}), flush=True)
    print("Eight-case inference finished; model process can exit and GPU can be disabled.", flush=True)


if __name__ == "__main__":
    main()
