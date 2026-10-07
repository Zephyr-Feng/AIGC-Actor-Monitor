#!/usr/bin/env python3
"""CPU-only Qwen processor check before opening the GPU for STOP replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contract_replay import common_token_prefix, reconstruct_stop_context, verdict_span
from run_b0 import canonical_hash, read_jsonl, sha256, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trajectories", type=Path, required=True)
    parser.add_argument("--original-runtime", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--tool-cards", type=Path, required=True)
    parser.add_argument("--experiment-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import transformers
    from PIL import Image

    runtime = json.loads(args.original_runtime.read_text(encoding="utf-8"))
    if sha256(args.manifest) != runtime["manifest_sha256"]:
        raise ValueError("manifest SHA differs from original")
    prompt = (args.experiment_dir / "prompts/system_prompt.txt").read_text(encoding="utf-8").strip()
    schema = json.loads((args.experiment_dir / "schemas/actor_b_action.schema.json").read_text(encoding="utf-8"))
    generation = json.loads((args.experiment_dir / "config/generation_config.json").read_text(encoding="utf-8"))
    cards = json.loads(args.tool_cards.read_text(encoding="utf-8"))
    if canonical_hash({"system_prompt": prompt, "tool_cards": cards, "schema": schema,
                       "generation": generation}) != runtime["prompt_sha256"]:
        raise ValueError("prompt material differs from original")
    manifest, records = read_jsonl(args.manifest), read_jsonl(args.trajectories)
    if [row["sample_id"] for row in manifest] != [row["sample_id"] for row in records]:
        raise ValueError("original manifest and trajectories differ")
    processor = transformers.AutoProcessor.from_pretrained(args.model_dir)
    first_failure = next(index for index, row in enumerate(records) if not row["parse_valid"])
    processor_check_indices = {0, first_failure}
    largest_boundary_shift = 0
    for number, (item, row) in enumerate(zip(manifest, records), 1):
        messages, raw = reconstruct_stop_context(row, "image-placeholder", prompt, cards, schema,
                                                 lambda path: ("crop-placeholder", path),
                                                 int(generation["max_tool_calls"]))
        _, start, _ = verdict_span(raw)
        prefix = raw[:start]
        prefix_ids = processor.tokenizer(prefix, add_special_tokens=False)["input_ids"]
        real_ids = processor.tokenizer(prefix + '"real"', add_special_tokens=False)["input_ids"]
        fake_ids = processor.tokenizer(prefix + '"fake"', add_special_tokens=False)["input_ids"]
        shared = common_token_prefix(real_ids, fake_ids)
        shift = len(prefix_ids) - shared
        if shared < len(prefix_ids) - 4 or shared == 0:
            raise ValueError(f"candidate tokenizations diverge before verdict at row {number}")
        if len(real_ids) <= shared or len(fake_ids) <= shared:
            raise ValueError(f"candidate tokenizations have no distinct suffix at row {number}")
        largest_boundary_shift = max(largest_boundary_shift, shift)
        if number - 1 in processor_check_indices:
            image_path = args.image_root / item["relative_path"]
            if sha256(image_path) != item["sha256"]:
                raise ValueError("frozen image SHA mismatch")
            with Image.open(image_path) as source:
                image = source.convert("RGB")

            def load_crop(relative: str):
                with Image.open(args.evidence_dir / relative) as source:
                    return source.convert("RGB")

            full_messages, _ = reconstruct_stop_context(row, image, prompt, cards, schema,
                                                        load_crop, int(generation["max_tool_calls"]))
            rendered = processor.apply_chat_template(full_messages, tokenize=False,
                                                     add_generation_prompt=True)
            images = [part["image"] for message in full_messages if isinstance(message["content"], list)
                      for part in message["content"] if part.get("type") == "image"]
            original = processor(text=[rendered], images=images, return_tensors="pt")
            expected = row["steps"][-1]["attempts"][-1]
            grids = int(original["image_grid_thw"].shape[0]) if "image_grid_thw" in original else 0
            if original["input_ids"].shape[1] != expected["input_tokens"] or grids != expected["image_grids"]:
                raise ValueError(f"processor context differs at row {number}")
            print(f"processor context matches original at row {number}", flush=True)
        if number % 10 == 0:
            print(f"tokenizer preflight {number}/{len(records)}", flush=True)
    write_json(args.output, {"records": len(records), "processor_contexts_checked": len(processor_check_indices),
                             "checked_context_tokens_and_grids_match": True,
                             "candidate_divergence_is_local_to_verdict": True,
                             "max_field_boundary_retokenized_tokens": largest_boundary_shift,
                             "model_revision": runtime["model_revision"],
                             "processor_transformers": transformers.__version__,
                             "trajectories_sha256": sha256(args.trajectories)})


if __name__ == "__main__":
    main()
