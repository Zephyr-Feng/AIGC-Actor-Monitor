#!/usr/bin/env python3
"""Run frozen Actor-0 baselines and the prompt-only autonomous investigator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import time
from pathlib import Path
from typing import Any


TOOL_ORDER = [
    "global_forensic_analyzer",
    "local_texture_analyzer",
    "complementary_forensic_analyzer",
    "provenance_inspector",
]
IMPLEMENTATION = {
    "global_forensic_analyzer": "PROBE-DINOv2",
    "local_texture_analyzer": "PatchCraft",
    "complementary_forensic_analyzer": "SAFE",
    "provenance_inspector": "c2patool + ExifTool",
}
ACTION_RE = re.compile(r"^CALL\((global_forensic_analyzer|local_texture_analyzer|complementary_forensic_analyzer|provenance_inspector)\)$")
RATIONALE_FIELDS = (
    "current_hypothesis", "confidence", "visual_observation", "evidence_summary",
    "unresolved_conflicts", "evidence_gap", "next_action", "action_reason",
)
FINAL_FIELDS = (
    "final_verdict", "final_confidence", "supporting_evidence",
    "contradictory_evidence", "remaining_uncertainty", "stop_reason",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return digest_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def safe_id(sample_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", sample_id)


def extract_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object found")
        value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def validate_common(obj: dict) -> None:
    for field in RATIONALE_FIELDS:
        if field not in obj:
            raise ValueError(f"missing field: {field}")
    if obj["current_hypothesis"] not in ("real", "fake", "uncertain"):
        raise ValueError("invalid current_hypothesis")
    if obj["confidence"] not in ("low", "moderate", "high"):
        raise ValueError("invalid confidence")
    if not isinstance(obj["visual_observation"], str) or not isinstance(obj["evidence_gap"], str):
        raise ValueError("visual_observation/evidence_gap must be strings")
    if not isinstance(obj["evidence_summary"], list) or not all(isinstance(x, str) for x in obj["evidence_summary"]):
        raise ValueError("evidence_summary must be a list of strings")
    if not isinstance(obj["unresolved_conflicts"], list) or not all(isinstance(x, str) for x in obj["unresolved_conflicts"]):
        raise ValueError("unresolved_conflicts must be a list of strings")
    if not isinstance(obj["action_reason"], str):
        raise ValueError("action_reason must be a string")


def validate_stop(obj: dict) -> None:
    for field in FINAL_FIELDS:
        if field not in obj:
            raise ValueError(f"STOP missing final field: {field}")
    if obj["final_verdict"] not in ("real", "fake"):
        raise ValueError("invalid final_verdict")
    if obj["final_confidence"] not in ("low", "moderate", "high"):
        raise ValueError("invalid final_confidence")
    for field in ("supporting_evidence", "contradictory_evidence"):
        if not isinstance(obj[field], list) or not all(isinstance(x, str) for x in obj[field]):
            raise ValueError(f"{field} must be a list of strings")
    for field in ("remaining_uncertainty", "stop_reason"):
        if not isinstance(obj[field], str):
            raise ValueError(f"{field} must be a string")


def parse_action(text: str) -> tuple[dict, str]:
    obj = extract_object(text)
    validate_common(obj)
    action = obj["next_action"]
    if action != "STOP" and ACTION_RE.fullmatch(action or "") is None:
        raise ValueError(f"invalid next_action: {action!r}")
    if action == "STOP":
        validate_stop(obj)
    return obj, action


def parse_final_only(text: str) -> dict:
    obj = extract_object(text)
    if obj.get("final_verdict") not in ("real", "fake"):
        raise ValueError("final_verdict must be real or fake")
    if obj.get("final_confidence") not in ("low", "moderate", "high"):
        raise ValueError("final_confidence must be low/moderate/high")
    for field in ("supporting_evidence", "contradictory_evidence"):
        if not isinstance(obj.get(field), list) or not all(isinstance(x, str) for x in obj[field]):
            raise ValueError(f"{field} must be a list of strings")
    for field in ("remaining_uncertainty", "stop_reason"):
        if not isinstance(obj.get(field), str):
            raise ValueError(f"{field} must be a string")
    return obj


def tool_strength(score: float) -> str:
    """Fixed descriptive score-extremity bins; not a calibrated probability."""
    if score <= 0.10 or score >= 0.90:
        return "high"
    if score <= 0.25 or score >= 0.75:
        return "moderate"
    return "low"


def tool_text(tools: list[dict]) -> str:
    return "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in tools)


def rationale_prompt() -> str:
    return (
        "请评估目前证据，并决定恰好一个动作。只输出一个 JSON 对象，不要输出代码围栏。"
        "JSON 必须包含 current_hypothesis(real/fake/uncertain)、confidence(low/moderate/high)、"
        "visual_observation、evidence_summary(字符串数组)、unresolved_conflicts(字符串数组)、"
        "evidence_gap、next_action、action_reason。next_action 必须严格是 STOP 或 CALL(一个可用的语义工具名)。"
        "若选 STOP，还必须包含 final_verdict(real/fake)、final_confidence(low/moderate/high)、"
        "supporting_evidence(字符串数组)、contradictory_evidence(字符串数组)、remaining_uncertainty、stop_reason。"
        "所有解释字段用中文。每条工具证据须保留 `语义工具名 | signal=实际标签 | score=实际分数或 null`，后接中文解释。"
        "不要给出思维过程，只给简洁、可核验的证据摘要。"
    )


def cards_text(cards: dict) -> str:
    return "语义工具说明（工具名称不对应可靠性排序）：\n" + json.dumps(cards, ensure_ascii=False, sort_keys=True)


def make_messages(image: Any, system_prompt: str, user_text: str) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": user_text},
        ]},
    ]


def read_frozen_hash(config_dir: Path, actual_hash: str, condition: str) -> None:
    freeze_path = config_dir / "prompt_sha256.txt"
    if condition in ("eval", "evaluation"):
        if not freeze_path.is_file():
            raise FileNotFoundError("Prompt must be frozen on the development set before evaluation")
        expected = freeze_path.read_text(encoding="utf-8").strip().split()[0]
        if expected != actual_hash:
            raise ValueError(f"prompt hash changed after freeze: {expected} != {actual_hash}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True,
                        help="Unified per-image JSONL with semantic tool observations")
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, default=Path(__file__).resolve().parents[1] / "config")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "eval"), required=True)
    parser.add_argument("--conditions", nargs="+", choices=("image_only", "forced_all", "autonomous"),
                        required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    tools_by_id = {row["sample_id"]: row for row in read_jsonl(args.tool_results)}
    cards = load_json(args.config_dir / "tool_cards.json")
    baseline_prompts = load_json(args.config_dir / "baseline_prompts.json")
    system_prompt = (args.config_dir / "system_prompt.txt").read_text(encoding="utf-8").strip()
    generation_config = load_json(args.config_dir / "generation_config.json")
    prompt_material = {
        "system_prompt": system_prompt,
        "tool_cards": cards,
        "baseline_prompts": baseline_prompts,
        "generation": generation_config,
    }
    prompt_sha = canonical_hash(prompt_material)
    read_frozen_hash(args.config_dir, prompt_sha, args.split)

    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 must be enabled before Actor-0 inference")
    torch.manual_seed(int(generation_config["seed"]))
    torch.cuda.manual_seed_all(int(generation_config["seed"]))
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()
    model.eval()
    model_config = load_json(args.model_dir / "config.json")
    if model_config.get("model_type") != "qwen3_vl":
        raise ValueError(f"expected Qwen3-VL config, found {model_config.get('model_type')!r}")
    model_config_sha = sha256(args.model_dir / "config.json")
    model_revision = getattr(model.config, "_commit_hash", None)
    processor_revision = getattr(processor, "tokenizer", None)
    processor_revision = getattr(processor_revision, "init_kwargs", {}).get("_commit_hash") if processor_revision else None
    processor_revision = processor_revision or model_revision

    def generate(messages: list[dict], image: Any, max_new_tokens: int) -> dict:
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[prompt], images=[image], return_tensors="pt")
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        input_tokens = int(inputs["input_ids"].shape[1])
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                                    repetition_penalty=generation_config["repetition_penalty"])
        torch.cuda.synchronize()
        generated = output[0][input_tokens:]
        return {
            "raw": processor.decode(generated, skip_special_tokens=True),
            "input_tokens": input_tokens,
            "output_tokens": int(generated.shape[0]),
            "seconds": round(time.perf_counter() - started, 4),
        }

    checkpoint = "dev" if args.split == "dev" else "evaluation"
    sample_records: list[dict] = []
    total = len(manifest)
    for condition in args.conditions:
        condition_dir = args.output_root / ("trajectories" if condition == "autonomous" else "baselines") / checkpoint / condition
        condition_dir.mkdir(parents=True, exist_ok=True)
        target = (args.output_root / "trajectories" / ("dev_trajectories.jsonl" if args.split == "dev" else "trajectories.jsonl") if condition == "autonomous"
                  else args.output_root / "baselines" / f"{condition}_{checkpoint}.jsonl")
        if target.exists() and not args.resume:
            raise FileExistsError(f"Refusing to overwrite existing output: {target}")
        existing = {}
        if args.resume:
            for path in condition_dir.glob("*.json"):
                try:
                    prior = load_json(path)
                    existing[prior["sample_id"]] = prior
                except (OSError, json.JSONDecodeError, KeyError):
                    continue
        for index, row in enumerate(manifest, 1):
            sample_id = row["sample_id"]
            image_path = args.image_root / row["relative_path"]
            image_hash = sha256(image_path)
            if image_hash != row["sha256"]:
                raise ValueError(f"image hash mismatch: {sample_id}")
            tool_record = tools_by_id.get(sample_id)
            if tool_record is None or tool_record.get("image_sha256") != image_hash:
                raise ValueError(f"tool observation missing or image mismatch: {sample_id}")
            if sample_id in existing:
                prior = existing[sample_id]
                if prior.get("prompt_sha256") != prompt_sha or prior.get("image_sha256") != image_hash:
                    raise ValueError(f"cannot resume incompatible output for {sample_id}")
                sample_records.append(prior)
                continue
            sample_path = condition_dir / f"{safe_id(sample_id)}.json"
            if sample_path.exists() and not args.resume:
                raise FileExistsError(f"Refusing to overwrite existing output: {sample_path}")
            with Image.open(image_path) as source_image:
                image = source_image.convert("RGB")
                if condition == "image_only":
                    messages = make_messages(
                        image,
                        baseline_prompts["image_only_system"],
                        baseline_prompts["image_only_user"] + "\n只输出 JSON：{\"final_verdict\":\"real|fake\",\"final_confidence\":\"low|moderate|high\",\"supporting_evidence\":[\"中文\"],\"contradictory_evidence\":[\"中文\"],\"remaining_uncertainty\":\"中文\",\"stop_reason\":\"中文\"}",
                    )
                    generated = generate(messages, image, generation_config["max_new_tokens_final"])
                    try:
                        final = parse_final_only(generated["raw"])
                        parse_error = None
                    except ValueError as exc:
                        final, parse_error = None, str(exc)
                    record = {
                        "sample_id": sample_id, "image_path": str(image_path), "image_sha256": image_hash,
                        "condition": condition, "model": "Qwen3-VL-8B-Instruct", "prompt_sha256": prompt_sha,
                        "model_revision": model_revision, "processor_revision": processor_revision,
                        "ground_truth": row["label"], "raw_output": generated["raw"], "parsed_output": final,
                        "parse_error": parse_error, "num_tool_calls": 0,
                        "final_verdict": final.get("final_verdict") if final else None,
                        "final_correct": bool(final and final["final_verdict"] == row["label"]),
                        "seconds": generated["seconds"], "forced_termination": False,
                    }
                elif condition == "forced_all":
                    all_tools = [item for item in tool_record["tools"]]
                    user_text = cards_text(cards) + "\n\n" + baseline_prompts["forced_all_user"] + "\n\n全部工具结果：\n" + tool_text(all_tools)
                    messages = make_messages(image, baseline_prompts["forced_all_system"], user_text + "\n只输出 JSON：{\"final_verdict\":\"real|fake\",\"final_confidence\":\"low|moderate|high\",\"supporting_evidence\":[\"中文\"],\"contradictory_evidence\":[\"中文\"],\"remaining_uncertainty\":\"中文\",\"stop_reason\":\"中文\"}")
                    generated = generate(messages, image, generation_config["max_new_tokens_final"])
                    try:
                        final = parse_final_only(generated["raw"])
                        parse_error = None
                    except ValueError as exc:
                        final, parse_error = None, str(exc)
                    record = {
                        "sample_id": sample_id, "image_path": str(image_path), "image_sha256": image_hash,
                        "condition": condition, "model": "Qwen3-VL-8B-Instruct", "prompt_sha256": prompt_sha,
                        "model_revision": model_revision, "processor_revision": processor_revision,
                        "ground_truth": row["label"], "tool_observations": all_tools,
                        "internal_tool_implementations": [IMPLEMENTATION[item["tool"]] for item in all_tools],
                        "raw_output": generated["raw"], "parsed_output": final, "parse_error": parse_error,
                        "num_tool_calls": 4,
                        "final_verdict": final.get("final_verdict") if final else None,
                        "final_correct": bool(final and final["final_verdict"] == row["label"]),
                        "seconds": generated["seconds"], "forced_termination": False,
                    }
                else:
                    record = run_autonomous(
                        sample_id=sample_id, image_path=image_path, image=image, image_hash=image_hash,
                        row=row, tool_record=tool_record, cards=cards, system_prompt=system_prompt,
                        generate=generate, prompt_sha=prompt_sha, model_revision=model_revision,
                        processor_revision=processor_revision, generation_config=generation_config,
                    )
            record["split"] = args.split
            write_json(condition_dir / f"{safe_id(sample_id)}.json", record)
            sample_records.append(record)
            print(f"{args.split} {condition} {index}/{total} {sample_id} calls={record.get('num_tool_calls', 0)} parse_error={bool(record.get('parse_error'))}", flush=True)

    args.output_root.mkdir(parents=True, exist_ok=True)
    for condition in args.conditions:
        condition_records = [record for record in sample_records if record.get("condition") == condition]
        if not condition_records:
            continue
        base = args.output_root / ("trajectories" if condition == "autonomous" else "baselines")
        if condition == "autonomous":
            target = base / ("dev_trajectories.jsonl" if args.split == "dev" else "trajectories.jsonl")
        else:
            target = base / f"{condition}_{checkpoint}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        rows_for_file = [record for record in condition_records if record.get("split") == args.split]
        target.write_text("".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in rows_for_file), encoding="utf-8")

    runtime = {
        "split": args.split, "conditions": args.conditions, "records_written": len(sample_records),
        "prompt_sha256": prompt_sha, "model_revision": model_revision,
        "processor_revision": processor_revision, "model_config_sha256": model_config_sha,
        "transformers": transformers.__version__,
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "generation": generation_config,
    }
    write_json(args.output_root / f"runtime_{args.split}.json", runtime)


def run_autonomous(
    *, sample_id: str, image_path: Path, image: Any, image_hash: str, row: dict,
    tool_record: dict, cards: dict, system_prompt: str, generate: Any, prompt_sha: str,
    model_revision: str | None, processor_revision: str | None, generation_config: dict,
) -> dict:
    user_text = cards_text(cards) + "\n\n" + rationale_prompt()
    messages = make_messages(image, system_prompt, user_text)
    observations = {item["tool"]: item for item in tool_record["tools"]}
    used: list[str] = []
    steps: list[dict] = []
    total_seconds = 0.0
    final: dict | None = None
    parse_error: str | None = None
    forced = False
    forced_finalization: dict | None = None

    for step_index in range(1, int(generation_config["max_actor_steps"]) + 1):
        generated = generate(messages, image, generation_config["max_new_tokens_action"])
        total_seconds += generated["seconds"]
        try:
            actor_output, action = parse_action(generated["raw"])
            error = None
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            actor_output, action, error = None, "INVALID", str(exc)
        step: dict[str, Any] = {
            "step": step_index, "actor_output_raw": generated["raw"], "actor_output": actor_output,
            "action": action, "parse_error": error, "input_tokens": generated["input_tokens"],
            "output_tokens": generated["output_tokens"], "seconds": generated["seconds"],
            "tool_observation": None,
        }
        steps.append(step)
        messages.append({"role": "assistant", "content": generated["raw"]})
        if error:
            parse_error = error
            step["invalid_tool_request"] = bool(re.search(r"CALL\(", generated["raw"]))
            messages.append({"role": "user", "content": "上一步未满足 JSON 字段规范。请修正格式，只输出一个满足 system schema 的 JSON 对象；不要补充未观察到的证据。"})
            continue
        parse_error = None
        if action == "STOP":
            final = actor_output
            break
        tool_name = ACTION_RE.fullmatch(action).group(1)
        if tool_name in used:
            step["invalid_action"] = "invalid/redundant action"
            step["tool_observation"] = {"error": "Tool already used."}
            parse_error = None
            messages.append({"role": "user", "content": "系统回应：Tool already used. 该工具本图已调用，请根据现有观察重新选择一个未调用工具或 STOP。"})
            continue
        if len(used) >= int(generation_config["max_tool_calls"]):
            step["invalid_action"] = "tool budget exhausted"
            step["tool_observation"] = {"error": "No tool-call budget remains."}
            messages.append({"role": "user", "content": "工具调用预算已用完。请基于当前已有证据输出 STOP 和最终判断。"})
            continue
        used.append(tool_name)
        observation = observations[tool_name]
        step["tool_implementation"] = IMPLEMENTATION[tool_name]
        step["tool_observation"] = observation
        messages.append({
            "role": "user",
            "content": "工具实际返回以下 JSON 观察结果：\n" + json.dumps(observation, ensure_ascii=False, sort_keys=True)
            + "\n请将此结果作为证据而非真值，再评估是否需要另一项不同的证据，或停止调查。",
        })

    if final is None:
        forced = True
        messages.append({
            "role": "user",
            "content": "已达到最大调查步数。现在必须停止调查，并依据目前实际获得的证据输出最终 JSON。"
            "请包含 current_hypothesis、confidence、visual_observation、evidence_summary、unresolved_conflicts、"
            "evidence_gap、next_action=STOP、action_reason，以及全部 final 字段。解释用中文。",
        })
        generated = generate(messages, image, generation_config["max_new_tokens_final"])
        total_seconds += generated["seconds"]
        try:
            final, _ = parse_action(generated["raw"])
            if final.get("next_action") != "STOP":
                raise ValueError("forced finalization did not select STOP")
            parse_error = None
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            final = None
            parse_error = f"forced finalization: {exc}"
        forced_finalization = {
            "actor_output_raw": generated["raw"], "actor_output": final,
            "action": "FORCED_STOP", "parse_error": parse_error,
            "input_tokens": generated["input_tokens"], "output_tokens": generated["output_tokens"],
            "seconds": generated["seconds"], "tool_observation": None,
        }

    verdict = final.get("final_verdict") if final else None
    return {
        "sample_id": sample_id, "image_path": str(image_path), "image_sha256": image_hash,
        "ground_truth": row["label"], "model": "Qwen3-VL-8B-Instruct", "prompt_version": "actor0-v1",
        "condition": "autonomous",
        "prompt_sha256": prompt_sha, "model_revision": model_revision, "processor_revision": processor_revision,
        "steps": steps, "final_output": final, "final_verdict": verdict,
        "split": "dev" if row["split"] == "development" else "eval",
        "tool_calls": used, "tool_implementations": [IMPLEMENTATION[name] for name in used],
        "num_tool_calls": len(used), "final_correct": bool(verdict and verdict == row["label"]),
        "forced_termination": forced, "parse_error": parse_error, "seconds": round(total_seconds, 4),
        "forced_finalization": forced_finalization,
    }


if __name__ == "__main__":
    main()
