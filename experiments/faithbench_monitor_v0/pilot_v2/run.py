"""Single-shot text-only comparison; models run on the authorized instance."""
import argparse
import json
import time
import urllib.request
from pathlib import Path
from protocol import parse_response
from prepare import sha, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--backend", choices=("transformers_8b", "llama_27b"))
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--run-inference", action="store_true")
    args = parser.parse_args()
    manifest, packets = validate(args.input_dir)
    if not args.run_inference:
        print(json.dumps({"preparation_valid": True, "cases": len(packets), "model_loaded": False}))
        return
    if args.backend is None or args.output_dir is None or args.model_dir is None:
        parser.error("inference needs backend, model-dir and new output-dir")
    if args.output_dir.exists():
        raise FileExistsError("output already exists; no repeats or overwrites")
    generation = manifest["generation"]
    runtime = {"backend": args.backend, "input_manifest_sha256": sha(args.input_dir / "manifest.json"),
               "generation": generation, "thinking_enabled": False, "actor_actions_executed": False,
               "images_supplied": 0, "annotations_read": False, "model_path": str(args.model_dir)}
    if args.backend == "transformers_8b":
        import torch
        import transformers
        cfg = manifest["model_8b"]
        if cfg["model_revision"] not in args.model_dir.resolve().parts or sha(args.model_dir / "config.json") != cfg["model_config_sha256"]:
            raise ValueError("not frozen 8B model")
        if not torch.cuda.is_available():
            raise RuntimeError("GPU unavailable")
        torch.manual_seed(generation["seed"])
        torch.cuda.manual_seed_all(generation["seed"])
        processor = transformers.AutoProcessor.from_pretrained(args.model_dir, local_files_only=True)
        print("Loading frozen 8B model", flush=True)
        model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
            args.model_dir, dtype=torch.bfloat16, device_map="cuda", local_files_only=True).eval()
        runtime.update(model=cfg, torch=str(torch.__version__), transformers=transformers.__version__)
    else:
        # This file is already hash-verified by download_public.py before the server is started.
        verified = json.loads((args.model_dir.parent / "verified_downloads.json").read_text())
        selected = next(record for record in verified if record["name"] == args.model_dir.name)
        if selected["sha256"] != "84b5f7f112156d63836a01a69dc3f11a6ba63b10a23b8ca7a7efaf52d5a2d806" or args.model_dir.stat().st_size != selected["size"]:
            raise ValueError("27B weights not verified")
        runtime.update(model="Qwen3.5-27B", quantization="Q4_K_M", downloads=verified,
                       backend_tag="b11517", backend_commit="8a1a9b5126126e5228b95fa909d4b08fac65e8b3")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "runtime.json").write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "responses.jsonl").open("x", encoding="utf-8") as handle:
        for index, packet in enumerate(packets, 1):
            request = (args.input_dir / f"{packet['case_id']}_request.txt").read_text(encoding="utf-8")
            print(f"Starting case {index}/8: {packet['case_id']}", flush=True)
            started = time.perf_counter()
            row = {"case_id": packet["case_id"]}
            if args.backend == "transformers_8b":
                messages = [{"role": "user", "content": [{"type": "text", "text": request}]}]
                rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                encoded = processor(text=[rendered], return_tensors="pt")
                if "pixel_values" in encoded or "image_grid_thw" in encoded:
                    raise ValueError("unexpected images")
                encoded = {key: value.to("cuda") for key, value in encoded.items()}
                count = int(encoded["input_ids"].shape[1])
                torch.cuda.synchronize()
                with torch.inference_mode():
                    output = model.generate(**encoded, do_sample=False, max_new_tokens=generation["max_new_tokens"],
                                            repetition_penalty=generation["repetition_penalty"])
                torch.cuda.synchronize()
                tokens = output[0][count:]
                row.update(raw=processor.decode(tokens, skip_special_tokens=True), input_tokens=count,
                           output_tokens=int(tokens.shape[0]))
            else:
                body = {"messages": [{"role": "user", "content": request}], "temperature": 0,
                        "max_tokens": generation["max_new_tokens"], "seed": generation["seed"],
                        "repeat_penalty": generation["repetition_penalty"], "cache_prompt": False,
                        "chat_template_kwargs": {"enable_thinking": False}}
                req = urllib.request.Request("http://127.0.0.1:8089/v1/chat/completions",
                                             data=json.dumps(body, ensure_ascii=False).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=600) as response:
                    result = json.load(response)
                message = result["choices"][0]["message"]
                row.update(raw=message["content"], input_tokens=result["usage"]["prompt_tokens"],
                           output_tokens=result["usage"]["completion_tokens"],
                           finish_reason=result["choices"][0]["finish_reason"],
                           reasoning_content=message.get("reasoning_content"))
            row["seconds"] = round(time.perf_counter() - started, 4)
            try:
                row.update(parse_valid=True, checked=parse_response(row["raw"], packet))
            except (ValueError, TypeError, KeyError) as exc:
                row.update(parse_valid=False, parse_error=str(exc))
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            print(json.dumps({"completed": index, "parse_valid": row["parse_valid"],
                              "seconds": row["seconds"], "output_tokens": row["output_tokens"]}), flush=True)
    print("Eight cases finished. No Actor actions executed.", flush=True)


if __name__ == "__main__":
    main()
