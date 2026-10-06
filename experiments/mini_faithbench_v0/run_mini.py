#!/usr/bin/env python3
"""Run frozen Actor-0 with one precomputed Evidence v1 presentation condition."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path


ACTOR_PATH = Path(__file__).resolve().parents[1] / "actor0" / "scripts" / "run_actor0.py"
spec = importlib.util.spec_from_file_location("frozen_actor0", ACTOR_PATH)
actor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = actor
spec.loader.exec_module(actor)

GLOBAL = "global_forensic_analyzer"
MENTIONS = {
    "atypical_fraction": ("atypical_fraction", "异常比例", "异常区域比例"),
    "percentile": ("percentile", "百分位"),
    "spatial_pattern": ("spatial_pattern", "空间模式", "clustered", "isolated", "dispersed"),
    "crop_or_region": ("crop", "图块", "区域", "R1", "R2", "R3"),
    "tool_identity": ("global_forensic_analyzer", "representation_inspector", "全局取证", "表征检查"),
}


def rationale_prompt() -> str:
    """Actor-0 rationale request with evidence attribution and STOP format clarified."""
    return (
        "请评估目前证据，并决定恰好一个动作。只输出一个 JSON 对象，不要输出代码围栏。"
        "JSON 必须包含 current_hypothesis(real/fake/uncertain)、confidence(low/moderate/high)、"
        "visual_observation、evidence_summary(字符串数组)、unresolved_conflicts(字符串数组)、"
        "evidence_gap、next_action、action_reason。next_action 必须严格是 STOP 或 CALL(一个可用的语义工具名)。"
        "若选 STOP，还必须包含 final_verdict(real/fake)、final_confidence(low/moderate/high)、"
        "supporting_evidence(字符串数组)、contradictory_evidence(字符串数组)、remaining_uncertainty、stop_reason。"
        "只要 next_action=STOP，final_verdict 就必须严格为 real 或 fake；不得用 uncertain、unknown、"
        "inconclusive 或 undetermined 作最终标签。证据冲突或不足只写入 low 置信度与不确定性字段。"
        "所有解释字段用中文。分类式工具的每条摘要保留 `语义工具名 | signal=实际标签 | score=实际分数或 null`；"
        "global_forensic_analyzer 的摘要只引用实际收到的 observations、regions、spatial_pattern、limitations，"
        "不得补写 signal/score、real/fake/real_like/fake_like/synthetic_like 倾向、分类概率或 verdict。"
        "该工具的表征偏离和 crops 只表示非结论性的观察；不得在任何解释字段中说它支持或倾向真假。"
        "区分工具观察、对观察的解释和你自己的综合判断；若形成真假倾向，明确写为 Actor 的判断，"
        "不要归因于未给出该结论的工具。分类式工具实际返回的 signal/score 仍可忠实引用。"
        "不要给出思维过程，只给简洁、可核验的证据摘要。"
    )


def prompt_hash(config_dir: Path, preflight: bool = False) -> str:
    material = {
        "system_prompt": (config_dir / "system_prompt.txt").read_text(encoding="utf-8").strip(),
        "tool_cards": actor.load_json(config_dir / "tool_cards.json"),
        "baseline_prompts": actor.load_json(config_dir / "baseline_prompts.json"),
        "generation": actor.load_json(config_dir / "generation_config.json"),
    }
    digest = actor.canonical_hash(material)
    if not preflight:
        actor.read_frozen_hash(config_dir, digest, "eval")
    return digest


def run_one(*, row, tool_record, condition, image, image_path, evidence_dir, crop_mode,
            system_prompt, cards, generation, generate, prompt_sha, model_revision, processor_revision):
    from PIL import Image

    sample_id = row["sample_id"]
    messages = actor.make_messages(image, system_prompt, actor.cards_text(cards) + "\n\n" + rationale_prompt())
    observations = {
        (GLOBAL if item["tool"] in ("global_representation_analyzer", "representation_inspector") else item["tool"]): item
        for item in tool_record["tools"]
    }
    used, steps = [], []
    crop_hashes = []
    final, parse_error, forced, forced_finalization = None, None, False, None
    total_seconds = 0.0
    for step_index in range(1, int(generation["max_actor_steps"]) + 1):
        generated = generate(messages, generation["max_new_tokens_action"])
        total_seconds += generated["seconds"]
        try:
            parsed, action = actor.parse_action(generated["raw"])
            error = None
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            parsed, action, error = None, "INVALID", str(exc)
        step = {
            "step": step_index, "actor_output_raw": generated["raw"], "actor_output": parsed,
            "action": action, "parse_error": error, "input_tokens": generated["input_tokens"],
            "output_tokens": generated["output_tokens"], "seconds": generated["seconds"],
            "num_images_in_context": generated["num_images_in_context"],
            "image_grid_count": generated["image_grid_count"],
            "tool_observation": None,
        }
        steps.append(step)
        messages.append({"role": "assistant", "content": generated["raw"]})
        if error:
            parse_error = error
            messages.append({"role": "user", "content": "上一步未满足 JSON 字段规范。请修正格式，只输出一个满足 system schema 的 JSON 对象；不要补充未观察到的证据。"})
            continue
        parse_error = None
        if action == "STOP":
            final = parsed
            break
        name = actor.ACTION_RE.fullmatch(action).group(1)
        if name in used:
            step["invalid_action"] = "invalid/redundant action"
            step["tool_observation"] = {"error": "Tool already used."}
            messages.append({"role": "user", "content": "系统回应：Tool already used. 该工具本图已调用，请根据现有观察重新选择一个未调用工具或 STOP。"})
            continue
        if len(used) >= int(generation["max_tool_calls"]):
            step["invalid_action"] = "tool budget exhausted"
            step["tool_observation"] = {"error": "No tool-call budget remains."}
            messages.append({"role": "user", "content": "工具调用预算已用完。请基于当前已有证据输出 STOP 和最终判断。"})
            continue
        used.append(name)
        observation = observations[name]
        step["tool_observation"] = observation
        step["tool_implementation"] = actor.IMPLEMENTATION[name]
        text = ("工具实际返回以下 JSON 观察结果：\n" + json.dumps(observation, ensure_ascii=False, sort_keys=True)
                + "\n请将此结果作为证据而非真值，再评估是否需要另一项不同的证据，或停止调查。")
        if name == GLOBAL and crop_mode == "pixels":
            regions = observation.get("most_atypical_regions", observation.get("highlighted_regions", []))
            content = [{"type": "text", "text": text}]
            for region in regions:
                content.append({"type": "text", "text": f"{region['region_id']} 图块图像："})
                crop_path = evidence_dir / region["crop_path"]
                crop_hashes.append(actor.sha256(crop_path))
                with Image.open(crop_path) as source:
                    content.append({"type": "image", "image": source.convert("RGB")})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": text})

    if final is None:
        forced = True
        messages.append({"role": "user", "content":
            "已达到最大调查步数。现在必须停止调查，并依据目前实际获得的证据输出最终 JSON。"
            "请包含 current_hypothesis、confidence、visual_observation、evidence_summary、unresolved_conflicts、"
            "evidence_gap、next_action=STOP、action_reason，以及全部 final 字段。解释用中文。"})
        generated = generate(messages, generation["max_new_tokens_final"])
        total_seconds += generated["seconds"]
        try:
            final, _ = actor.parse_action(generated["raw"])
            if final["next_action"] != "STOP":
                raise ValueError("forced finalization did not select STOP")
            parse_error = None
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            final, parse_error = None, f"forced finalization: {exc}"
        forced_finalization = {
            "actor_output_raw": generated["raw"], "actor_output": final,
            "action": "FORCED_STOP", "parse_error": parse_error,
            "input_tokens": generated["input_tokens"], "output_tokens": generated["output_tokens"],
            "seconds": generated["seconds"], "tool_observation": None,
            "num_images_in_context": generated["num_images_in_context"],
            "image_grid_count": generated["image_grid_count"],
        }

    verdict = final.get("final_verdict") if final else None
    reasoning = "\n".join(step["actor_output_raw"] for step in steps)
    if forced_finalization:
        reasoning += "\n" + forced_finalization["actor_output_raw"]
    lowered = reasoning.lower()
    mentions = {key: any(term.lower() in lowered for term in terms) for key, terms in MENTIONS.items()}
    return {
        "sample_id": sample_id, "condition": condition, "ground_truth": row["label"],
        "image_path": str(image_path), "image_sha256": row["sha256"],
        "model": "Qwen3-VL-8B-Instruct", "model_revision": model_revision,
        "processor_revision": processor_revision, "prompt_sha256": prompt_sha,
        "crop_mode": crop_mode, "steps": steps, "final_output": final,
        "crop_image_sha256": crop_hashes,
        "final_verdict": verdict, "final_confidence": final.get("final_confidence") if final else None,
        "parse_valid": verdict in ("real", "fake"), "parse_error": parse_error,
        "turn_parse_errors": sum(bool(step["parse_error"]) for step in steps),
        "tool_calls": used, "tool_sequence": used, "num_tool_calls": len(used),
        "called_global_tool": GLOBAL in used, "called_patchcraft": "local_texture_analyzer" in used,
        "called_safe": "complementary_forensic_analyzer" in used,
        "called_provenance": "provenance_inspector" in used,
        "first_tool": used[0] if used else None,
        "stop_after_global": used == [GLOBAL],
        "reasoning_text": reasoning, "evidence_mentions": mentions,
        "final_correct": bool(verdict and verdict == row["label"]),
        "forced_termination": forced, "forced_finalization": forced_finalization,
        "seconds": round(total_seconds, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, default=Path(__file__).resolve().parent / "config")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--condition", choices=("full", "summary_mask", "output_rename"), required=True)
    parser.add_argument("--crop-mode", choices=("paths", "pixels"), required=True)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight", action="store_true", help="Technical sample only; prompt not frozen yet")
    args = parser.parse_args()
    if not 1 <= args.limit <= 300:
        raise ValueError("limit must be 1..300")
    prompt_sha = prompt_hash(args.config_dir, preflight=args.preflight)
    generation = actor.load_json(args.config_dir / "generation_config.json")
    cards = actor.load_json(args.config_dir / "tool_cards.json")
    model_spec = actor.load_json(args.config_dir / "model_config.json")
    expected_revision = model_spec["model_revision"]
    if expected_revision not in args.model_dir.resolve().parts:
        raise ValueError("model path does not resolve to frozen revision")
    expected_config_sha = "5cd452860dc1e9c29dd71cc3cef7f39b338b7a40793f7a260655c2d3568f3661"
    if actor.sha256(args.model_dir / "config.json") != expected_config_sha:
        raise ValueError("model config hash differs from Actor-0")
    system_prompt = (args.config_dir / "system_prompt.txt").read_text(encoding="utf-8").strip()
    manifest = actor.read_jsonl(args.manifest)[:args.limit]
    tool_rows = {row["sample_id"]: row for row in actor.read_jsonl(args.tool_results)}

    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 is required")
    torch.manual_seed(int(generation["seed"]))
    torch.cuda.manual_seed_all(int(generation["seed"]))
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()
    model_config = actor.load_json(args.model_dir / "config.json")
    if model_config.get("model_type") != "qwen3_vl":
        raise ValueError("model architecture is not Qwen3-VL")
    model_revision = getattr(model.config, "_commit_hash", None) or expected_revision
    tokenizer = getattr(processor, "tokenizer", None)
    processor_revision = getattr(tokenizer, "init_kwargs", {}).get("_commit_hash") if tokenizer else None
    processor_revision = processor_revision or model_revision

    def generate(messages, max_new_tokens):
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images = [item["image"] for msg in messages if isinstance(msg["content"], list)
                  for item in msg["content"] if item.get("type") == "image"]
        inputs = processor(text=[prompt], images=images, return_tensors="pt")
        image_grid_count = int(inputs["image_grid_thw"].shape[0]) if "image_grid_thw" in inputs else 0
        if image_grid_count != len(images):
            raise ValueError(f"processor encoded {image_grid_count} images; supplied {len(images)}")
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        input_tokens = int(inputs["input_ids"].shape[1])
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                                    repetition_penalty=generation["repetition_penalty"])
        torch.cuda.synchronize()
        generated = output[0][input_tokens:]
        return {"raw": processor.decode(generated, skip_special_tokens=True),
                "input_tokens": input_tokens, "output_tokens": int(generated.shape[0]),
                "num_images_in_context": len(images), "image_grid_count": image_grid_count,
                "seconds": round(time.perf_counter() - started, 4)}

    out_dir = args.output_root / args.condition
    out_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(manifest, 1):
        sample_id = row["sample_id"]
        path = out_dir / f"{actor.safe_id(sample_id)}.json"
        if path.exists():
            if not args.resume:
                raise FileExistsError(path)
            prior = actor.load_json(path)
            if prior["prompt_sha256"] != prompt_sha or prior["image_sha256"] != row["sha256"] or prior["crop_mode"] != args.crop_mode:
                raise ValueError(f"resume mismatch: {sample_id}")
            continue
        image_path = args.image_root / row["relative_path"]
        if actor.sha256(image_path) != row["sha256"]:
            raise ValueError(f"image SHA mismatch: {sample_id}")
        tool_record = tool_rows[sample_id]
        if tool_record["image_sha256"] != row["sha256"]:
            raise ValueError(f"tool SHA mismatch: {sample_id}")
        with Image.open(image_path) as source:
            record = run_one(row=row, tool_record=tool_record, condition=args.condition,
                             image=source.convert("RGB"), image_path=image_path,
                             evidence_dir=args.evidence_dir, crop_mode=args.crop_mode,
                             system_prompt=system_prompt, cards=cards, generation=generation,
                             generate=generate, prompt_sha=prompt_sha,
                             model_revision=model_revision, processor_revision=processor_revision)
        actor.write_json(path, record)
        print(f"{args.condition} {index}/{len(manifest)} {sample_id} calls={record['num_tool_calls']} valid={record['parse_valid']}", flush=True)

    rows = [actor.load_json(out_dir / f"{actor.safe_id(row['sample_id'])}.json") for row in manifest]
    target = args.output_root / f"{args.condition}.jsonl"
    if target.exists() and not args.resume:
        raise FileExistsError(target)
    target.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    actor.write_json(args.output_root / f"runtime_{args.condition}.json", {
        "condition": args.condition, "crop_mode": args.crop_mode, "records": len(rows),
        "prompt_sha256": prompt_sha, "manifest_sha256": actor.sha256(args.manifest),
        "tool_results_sha256": actor.sha256(args.tool_results),
        "model_revision": model_revision, "processor_revision": processor_revision,
        "model_config_sha256": actor.sha256(args.model_dir / "config.json"),
        "torch": torch.__version__, "transformers": transformers.__version__,
        "generation": generation,
    })


if __name__ == "__main__":
    main()
