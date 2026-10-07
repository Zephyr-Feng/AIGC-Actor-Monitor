#!/usr/bin/env python3
"""Replay only the final STOP verdict with the frozen Actor-B model.

All prior Actor actions and tool observations come from the original trajectory.
The same model scores the two legal JSON string values at final_verdict; no
ground-truth label or tool score participates in the choice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from actor_b_protocol import parse_action
from run_b0 import canonical_hash, read_jsonl, sha256, write_json


VERDICT_FIELD = re.compile(r'(?<!\\)"final_verdict"\s*:\s*(null|"(?:[^"\\]|\\.)*")')
CANDIDATES = ("real", "fake")


def verdict_span(raw: str) -> tuple[dict, int, int]:
    original = json.loads(raw)
    matches = list(VERDICT_FIELD.finditer(raw))
    if len(matches) != 1 or original.get("next_action") != "STOP":
        raise ValueError("expected one final_verdict field in a STOP object")
    if original.get("selected_tool") is not None:
        raise ValueError("STOP must not select a tool")
    start, end = matches[0].span(1)
    if json.loads(raw[start:end]) != original["final_verdict"]:
        raise ValueError("verdict span differs from parsed JSON")
    return original, start, end


def replace_verdict(raw: str, verdict: str) -> str:
    if verdict not in CANDIDATES:
        raise ValueError("constrained verdict must be real or fake")
    original, start, end = verdict_span(raw)
    amended = raw[:start] + json.dumps(verdict) + raw[end:]
    changed = json.loads(amended)
    if {key: value for key, value in changed.items() if key != "final_verdict"} != {
        key: value for key, value in original.items() if key != "final_verdict"
    }:
        raise AssertionError("a non-verdict field changed")
    return amended


def reconstruct_stop_context(row: dict, image, prompt: str, cards: dict, schema: dict,
                             crop_loader, max_tool_calls: int) -> tuple[list[dict], str]:
    """Rebuild the exact messages preceding the last original STOP attempt."""
    initial = ("工具定义：\n" + json.dumps(cards, ensure_ascii=False, sort_keys=True) +
               "\n\n每一步的 JSON schema：\n" + json.dumps(schema, ensure_ascii=False, sort_keys=True) +
               "\n\n请观察原图，根据 schema 输出第一个动作。工具结果只能通过 CALL_TOOL 获得。")
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": [{"type": "image", "image": image},
                                               {"type": "text", "text": initial}]}]
    used: list[str] = []
    for index, step in enumerate(row["steps"]):
        attempts = step["attempts"]
        if not attempts:
            raise ValueError("trajectory step has no generation attempt")
        for attempt in attempts[:-1]:
            try:
                parse_action(attempt["raw"], set(used))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                messages.append({"role": "assistant", "content": attempt["raw"]})
                messages.append({"role": "user", "content":
                                 f"结构校验失败：{exc}。只修正 JSON 结构和枚举，不改变已有证据内容。"})
            else:
                raise ValueError("a non-final attempt was accepted")
        if index == len(row["steps"]) - 1:
            verdict_span(attempts[-1]["raw"])
            if used != row["tool_calls"]:
                raise ValueError("reconstructed tool history differs from original")
            return messages, attempts[-1]["raw"]
        parsed = parse_action(attempts[-1]["raw"], set(used))
        if parsed != step["actor_output"]:
            raise ValueError("accepted action differs from original trajectory")
        messages.append({"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)})
        if parsed["next_action"] != "CALL_TOOL":
            raise ValueError("STOP occurred before final trajectory step")
        if len(used) >= max_tool_calls:
            if step.get("runtime_error") != "tool budget exhausted":
                raise ValueError("unrecognized tool-budget state")
            messages.append({"role": "user", "content": "工具预算已用完。下一步必须 STOP。"})
            continue
        tool = parsed["selected_tool"]
        used.append(tool)
        observation = step["tool_observation"]
        if not observation or observation["tool"] != tool:
            raise ValueError("tool observation differs from selected tool")
        content = [{"type": "text", "text": "工具真实返回：\n" +
                    json.dumps(observation, ensure_ascii=False, sort_keys=True) +
                    "\n请更新 current_evidence，并选择下一动作。"}]
        if tool == "global_forensic_analyzer":
            for region in observation.get("most_atypical_regions", []):
                content.extend([{"type": "text", "text": f"{region['region_id']} 图块："},
                                {"type": "image", "image": crop_loader(region["crop_path"])}])
        messages.append({"role": "user", "content": content})
    raise AssertionError("missing final step")


def common_token_prefix(left: list[int], right: list[int]) -> int:
    count = 0
    for first, second in zip(left, right):
        if first != second:
            break
        count += 1
    return count


def score_legal_verdicts(model, processor, messages: list[dict], raw: str,
                         expected_input_tokens: int, expected_image_grids: int,
                         torch) -> tuple[dict[str, float], int]:
    """Conditional log likelihood of each legal JSON string at the verdict span."""
    _, start, _ = verdict_span(raw)
    rendered = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    raw_prefix = raw[:start]
    images = [part["image"] for message in messages if isinstance(message["content"], list)
              for part in message["content"] if part.get("type") == "image"]
    original_inputs = processor(text=[rendered], images=images, return_tensors="pt")
    grids = int(original_inputs["image_grid_thw"].shape[0]) if "image_grid_thw" in original_inputs else 0
    if int(original_inputs["input_ids"].shape[1]) != expected_input_tokens or grids != expected_image_grids:
        raise ValueError("reconstructed STOP context differs from the original processor input")
    # The original generation tokens were not saved, only their decoded text.
    # Re-encode that text once as an assistant continuation; visual inputs stay
    # exactly as they were in the original processor call above.
    prefix_ids = processor.tokenizer(raw_prefix, add_special_tokens=False)["input_ids"]
    candidates = {verdict: processor.tokenizer(raw_prefix + json.dumps(verdict),
                                              add_special_tokens=False)["input_ids"]
                  for verdict in CANDIDATES}
    real_ids, fake_ids = candidates["real"], candidates["fake"]
    shared = common_token_prefix(real_ids, fake_ids)
    # Qwen can merge a quote/space at the JSON value boundary with the first
    # value token. Score from the candidates' last common token boundary.
    if shared < len(prefix_ids) - 4 or shared == 0:
        raise ValueError("candidate tokenizations diverge before the verdict field")
    scores = {}
    for verdict in CANDIDATES:
        ids = candidates[verdict]
        if len(ids) <= shared:
            raise ValueError("verdict candidate has no distinct token suffix")
        inputs = {key: value.to("cuda") for key, value in original_inputs.items()}
        continuation = torch.tensor([ids], device="cuda", dtype=inputs["input_ids"].dtype)
        inputs["input_ids"] = torch.cat((inputs["input_ids"], continuation), dim=1)
        inputs["attention_mask"] = torch.cat((inputs["attention_mask"],
                                               torch.ones_like(continuation)), dim=1)
        candidate_tokens = len(ids) - shared
        with torch.inference_mode():
            # Installed Qwen3-VL supports logits_to_keep. The extra logit
            # predicts the first candidate token; the final logit is unused.
            logits = model(**inputs, use_cache=False,
                           logits_to_keep=candidate_tokens + 1).logits[0]
            targets = continuation[0, shared:]
            log_probs = torch.log_softmax(logits[:-1].float(), dim=-1)
            scores[verdict] = float(log_probs.gather(1, targets[:, None]).sum())
    return scores, len(prefix_ids) - shared


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tool-results", type=Path, required=True)
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--original-runtime", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--tool-cards", type=Path, required=True)
    parser.add_argument("--experiment-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-trajectories-sha256", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 is required for the model likelihood replay")
    original_runtime = json.loads(args.original_runtime.read_text(encoding="utf-8"))
    if sha256(args.trajectories) != args.expected_trajectories_sha256:
        raise ValueError("original trajectories SHA mismatch")
    for path, key in ((args.manifest, "manifest_sha256"), (args.tool_results, "tool_results_sha256")):
        if sha256(path) != original_runtime[key]:
            raise ValueError(f"frozen input SHA mismatch: {path}")
    prompt = (args.experiment_dir / "prompts/system_prompt.txt").read_text(encoding="utf-8").strip()
    schema = json.loads((args.experiment_dir / "schemas/actor_b_action.schema.json").read_text(encoding="utf-8"))
    generation = json.loads((args.experiment_dir / "config/generation_config.json").read_text(encoding="utf-8"))
    model_spec = json.loads((args.experiment_dir / "config/model_config.json").read_text(encoding="utf-8"))
    cards = json.loads(args.tool_cards.read_text(encoding="utf-8"))
    prompt_sha = canonical_hash({"system_prompt": prompt, "tool_cards": cards, "schema": schema,
                                 "generation": generation})
    if prompt_sha != original_runtime["prompt_sha256"] or generation != original_runtime["generation"]:
        raise ValueError("prompt or generation configuration changed")
    if sha256(args.experiment_dir / "schemas/actor_b_action.schema.json") != original_runtime["schema_sha256"]:
        raise ValueError("action schema changed")
    if model_spec["model_revision"] not in args.model_dir.resolve().parts:
        raise ValueError("model path does not contain the frozen revision")
    if sha256(args.model_dir / "config.json") != model_spec["model_config_sha256"]:
        raise ValueError("model config differs from the frozen Actor model")

    manifest = read_jsonl(args.manifest)
    records = read_jsonl(args.trajectories)
    tools_by_id = {row["sample_id"]: row for row in read_jsonl(args.tool_results)}
    if [r["sample_id"] for r in records] != [r["sample_id"] for r in manifest]:
        raise ValueError("trajectory order differs from frozen manifest")
    if set(tools_by_id) != {row["sample_id"] for row in manifest}:
        raise ValueError("tool results differ from frozen manifest")
    controls = {row["sample_id"] for row in read_jsonl(args.controls)}
    failures = {row["sample_id"] for row in records if not row["parse_valid"]}
    if len(failures) != 5 or len(controls) != 15 or controls & failures:
        raise ValueError("expected five failures and 15 disjoint controls")
    selected = failures | controls if args.mode == "pilot" else {row["sample_id"] for row in records}
    torch.manual_seed(int(generation["seed"]))
    torch.cuda.manual_seed_all(int(generation["seed"]))
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda").eval()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for number, (item, row) in enumerate(zip(manifest, records), 1):
        if row["sample_id"] not in selected:
            continue
        target = args.output_dir / "records" / (row["sample_id"].replace(":", "__") + ".json")
        if target.exists():
            if not args.resume:
                raise FileExistsError(target)
            prior = json.loads(target.read_text(encoding="utf-8"))
            if prior["original_trajectories_sha256"] != args.expected_trajectories_sha256:
                raise ValueError("resume input mismatch")
            continue
        image_path = args.image_root / item["relative_path"]
        if sha256(image_path) != item["sha256"] or row["image_sha256"] != item["sha256"]:
            raise ValueError("frozen image hash mismatch")
        available = {tool["tool"]: tool for tool in tools_by_id[row["sample_id"]]["tools"]}
        for step in row["steps"]:
            observed = step.get("tool_observation")
            if observed and observed != available[observed["tool"]]:
                raise ValueError("recorded tool observation differs from frozen input")
        with Image.open(image_path) as source:
            image = source.convert("RGB")

        def load_crop(relative: str):
            with Image.open(args.evidence_dir / relative) as source:
                return source.convert("RGB")

        messages, raw = reconstruct_stop_context(row, image, prompt, cards, schema, load_crop,
                                                 int(generation["max_tool_calls"]))
        torch.cuda.synchronize()
        started = time.perf_counter()
        last_attempt = row["steps"][-1]["attempts"][-1]
        scores, retokenized_tokens = score_legal_verdicts(
            model, processor, messages, raw, int(last_attempt["input_tokens"]),
            int(last_attempt["image_grids"]), torch)
        torch.cuda.synchronize()
        if scores["real"] == scores["fake"]:
            raise ValueError("forced choice is tied")
        chosen = max(scores, key=scores.get)
        constrained = replace_verdict(raw, chosen)
        parsed = parse_action(constrained, set(row["tool_calls"]))
        original, _, _ = verdict_span(raw)
        write_json(target, {"sample_id": row["sample_id"],
                            "original_trajectories_sha256": args.expected_trajectories_sha256,
                            "pre_stop_steps_sha256": canonical_hash(row["steps"][:-1]),
                            "original_parse_valid": row["parse_valid"],
                            "original_final_verdict": original["final_verdict"],
                            "raw_unconstrained_output": raw,
                            "contract_constrained_output": constrained,
                            "contract_verdict": parsed["final_verdict"],
                            "verdict_log_likelihood": {key: round(value, 9)
                                                       for key, value in scores.items()},
                            "field_boundary_retokenized_tokens": retokenized_tokens,
                            "verdict_preserved": row["parse_valid"] and
                                                 parsed["final_verdict"] == row["final_verdict"],
                            "tool_calls": row["tool_calls"],
                            "seconds": round(time.perf_counter() - started, 4)})
        print(f"B0-C {args.mode} {number}/{len(records)} valid=True preserve="
              f"{row['parse_valid'] and chosen == row['final_verdict']}", flush=True)
    output_rows = [json.loads((args.output_dir / "records" /
                              (row["sample_id"].replace(":", "__") + ".json")).read_text(encoding="utf-8"))
                   for row in records if row["sample_id"] in selected]
    (args.output_dir / "replay.jsonl").write_bytes(
        b"".join((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
                 for row in output_rows))
    write_json(args.output_dir / "runtime.json", {"mode": args.mode, "records": len(output_rows),
               "original_trajectories_sha256": args.expected_trajectories_sha256,
               "manifest_sha256": sha256(args.manifest), "tool_results_sha256": sha256(args.tool_results),
               "model_revision": model_spec["model_revision"], "prompt_sha256": prompt_sha,
               "schema_sha256": original_runtime["schema_sha256"], "generation": generation,
               "decoder_sha256": sha256(Path(__file__)),
               "scoring": "sum of model conditional log likelihood for exact JSON strings real/fake",
               "torch": torch.__version__, "transformers": transformers.__version__})


if __name__ == "__main__":
    main()
