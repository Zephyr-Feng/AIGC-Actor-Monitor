"""One-image Qwen smoke test for Chinese checkpoint and three continuations.

This is a prompt/interface check without forensic tools or ground-truth labels.
It is not an experiment result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.checkpoint import (  # noqa: E402
    ACTION_PROMPTS,
    PRELIMINARY_PROMPT,
    build_branch_messages,
    parse_final,
    parse_preliminary,
)


SYSTEM_PROMPT = (
    "你是一名图像鉴伪分析师。根据实际看到的图像和已经取得的工具结果，"
    "判断图像是真实拍摄还是 AI 生成。分析和解释使用中文；"
    "不得编造未观察到的图像细节或工具读数。本次没有提供任何取证工具结果。"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    import transformers
    from PIL import Image

    if not torch.cuda.is_available():
        raise RuntimeError("GPU is required for this Qwen smoke test")

    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    model = transformers.Qwen3VLForConditionalGeneration.from_pretrained(
        args.model_dir, dtype=torch.bfloat16, device_map="cuda"
    ).eval()
    with Image.open(args.image) as source:
        image = source.convert("RGB")

    def generate(messages: list[dict]) -> str:
        prompt = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(text=[prompt], images=[image], return_tensors="pt")
        inputs = {key: value.to("cuda") for key, value in inputs.items()}
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=512, do_sample=False)
        generated = output[0][inputs["input_ids"].shape[1]:]
        return processor.decode(generated, skip_special_tokens=True)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "请观察这张待鉴别图像。\n\n" + PRELIMINARY_PROMPT},
        ]},
    ]
    preliminary_text = generate(messages)
    report = {
        "kind": "prompt_smoke_without_tools_or_labels",
        "image_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest(),
        "model_dir": str(args.model_dir),
        "preliminary_raw": preliminary_text,
        "branches": {},
    }
    try:
        report["preliminary"] = vars(parse_preliminary(preliminary_text))
    except ValueError as exc:
        report["preliminary_parse_error"] = str(exc)
    messages.append({"role": "assistant", "content": preliminary_text})

    for arm in ACTION_PROMPTS:
        final_text = generate(build_branch_messages(messages, arm))
        branch = {"raw": final_text}
        try:
            branch["parsed"] = vars(parse_final(final_text))
        except ValueError as exc:
            branch["parse_error"] = str(exc)
        report["branches"][arm] = branch

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved prompt smoke: {args.output}")


if __name__ == "__main__":
    main()
