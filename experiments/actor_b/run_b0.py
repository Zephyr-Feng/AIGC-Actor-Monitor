#!/usr/bin/env python3
"""Run the structured, prompt-only Actor-B0 sanity baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from actor_b_protocol import TOOLS, parse_action


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def safe_id(sample_id: str) -> str:
    return sample_id.replace(":", "__")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--tool-cards", type=Path, required=True)
    parser.add_argument("--experiment-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 is required for Actor-B0 inference")
    prompt = (args.experiment_dir / "prompts/system_prompt.txt").read_text(encoding="utf-8").strip()
    schema = json.loads((args.experiment_dir / "schemas/actor_b_action.schema.json").read_text(encoding="utf-8"))
    generation = json.loads((args.experiment_dir / "config/generation_config.json").read_text(encoding="utf-8"))
    model_spec = json.loads((args.experiment_dir / "config/model_config.json").read_text(encoding="utf-8"))
    cards = json.loads(args.tool_cards.read_text(encoding="utf-8"))
    prompt_sha = canonical_hash({"system_prompt": prompt, "tool_cards": cards, "schema": schema, "generation": generation})
    if model_spec["model_revision"] not in args.model_dir.resolve().parts:
        raise ValueError("model path does not contain the frozen revision")
    if sha256(args.model_dir / "config.json") != model_spec["model_config_sha256"]:
        raise ValueError("model config hash differs from the frozen Actor model")

    manifest = read_jsonl(args.manifest)
    tools_by_id = {row["sample_id"]: row for row in read_jsonl(args.tool_results)}
    if len(manifest) != 30 or set(tools_by_id) != {row["sample_id"] for row in manifest}:
        raise ValueError("Actor-B0 expects the fixed 30-image sanity set")
    torch.manual_seed(int(generation["seed"]))
    torch.cuda.manual_seed_all(int(generation["seed"]))
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()

    def generate(messages):
        rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images = [part["image"] for message in messages if isinstance(message["content"], list)
                  for part in message["content"] if part.get("type") == "image"]
        inputs = processor(text=[rendered], images=images, return_tensors="pt")
        grids = int(inputs["image_grid_thw"].shape[0]) if "image_grid_thw" in inputs else 0
        if grids != len(images):
            raise ValueError(f"processor image mismatch: supplied={len(images)} encoded={grids}")
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        input_tokens = int(inputs["input_ids"].shape[1])
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=int(generation["max_new_tokens"]),
                                    do_sample=False, repetition_penalty=float(generation["repetition_penalty"]))
        torch.cuda.synchronize()
        tokens = output[0][input_tokens:]
        return {"raw": processor.decode(tokens, skip_special_tokens=True), "input_tokens": input_tokens,
                "output_tokens": int(tokens.shape[0]), "seconds": round(time.perf_counter() - started, 4),
                "num_images": len(images), "image_grids": grids}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for number, row in enumerate(manifest, 1):
        target = args.output_dir / "records" / f"{safe_id(row['sample_id'])}.json"
        if target.exists():
            if not args.resume:
                raise FileExistsError(target)
            prior = json.loads(target.read_text(encoding="utf-8"))
            if prior["prompt_sha256"] != prompt_sha or prior["image_sha256"] != row["sha256"]:
                raise ValueError(f"resume mismatch: {row['sample_id']}")
            continue
        image_path = args.image_root / row["relative_path"]
        if sha256(image_path) != row["sha256"]:
            raise ValueError(f"image SHA mismatch: {row['sample_id']}")
        tool_record = tools_by_id[row["sample_id"]]
        observations = {item["tool"]: item for item in tool_record["tools"]}
        if tuple(observations) != TOOLS:
            raise ValueError(f"tool protocol mismatch: {row['sample_id']}")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        initial = ("工具定义：\n" + json.dumps(cards, ensure_ascii=False, sort_keys=True) +
                   "\n\n每一步的 JSON schema：\n" + json.dumps(schema, ensure_ascii=False, sort_keys=True) +
                   "\n\n请观察原图，根据 schema 输出第一个动作。工具结果只能通过 CALL_TOOL 获得。")
        messages = [{"role": "system", "content": prompt},
                    {"role": "user", "content": [{"type": "image", "image": image},
                                                   {"type": "text", "text": initial}]}]
        used, steps, final = [], [], None
        format_errors = 0
        started_total = time.perf_counter()
        for step_number in range(1, int(generation["max_actor_steps"]) + 1):
            generated, parsed, error = None, None, None
            attempts = []
            for repair in range(int(generation["max_format_repairs_per_step"]) + 1):
                generated = generate(messages)
                attempts.append(generated)
                try:
                    parsed = parse_action(generated["raw"], set(used))
                    error = None
                    break
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    error = str(exc)
                    format_errors += 1
                    messages.append({"role": "assistant", "content": generated["raw"]})
                    messages.append({"role": "user", "content":
                                     f"结构校验失败：{error}。只修正 JSON 结构和枚举，不改变已有证据内容。"})
            step = {"step": step_number, "attempts": attempts, "actor_output": parsed,
                    "parse_error": error, "tool_observation": None}
            steps.append(step)
            if parsed is None:
                break
            messages.append({"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)})
            if parsed["next_action"] == "STOP":
                final = parsed
                break
            tool = parsed["selected_tool"]
            if len(used) >= int(generation["max_tool_calls"]):
                step["runtime_error"] = "tool budget exhausted"
                messages.append({"role": "user", "content": "工具预算已用完。下一步必须 STOP。"})
                continue
            used.append(tool)
            observation = observations[tool]
            step["tool_observation"] = observation
            content = [{"type": "text", "text": "工具真实返回：\n" +
                       json.dumps(observation, ensure_ascii=False, sort_keys=True) +
                       "\n请更新 current_evidence，并选择下一动作。"}]
            if tool == "global_forensic_analyzer":
                for region in observation.get("most_atypical_regions", []):
                    crop = args.evidence_dir / region["crop_path"]
                    with Image.open(crop) as crop_image:
                        content.extend([{"type": "text", "text": f"{region['region_id']} 图块："},
                                        {"type": "image", "image": crop_image.convert("RGB")}])
            messages.append({"role": "user", "content": content})
        record = {"sample_id": row["sample_id"], "ground_truth": row["label"],
                  "generator": row["generator"], "source_group": row["source_group"],
                  "image_path": str(image_path), "image_sha256": row["sha256"],
                  "model": model_spec["model"], "model_revision": model_spec["model_revision"],
                  "prompt_sha256": prompt_sha, "schema_sha256": sha256(args.experiment_dir / "schemas/actor_b_action.schema.json"),
                  "steps": steps, "tool_calls": used, "num_tool_calls": len(used),
                  "format_error_count": format_errors, "final_output": final,
                  "parse_valid": final is not None, "final_verdict": final.get("final_verdict") if final else None,
                  "final_correct": bool(final and final["final_verdict"] == row["label"]),
                  "seconds": round(time.perf_counter() - started_total, 4)}
        write_json(target, record)
        print(f"B0 {number}/{len(manifest)} {row['sample_id']} calls={len(used)} valid={record['parse_valid']}", flush=True)
    records = [json.loads((args.output_dir / "records" / f"{safe_id(row['sample_id'])}.json").read_text(encoding="utf-8"))
               for row in manifest]
    (args.output_dir / "trajectories.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    write_json(args.output_dir / "runtime.json", {"records": len(records), "prompt_sha256": prompt_sha,
               "schema_sha256": sha256(args.experiment_dir / "schemas/actor_b_action.schema.json"),
               "manifest_sha256": sha256(args.manifest), "tool_results_sha256": sha256(args.tool_results),
               "model_revision": model_spec["model_revision"], "torch": torch.__version__,
               "transformers": transformers.__version__, "generation": generation})


if __name__ == "__main__":
    main()

