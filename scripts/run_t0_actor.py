"""Compare image-only and image-plus-tool Chinese Actor outputs on T0.

Discovery check only. Labels stay in the separate manifest and are never sent
to the model. This script runs A0 only; it does not estimate intervention gains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.checkpoint import (  # noqa: E402
    ACTION_PROMPTS,
    FINAL_PROMPT,
    PRELIMINARY_PROMPT,
    build_branch_messages,
    parse_final,
    parse_preliminary,
)
from actor_monitor.p0 import read_jsonl  # noqa: E402
from actor_monitor.tool_text import format_tool_results  # noqa: E402


SYSTEM_PROMPT = (
    "你是一名图像鉴伪分析师。根据实际看到的图像及本次明确提供的取证工具结果，"
    "判断图像是真实拍摄还是 AI 生成。初步判断和最终解释均用中文；"
    "不得编造未观察到的图像细节或未提供的工具读数。"
)


def initial_messages(image: object, tool_text: str | None) -> list[dict]:
    evidence = tool_text or "本次没有提供任何取证工具结果。"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": evidence + "\n\n" + PRELIMINARY_PROMPT},
        ]},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260928)
    args = parser.parse_args()

    manifest = read_jsonl(args.manifest)
    tools = {row["sample_id"]: row for row in read_jsonl(args.tools)}
    refs = json.loads(args.references.read_text(encoding="utf-8"))["ranges"]
    prompt_hash = hashlib.sha256((
        SYSTEM_PROMPT + PRELIMINARY_PROMPT + FINAL_PROMPT + ACTION_PROMPTS["A0"]
    ).encode("utf-8")).hexdigest()

    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("GPU is required for the T0 Actor comparison")
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()

    def generate(messages: list[dict], image: object) -> tuple[str, float]:
        prompt = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(text=[prompt], images=[image], return_tensors="pt")
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        started = time.perf_counter()
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=512, do_sample=False)
        generated = output[0][inputs["input_ids"].shape[1]:]
        text = processor.decode(generated, skip_special_tokens=True)
        return text, round(time.perf_counter() - started, 3)

    conditions = ["vision_only"] * (len(manifest) // 2) + ["with_tools"] * (len(manifest) - len(manifest) // 2)
    random.Random(args.seed).shuffle(conditions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(manifest):
            image_path = Path(row["image_path"])
            if hashlib.sha256(image_path.read_bytes()).hexdigest() != row["image_sha256"]:
                raise ValueError(f"{row['sample_id']}: image hash changed")
            tool_row = tools[row["sample_id"]]
            if tool_row["image_sha256"] != row["image_sha256"]:
                raise ValueError(f"{row['sample_id']}: tool result image hash mismatch")
            tool_text = format_tool_results(tool_row["results"], refs)
            order = [conditions[index], "with_tools" if conditions[index] == "vision_only" else "vision_only"]
            with Image.open(image_path) as source:
                image = source.convert("RGB")
            for condition in order:
                messages = initial_messages(image, tool_text if condition == "with_tools" else None)
                preliminary_raw, preliminary_s = generate(messages, image)
                messages.append({"role": "assistant", "content": preliminary_raw})
                final_raw, final_s = generate(build_branch_messages(messages, "A0"), image)
                record = {
                    "sample_id": row["sample_id"],
                    "image_sha256": row["image_sha256"],
                    "condition": condition,
                    "order": order,
                    "prompt_sha256": prompt_hash,
                    "tool_text_sha256": hashlib.sha256(tool_text.encode("utf-8")).hexdigest() if condition == "with_tools" else None,
                    "preliminary_raw": preliminary_raw,
                    "final_raw": final_raw,
                    "preliminary_s": preliminary_s,
                    "final_s": final_s,
                }
                for name, raw, parser_fn in (
                    ("preliminary", preliminary_raw, parse_preliminary),
                    ("final", final_raw, parse_final),
                ):
                    try:
                        record[name] = vars(parser_fn(raw))
                    except ValueError as exc:
                        record[f"{name}_parse_error"] = str(exc)
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                print(f"{index + 1}/{len(manifest)} {row['sample_id']} {condition}", flush=True)


if __name__ == "__main__":
    main()
