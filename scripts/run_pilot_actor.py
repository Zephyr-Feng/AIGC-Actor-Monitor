"""Run vision A0 and three tool-conditioned arms on the same pilot images."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.checkpoint import (  # noqa: E402
    ACTION_PROMPTS, FINAL_PROMPT, PRELIMINARY_PROMPT,
    build_branch_messages, parse_final, parse_preliminary,
)
from actor_monitor.p0 import read_jsonl  # noqa: E402
from actor_monitor.pilot_tool_text import FORMAL_FAMILIES, format_formal_tool_results  # noqa: E402
from run_t0_actor import SYSTEM_PROMPT, initial_messages  # noqa: E402


def digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parsed(raw: str, parser_fn: object) -> dict:
    try:
        return {"parsed": vars(parser_fn(raw))}
    except ValueError as exc:
        return {"parse_error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    tool_rows = {row["sample_id"]: row for row in read_jsonl(args.tools)}
    refs = json.loads(args.references.read_text(encoding="utf-8"))["ranges"]
    prompt_hash = digest({
        "system": SYSTEM_PROMPT, "preliminary": PRELIMINARY_PROMPT,
        "final": FINAL_PROMPT, "actions": ACTION_PROMPTS,
    })
    model_config_hash = hashlib.sha256((args.model_dir / "config.json").read_bytes()).hexdigest()
    refs_hash = hashlib.sha256(args.references.read_bytes()).hexdigest()
    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("RTX 4090 must be enabled before Actor collection")
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    def generate(messages: list[dict], image: object, max_tokens: int) -> dict:
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[prompt], images=[image], return_tensors="pt")
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        input_tokens = inputs["input_ids"].shape[1]
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
        torch.cuda.synchronize()
        seconds = round(time.perf_counter() - started, 3)
        generated = output[0][input_tokens:]
        return {
            "raw": processor.decode(generated, skip_special_tokens=True),
            "input_tokens": int(input_tokens),
            "output_tokens": int(generated.shape[0]),
            "seconds": seconds,
        }

    run_config = {
        "model_dir": str(args.model_dir),
        "model_config_sha256": model_config_hash,
        "prompt_sha256": prompt_hash,
        "references_sha256": refs_hash,
        "tool_families": list(FORMAL_FAMILIES),
        "conditions": ["vision_only_A0", "three_tools_A0_A1_A2"],
        "condition_order": "alternate by source pair, 12 images each order",
        "decoding": {"do_sample": False, "preliminary_max_new_tokens": 512,
                     "final_max_new_tokens": 768},
    }
    (args.output_dir / "run-config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (args.output_dir / "prefixes.jsonl").open("x", encoding="utf-8", newline="\n") as prefixes, \
         (args.output_dir / "branches.jsonl").open("x", encoding="utf-8", newline="\n") as branches, \
         (args.output_dir / "vision-baseline.jsonl").open("x", encoding="utf-8", newline="\n") as vision_stream:
        for index, row in enumerate(manifest, 1):
            sample_id = row["sample_id"]
            image_path = Path(row["image_path"])
            image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if image_hash != row["image_sha256"]:
                raise ValueError(f"{sample_id}: image hash changed")
            tool_row = tool_rows[sample_id]
            if tool_row["image_sha256"] != image_hash:
                raise ValueError(f"{sample_id}: tool image hash mismatch")
            observed_families = {item["tool"] for item in tool_row["results"]}
            if observed_families != set(FORMAL_FAMILIES):
                raise ValueError(f"{sample_id}: expected exactly three formal tool families")
            tool_text = format_formal_tool_results(tool_row["results"], refs)
            with Image.open(image_path) as source:
                image = source.convert("RGB")

            def run_vision_baseline() -> None:
                vision_messages = initial_messages(image, None)
                initial = generate(vision_messages, image, 512)
                vision_messages.append({"role": "assistant", "content": initial["raw"]})
                final = generate(build_branch_messages(vision_messages, "A0"), image, 768)
                vision_record = {
                    "sample_id": sample_id, "image_sha256": image_hash,
                    "prompt_sha256": prompt_hash,
                    "preliminary": {**initial, **parsed(initial["raw"], parse_preliminary)},
                    "final": {**final, **parsed(final["raw"], parse_final)},
                }
                vision_stream.write(json.dumps(vision_record, ensure_ascii=False, sort_keys=True) + "\n")
                vision_stream.flush()

            vision_first = ((index - 1) // 2) % 2 == 0
            if vision_first:
                run_vision_baseline()
            messages = initial_messages(image, tool_text)
            preliminary = generate(messages, image, 512)
            messages.append({"role": "assistant", "content": preliminary["raw"]})
            # The image bytes are identified separately; this serializable prefix
            # captures every text message sent to each continuation.
            saved_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "image", "image_sha256": image_hash},
                    {"type": "text", "text": tool_text + "\n\n" + PRELIMINARY_PROMPT},
                ]},
                {"role": "assistant", "content": preliminary["raw"]},
            ]
            prefix_hash = digest(saved_messages)
            prefix_record = {
                "sample_id": sample_id, "image_sha256": image_hash,
                "tool_text_sha256": hashlib.sha256(tool_text.encode("utf-8")).hexdigest(),
                "prefix_sha256": prefix_hash, "messages": saved_messages,
                "preliminary": {**preliminary, **parsed(preliminary["raw"], parse_preliminary)},
            }
            prefixes.write(json.dumps(prefix_record, ensure_ascii=False, sort_keys=True) + "\n")
            prefixes.flush()
            for arm in ACTION_PROMPTS:
                final = generate(build_branch_messages(messages, arm), image, 768)
                branch_record = {
                    "sample_id": sample_id, "arm": arm,
                    "image_sha256": image_hash, "prefix_sha256": prefix_hash,
                    "prompt_sha256": prompt_hash,
                    "final": {**final, **parsed(final["raw"], parse_final)},
                }
                branches.write(json.dumps(branch_record, ensure_ascii=False, sort_keys=True) + "\n")
                branches.flush()
            if not vision_first:
                run_vision_baseline()
            print(f"{index}/{len(manifest)} {sample_id} vision A0 + tools A0/A1/A2", flush=True)


if __name__ == "__main__":
    main()
