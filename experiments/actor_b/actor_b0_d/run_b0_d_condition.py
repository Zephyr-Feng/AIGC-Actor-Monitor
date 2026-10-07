#!/usr/bin/env python3
"""Run one B0-D perturbation while keeping Actor-B0-C assets frozen."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ACTOR_DIR = Path(__file__).resolve().parents[1]
if str(ACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(ACTOR_DIR))

from actor_b_protocol import TOOLS as BASE_TOOLS
from actor_b_protocol import extract_object, parse_action
from contract_replay import replace_verdict, score_legal_verdicts
from run_b0 import canonical_hash, read_jsonl, sha256, write_json


TOOLS_ORDER = tuple(BASE_TOOLS)
GLOBAL = "global_forensic_analyzer"
ALIAS = {
    "global_forensic_analyzer": "tool_alpha",
    "local_texture_analyzer": "tool_beta",
    "complementary_forensic_analyzer": "tool_gamma",
    "provenance_inspector": "tool_delta",
}
DESCRIPTION = {
    "global_forensic_analyzer": (
        "Returns image-region representation-deviation observations, spatial summaries, "
        "selected regions, and the corresponding crops. It does not return a real/fake verdict."
    ),
    "local_texture_analyzer": (
        "Returns the local-texture analysis fields: signal, score, strength, and limitations."
    ),
    "complementary_forensic_analyzer": (
        "Returns the complementary forensic analysis fields: signal, score, strength, and limitations."
    ),
    "provenance_inspector": (
        "Returns available provenance metadata observations and limitations; unavailable metadata is inconclusive."
    ),
}
PROBE_MASK_SENTENCE = (
    "global_forensic_analyzer 的表征偏离是非方向观察，工具本身不提供 real/fake 结论；"
    "不得把它直接写成支持 real 或 fake。"
)
PROBE_DELAY_ERROR = (
    "PROBE is unavailable as the first evidence source. Choose another available tool."
)


def canonical_to_visible(condition: str) -> dict[str, str]:
    if condition == "tool_rename":
        return dict(ALIAS)
    return {name: name for name in TOOLS_ORDER}


def condition_material(condition: str, prompt: str, schema: dict, cards: Any) -> tuple[str, dict, Any, tuple[str, ...]]:
    canonical_to_alias = canonical_to_visible(condition)
    alias_to_canonical = {value: key for key, value in canonical_to_alias.items()}

    if condition == "probe_mask":
        if PROBE_MASK_SENTENCE not in prompt:
            raise ValueError("cannot safely remove the frozen PROBE rule from system prompt")
        prompt = prompt.replace(
            PROBE_MASK_SENTENCE,
            "不得把非方向观察直接写成支持 real 或 fake。",
        )
    elif condition == "tool_rename":
        for canonical, alias in canonical_to_alias.items():
            prompt = prompt.replace(canonical, alias)

    if condition == "tool_rename" and any(name in prompt for name in TOOLS_ORDER):
        raise ValueError("renamed prompt still exposes a canonical tool name")
    if condition == "probe_mask" and GLOBAL in prompt:
        raise ValueError("masked prompt still names the hidden tool")

    variant_schema = copy.deepcopy(schema)
    allowed_canonical = tuple(name for name in TOOLS_ORDER
                              if not (condition == "probe_mask" and name == GLOBAL))
    visible_tools = tuple(canonical_to_alias[name] for name in allowed_canonical)
    variant_schema["properties"]["selected_tool"]["enum"] = [None, *visible_tools]
    source_enum = ["visual", *visible_tools]
    variant_schema["properties"]["current_evidence"]["items"]["properties"]["source"]["enum"] = source_enum

    variant_cards = transform_cards(cards, condition, canonical_to_alias)
    card_text = json.dumps(variant_cards, ensure_ascii=False, sort_keys=True).lower()
    if condition == "probe_mask" and GLOBAL in card_text:
        raise ValueError("masked registry still contains the hidden tool")
    if condition == "tool_rename":
        for forbidden in ("probe", "accuracy", "most reliable", "recommend", "strongest expert"):
            if forbidden in card_text:
                raise ValueError(f"renamed tool descriptions contain forbidden cue: {forbidden}")
    return prompt, variant_schema, variant_cards, allowed_canonical


def _tool_name_from_card(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in ("tool", "name"):
        if item.get(key) in TOOLS_ORDER:
            return item[key]
    function = item.get("function")
    if isinstance(function, dict) and function.get("name") in TOOLS_ORDER:
        return function["name"]
    return None


def _rename_card_value(value: Any, canonical: str, alias: str) -> Any:
    if isinstance(value, str):
        return alias if value == canonical else value
    if isinstance(value, list):
        return [_rename_card_value(item, canonical, alias) for item in value]
    if isinstance(value, dict):
        output = {}
        for key, child in value.items():
            if key in ("useful_when", "recommended_order", "accuracy", "reliability"):
                continue
            output[alias if key == canonical else key] = _rename_card_value(child, canonical, alias)
        return output
    return value


def _neutralize_card_descriptions(value: Any, description: str) -> Any:
    if isinstance(value, list):
        return [_neutralize_card_descriptions(item, description) for item in value]
    if not isinstance(value, dict):
        return value
    output = {}
    for key, child in value.items():
        if key in ("useful_when", "recommended_order", "accuracy", "reliability"):
            continue
        if key in ("description", "purpose", "returns") and isinstance(child, str):
            output[key] = description
        elif key in ("parameters", "input_schema", "schema"):
            output[key] = child
        else:
            output[key] = _neutralize_card_descriptions(child, description)
    return output


def _neutral_card(card: Any, canonical: str, alias: str) -> Any:
    if isinstance(card, str):
        return DESCRIPTION[canonical]
    if not isinstance(card, dict):
        raise ValueError("unsupported B0-C tool-card format for neutral rename")
    output = _neutralize_card_descriptions(
        _rename_card_value(card, canonical, alias), DESCRIPTION[canonical]
    )
    # Keep callable/function names and input schemas, while removing descriptive routing cues.
    if "limitations" in output:
        if canonical == GLOBAL:
            output["limitations"] = ["This observation has no real/fake direction."]
        else:
            output["limitations"] = ["Interpret only the fields present in this tool output."]
    if "function" in output and isinstance(output["function"], dict):
        output["function"].pop("useful_when", None)
    return output


def transform_cards(cards: Any, condition: str, mapping: dict[str, str]) -> Any:
    if condition in ("full", "probe_delay"):
        return copy.deepcopy(cards)
    if isinstance(cards, dict):
        if all(name in cards for name in TOOLS_ORDER):
            result = {}
            for canonical in TOOLS_ORDER:
                if condition == "probe_mask" and canonical == GLOBAL:
                    continue
                visible = mapping[canonical]
                value = cards[canonical]
                result[visible] = (_neutral_card(value, canonical, visible)
                                   if condition == "tool_rename" else copy.deepcopy(value))
            expected = len(TOOLS_ORDER) - int(condition == "probe_mask")
            if len(result) != expected:
                raise ValueError("tool-card mapping did not produce the required registry")
            return result
        output = copy.deepcopy(cards)
        for key in ("tools", "tool_cards", "registry"):
            if key in output:
                output[key] = transform_cards(output[key], condition, mapping)
                return output
        raise ValueError("unrecognized B0-C tool-card mapping; refusing to guess")
    if isinstance(cards, list):
        output = []
        found = set()
        for entry in cards:
            canonical = _tool_name_from_card(entry)
            if canonical is None:
                output.append(copy.deepcopy(entry))
                continue
            found.add(canonical)
            if condition == "probe_mask" and canonical == GLOBAL:
                continue
            alias = mapping[canonical]
            rewritten = _rename_card_value(entry, canonical, alias)
            if condition == "tool_rename":
                rewritten = _neutral_card(rewritten, canonical, alias)
                if "name" in rewritten:
                    rewritten["name"] = alias
                if "tool" in rewritten:
                    rewritten["tool"] = alias
                if isinstance(rewritten.get("function"), dict):
                    rewritten["function"]["name"] = alias
            output.append(rewritten)
        expected = set(TOOLS_ORDER)
        if condition == "probe_mask":
            expected.remove(GLOBAL)
        if found != set(TOOLS_ORDER):
            raise ValueError("tool-card list does not expose every frozen B0-C tool")
        return output
    raise ValueError("unsupported B0-C tool-card format")


def parse_variant(raw: str, used_canonical: set[str], alias_to_canonical: dict[str, str],
                  allowed_canonical: set[str]) -> tuple[dict, dict]:
    visible = extract_object(raw)
    canonical = copy.deepcopy(visible)
    if isinstance(canonical.get("selected_tool"), str):
        canonical["selected_tool"] = alias_to_canonical.get(
            canonical["selected_tool"], canonical["selected_tool"]
        )
    for evidence in canonical.get("current_evidence", []):
        if isinstance(evidence, dict) and isinstance(evidence.get("source"), str):
            evidence["source"] = alias_to_canonical.get(evidence["source"], evidence["source"])
    if canonical.get("next_action") == "CALL_TOOL":
        selected = canonical.get("selected_tool")
        if selected not in allowed_canonical:
            raise ValueError("selected_tool is not in the exposed tool registry")
    if any(item.get("source") in TOOLS_ORDER and item["source"] not in allowed_canonical
           for item in canonical.get("current_evidence", []) if isinstance(item, dict)):
        raise ValueError("current_evidence cites a tool unavailable in this condition")
    parsed = parse_action(json.dumps(canonical, ensure_ascii=False), used_canonical)
    return visible, parsed


def file_prompt_hash(prompt: str, cards: Any, schema: dict, generation: dict) -> str:
    return canonical_hash({"system_prompt": prompt, "tool_cards": cards,
                           "schema": schema, "generation": generation})


def try_invalid_verdict_projection(raw: str, messages: list[dict], generated: dict,
                                   model: Any, processor: Any, torch: Any,
                                   used_canonical: set[str], alias_to_canonical: dict[str, str],
                                   allowed_canonical: set[str]) -> tuple[dict | None, dict | None]:
    """Repair only an invalid verdict on an otherwise valid terminal STOP."""
    try:
        value = extract_object(raw)
        if value.get("next_action") != "STOP" or value.get("selected_tool") is not None:
            return None, None
        if value.get("final_verdict") in ("real", "fake"):
            return None, None
        temporary = copy.deepcopy(value)
        temporary["final_verdict"] = "real"
        parse_variant(json.dumps(temporary, ensure_ascii=False), used_canonical,
                      alias_to_canonical, allowed_canonical)
        scores, retokenized = score_legal_verdicts(
            model, processor, messages, raw,
            int(generated["input_tokens"]), int(generated["image_grids"]), torch,
        )
        if scores["real"] == scores["fake"]:
            return None, {
                "applied": False,
                "unresolved_exact_tie": True,
                "scores": scores,
                "retokenized_tokens": retokenized,
                "reason": "no legal original verdict exists to preserve on an exact tie",
            }
        selected = max(scores, key=scores.get)
        constrained = replace_verdict(raw, selected)
        visible, canonical = parse_variant(
            constrained, used_canonical, alias_to_canonical, allowed_canonical
        )
        return visible, {
            "applied": True,
            "selected_verdict": canonical["final_verdict"],
            "scores": scores,
            "retokenized_tokens": retokenized,
        }
    except (ValueError, TypeError, json.JSONDecodeError, KeyError, IndexError):
        return None, None


def write_record(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def run(args: argparse.Namespace) -> None:
    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 is required for B0-D Actor inference")
    prompt_base = (args.experiment_dir / "prompts/system_prompt.txt").read_text(encoding="utf-8").strip()
    schema_base = json.loads((args.experiment_dir / "schemas/actor_b_action.schema.json").read_text(encoding="utf-8"))
    generation = json.loads((args.experiment_dir / "config/generation_config.json").read_text(encoding="utf-8"))
    model_spec = json.loads((args.experiment_dir / "config/model_config.json").read_text(encoding="utf-8"))
    base_cards = json.loads(args.tool_cards.read_text(encoding="utf-8"))
    base_prompt_sha = file_prompt_hash(prompt_base, base_cards, schema_base, generation)
    baseline_runtime = json.loads(args.b0_runtime.read_text(encoding="utf-8"))
    if base_prompt_sha != baseline_runtime["prompt_sha256"]:
        raise ValueError("base tool cards/prompt/schema/generation do not reproduce frozen B0-C prompt hash")
    if generation != baseline_runtime["generation"]:
        raise ValueError("generation configuration differs from frozen B0-C")
    if str(torch.__version__) != baseline_runtime["torch"]:
        raise ValueError("PyTorch runtime differs from frozen B0-C")
    if transformers.__version__ != baseline_runtime["transformers"]:
        raise ValueError("Transformers runtime differs from frozen B0-C")
    if sha256(args.experiment_dir / "schemas/actor_b_action.schema.json") != baseline_runtime["schema_sha256"]:
        raise ValueError("base Actor-B schema differs from frozen B0-C")
    prompt, schema, cards, allowed_tools = condition_material(
        args.condition, prompt_base, schema_base, base_cards
    )
    visible_to_canonical = {visible: canonical for canonical, visible in canonical_to_visible(args.condition).items()}
    allowed_canonical = set(allowed_tools)
    prompt_sha = file_prompt_hash(prompt, cards, schema, generation)
    run_control_sha = sha256(Path(__file__))
    run_fingerprint = canonical_hash({
        "condition": args.condition,
        "prompt_sha256": prompt_sha,
        "base_prompt_sha256": base_prompt_sha,
        "manifest_sha256": sha256(args.manifest),
        "tool_results_sha256": sha256(args.tool_results),
        "generation": generation,
        "model_revision": model_spec["model_revision"],
        "torch": str(torch.__version__),
        "transformers": transformers.__version__,
        "run_control_sha256": run_control_sha,
    })
    if model_spec["model_revision"] not in args.model_dir.resolve().parts:
        raise ValueError("model path does not contain the frozen revision")
    if sha256(args.model_dir / "config.json") != model_spec["model_config_sha256"]:
        raise ValueError("model config hash differs from frozen Actor-B0-C")

    manifest = read_jsonl(args.manifest)
    tool_rows = read_jsonl(args.tool_results)
    tools_by_id = {row["sample_id"]: row for row in tool_rows}
    if len(manifest) != args.expected_records or set(tools_by_id) != {row["sample_id"] for row in manifest}:
        raise ValueError("B0-D actor manifest and cached tool results do not align")
    if any(set(row) != {"sample_id", "relative_path", "sha256"} for row in manifest):
        raise ValueError("actor input manifest must exclude GT, source group, generator, and categories")

    torch.manual_seed(int(generation["seed"]))
    torch.cuda.manual_seed_all(int(generation["seed"]))
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()

    def generate(messages: list[dict]) -> dict:
        rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        images = [part["image"] for message in messages if isinstance(message.get("content"), list)
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
            output = model.generate(
                **inputs,
                max_new_tokens=int(generation["max_new_tokens"]),
                do_sample=False,
                repetition_penalty=float(generation["repetition_penalty"]),
            )
        torch.cuda.synchronize()
        generated_tokens = output[0][input_tokens:]
        return {
            "raw": processor.decode(generated_tokens, skip_special_tokens=True),
            "input_tokens": input_tokens,
            "output_tokens": int(generated_tokens.shape[0]),
            "seconds": round(time.perf_counter() - started, 4),
            "num_images": len(images),
            "image_grids": grids,
        }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_dir = args.output_dir / "records"
    for number, row in enumerate(manifest, 1):
        record_path = records_dir / f"{row['sample_id'].replace(':', '__')}.json"
        if record_path.exists():
            if not args.resume:
                raise FileExistsError(record_path)
            prior = json.loads(record_path.read_text(encoding="utf-8"))
            if prior.get("run_fingerprint") != run_fingerprint or prior.get("image_sha256") != row["sha256"]:
                raise ValueError("resume input hash mismatch")
            continue
        image_path = args.image_root / row["relative_path"]
        if sha256(image_path) != row["sha256"]:
            raise ValueError("image SHA-256 differs from frozen B0-C")
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        tool_record = tools_by_id[row["sample_id"]]
        observations = {item["tool"]: item for item in tool_record["tools"]}
        if tuple(observations) != TOOLS_ORDER:
            raise ValueError("cached tool order differs from frozen B0-C")

        initial = (
            "工具定义：\n" + json.dumps(cards, ensure_ascii=False, sort_keys=True)
            + "\n\n每一步的 JSON schema：\n" + json.dumps(schema, ensure_ascii=False, sort_keys=True)
            + "\n\n请观察原图，根据 schema 输出第一个动作。工具结果只能通过 CALL_TOOL 获得。"
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": [
                {"type": "image", "image": image}, {"type": "text", "text": initial}
            ]},
        ]
        used_canonical: set[str] = set()
        successful_calls: list[str] = []
        call_attempts: list[dict] = []
        steps: list[dict] = []
        final_output = None
        raw_final = None
        final_context = None
        final_generated = None
        format_errors = 0
        unavailable_tool_attempts = 0
        blocked_probe_attempts = 0
        started_total = time.perf_counter()

        for step_number in range(1, int(generation["max_actor_steps"]) + 1):
            generated = None
            parsed_visible = None
            parsed_canonical = None
            error = None
            attempts = []
            contexts = []
            for _repair in range(int(generation["max_format_repairs_per_step"]) + 1):
                contexts.append(list(messages))
                generated = generate(messages)
                attempts.append(generated)
                try:
                    parsed_visible, parsed_canonical = parse_variant(
                        generated["raw"], used_canonical, visible_to_canonical, allowed_canonical
                    )
                    error = None
                    break
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    error = str(exc)
                    format_errors += 1
                    if "not in the exposed tool registry" in error or "unavailable in this condition" in error:
                        unavailable_tool_attempts += 1
                    messages.append({"role": "assistant", "content": generated["raw"]})
                    messages.append({"role": "user", "content":
                                     f"结构校验失败：{error}。只修正 JSON 结构和枚举，不改变已有证据内容。"})
            raw_final = generated["raw"] if generated else None
            final_context = contexts[-1] if contexts else None
            final_generated = generated
            step = {
                "step": step_number,
                "attempts": attempts,
                "actor_output": parsed_visible,
                "canonical_action": parsed_canonical,
                "parse_error": error,
                "tool_input": None,
                "tool_observation": None,
                "call_status": None,
            }
            steps.append(step)
            if parsed_visible is None or parsed_canonical is None:
                break
            messages.append({"role": "assistant", "content": json.dumps(parsed_visible, ensure_ascii=False)})
            if parsed_canonical["next_action"] == "STOP":
                final_output = parsed_visible
                break

            visible_tool = parsed_visible["selected_tool"]
            canonical_tool = parsed_canonical["selected_tool"]
            call_attempts.append({"step": step_number, "tool": visible_tool,
                                  "canonical_tool": canonical_tool})
            if len(call_attempts) > int(generation["max_tool_calls"]):
                step["call_status"] = "over_budget"
                step["tool_observation"] = {"contract_error": True, "message": "tool-call budget exhausted"}
                messages.append({"role": "user", "content": "工具预算已用完。下一步必须 STOP。"})
                continue

            if (args.condition == "probe_delay" and not successful_calls
                    and canonical_tool == GLOBAL and len(call_attempts) == 1):
                blocked_probe_attempts += 1
                step["call_status"] = "blocked_first_probe_contract_error"
                step["tool_observation"] = {"contract_error": True, "message": PROBE_DELAY_ERROR}
                messages.append({"role": "user", "content": PROBE_DELAY_ERROR})
                continue

            successful_calls.append(visible_tool)
            used_canonical.add(canonical_tool)
            step["call_status"] = "success"
            step["tool_input"] = {
                "sample_id": row["sample_id"],
                "image_sha256": row["sha256"],
                "tool": visible_tool,
            }
            observation = copy.deepcopy(observations[canonical_tool])
            if "tool" in observation:
                observation["tool"] = visible_tool
            step["tool_observation"] = observation
            content = [{"type": "text", "text": "工具真实返回：\n" +
                       json.dumps(observation, ensure_ascii=False, sort_keys=True) +
                       "\n请更新 current_evidence，并选择下一动作。"}]
            if canonical_tool == GLOBAL:
                for region in observation.get("most_atypical_regions", []):
                    crop_path = args.evidence_dir / region["crop_path"]
                    with Image.open(crop_path) as crop_image:
                        content.extend([
                            {"type": "text", "text": f"{region['region_id']} 图块："},
                            {"type": "image", "image": crop_image.convert("RGB")},
                        ])
            messages.append({"role": "user", "content": content})

        projection = None
        effective_output = final_output
        effective_raw = None
        if final_output is not None:
            effective_raw = raw_final
        elif raw_final is not None and final_context is not None and final_generated is not None:
            projected, projection = try_invalid_verdict_projection(
                raw_final, final_context, final_generated, model, processor, torch,
                used_canonical, visible_to_canonical, allowed_canonical,
            )
            if projected is not None:
                effective_output = projected
                effective_raw = replace_verdict(raw_final, projected["final_verdict"])

        raw_parse_valid = final_output is not None
        effective_parse_valid = effective_output is not None
        record = {
            "condition": args.condition,
            "sample_id": row["sample_id"],
            "relative_path": row["relative_path"],
            "image_sha256": row["sha256"],
            "model_revision": model_spec["model_revision"],
            "base_prompt_sha256": base_prompt_sha,
            "condition_prompt_sha256": prompt_sha,
            "schema_sha256": canonical_hash(schema),
            "tool_cards_sha256": canonical_hash(cards),
            "run_fingerprint": run_fingerprint,
            "run_control_sha256": run_control_sha,
            "steps": steps,
            "tool_call_attempts": call_attempts,
            "tool_calls": successful_calls,
            "num_tool_calls": len(successful_calls),
            "call_budget_used": min(len(call_attempts), int(generation["max_tool_calls"])),
            "format_error_count": format_errors,
            "unavailable_tool_attempts": unavailable_tool_attempts,
            "blocked_probe_attempts": blocked_probe_attempts,
            "raw_final_output": final_output,
            "raw_terminal_text": raw_final,
            "raw_parse_valid": raw_parse_valid,
            "minimal_stop_projection": projection,
            "effective_final_output": effective_output,
            "effective_final_raw": effective_raw,
            "effective_parse_valid": effective_parse_valid,
            "effective_final_verdict": (effective_output or {}).get("final_verdict"),
            "seconds": round(time.perf_counter() - started_total, 4),
        }
        write_record(record_path, record)
        print(f"B0-D {args.condition} {number}/{len(manifest)} raw_valid={raw_parse_valid} "
              f"effective_valid={effective_parse_valid} calls={len(successful_calls)}", flush=True)

    records = [json.loads((records_dir / f"{row['sample_id'].replace(':', '__')}.json").read_text(encoding="utf-8"))
               for row in manifest]
    trajectory_path = args.output_dir / "trajectories.jsonl"
    trajectory_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    runtime = {
        "condition": args.condition,
        "records": len(records),
        "base_prompt_sha256": base_prompt_sha,
        "condition_prompt_sha256": prompt_sha,
        "schema_sha256": canonical_hash(schema),
        "tool_cards_sha256": canonical_hash(cards),
        "manifest_sha256": sha256(args.manifest),
        "tool_results_sha256": sha256(args.tool_results),
        "model_revision": model_spec["model_revision"],
        "generation": generation,
        "run_fingerprint": run_fingerprint,
        "run_control_sha256": run_control_sha,
        "model_config_sha256": sha256(args.model_dir / "config.json"),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "runtime_seconds_sum": round(sum(row["seconds"] for row in records), 2),
        "raw_parse_success": sum(row["raw_parse_valid"] for row in records),
        "effective_parse_success": sum(row["effective_parse_valid"] for row in records),
        "blocked_probe_attempts": sum(row["blocked_probe_attempts"] for row in records),
        "unavailable_tool_attempts": sum(row["unavailable_tool_attempts"] for row in records),
    }
    write_json(args.output_dir / "runtime.json", runtime)
    print(json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("probe_mask", "probe_delay", "tool_rename"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--tool-cards", type=Path, required=True)
    parser.add_argument("--b0-runtime", type=Path, required=True)
    parser.add_argument("--experiment-dir", type=Path, default=ROOT / "experiments/actor_b")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, default=60)
    parser.add_argument("--resume", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
