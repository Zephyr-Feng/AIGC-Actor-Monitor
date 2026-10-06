# Actor-0: Prompt-only autonomous image-forensics agent

Status: **complete (2026-10-03)**. Frozen prompt inference, per-image trajectory export, baselines, behavior analysis, qualitative review, and `REPORT.md` are complete.

This experiment compares an image-only MLLM, the fixed PROBE operating point, one-shot all-tool input, and an autonomous prompt-only Actor. It does not train a model, tune a threshold, or use evaluation labels in prompts. It stops after the Actor-0 report; no SFT, GRPO, or Monitor work is included.

## Final result

- Independent evaluation: 300 images / 100 source groups, with image-only accuracy 0.6067, PROBE-only 0.9867, forced-all 0.9133, and Actor-0 autonomous 0.9500. Actor balanced accuracy was 0.9400; it used 2.58 tools per image on average.
- Actor outputs parsed for 300/300 images. The main behavior risks were 112/300 global-only stops and unresolved conflicts in all 128 conflict cases. Detailed A–H answers, decisions, cost, failures, and limitations are in [REPORT.md](REPORT.md).
- Prompt v3 is frozen at SHA-256 `a1a9dc690cec5cbc7d15eef711feffc9d7e52bf184cd707a30239d1cc429926d`. Evaluation resumed after one SSH-session interruption with the identical config and output root; final hashes were checked against the remote manifests.
- Main outputs: [analysis](analysis/), [run archive and raw scores](../../runs/actor0-bfree-20261002/), and [trajectory review bundle](analysis/qualitative_audit_review/).

## Frozen data

- Development: 60 previously unused B-Free source groups / 180 original PNGs.
- Evaluation: 100 different previously unused source groups / 300 original PNGs.
- Selection seed: `20261002`; each split is stratified to 70% landscape and 30% portrait groups.
- The source-group sets are disjoint from 530 groups in prior manifests and from each other; 310 groups remain unused.
- Archive checksums, all prior-manifest hashes, group IDs, and each original PNG hash are recorded in `data/selection_summary.json` and the JSONL manifests.
- B-Free and RAISE notices are retained under `data/licenses/`; follow their informational/nonprofit and scientific non-commercial conditions.
- Image bytes are not transformed. Labels remain in manifests and are attached to result records only after model/tool outputs have been produced.

The images are in the ignored run-data directory `runs/actor0-bfree-20261002/data/`, not duplicated inside this tracked experiment directory.

The ignored run archive also holds the per-image Provenance raw JSON, unified CSV, CPU scan log, model download manifest, local processor/config/index check, and per-shard SHA-256 list under `runs/actor0-bfree-20261002/`. A redacted transfer note and portable verification summaries are copied into this experiment's `logs/` directory; the model weights remain in the remote pinned Hub snapshot and are not copied into the repository.

## Model and protocol

The planned backbone is the official [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) checkpoint, loaded with the Transformers Qwen3-VL API. Model revision, tokenizer revision, framework versions, dtype, and greedy decoding settings are recorded by the runner. A fallback backbone may be used only if the report records why Qwen3-VL could not run.

The actor sees only four semantic tool names, with no detector brands or benchmark accuracy:

| Actor-visible tool | Internal implementation |
|---|---|
| `global_forensic_analyzer` | PROBE-DINOv2 |
| `local_texture_analyzer` | PatchCraft |
| `complementary_forensic_analyzer` | SAFE |
| `provenance_inspector` | c2patool + ExifTool |

Each tool is callable once per image; the actor has up to four tool calls and six decision steps, with no fixed order or minimum number of tools. Tool outputs are evidence, not ground truth. Absence of provenance is `inconclusive`. `strength` for learned scores is a fixed descriptive raw-score extremity bin, not calibrated confidence.

Development use is limited to API, format, tool-loop, and prompt-clarity debugging. The frozen prompt is written only after >=95% of development trajectories and actor turns pass the parse gate. The evaluation prompt hash must match that freeze file.

## Output layout

- `config/`: model/generation settings, semantic Tool Cards, prompts, and frozen prompt SHA-256.
- `data/`: frozen manifests, selection summary, and retained license notices.
- `trajectories/`: per-image autonomous JSON and `trajectories.jsonl`.
- `analysis/`: baseline and Actor metrics, behavior diagnostics, sequence table, conflict and PROBE-failure records, Monitor-candidate rows, and a fixed 50-case qualitative audit sheet.
- `logs/`: transfer, environment, scoring, model-download, and inference logs.
- `REPORT.md`: final answers to the experiment questions, limitations, and KEEP / CONDITIONAL / DROP decisions.

## Reproduction scripts

1. `scripts/prepare_actor0_data.py` freezes disjoint source groups and exports byte-identical original PNGs.
2. Run the official detector pipelines for PROBE, PatchCraft, and SAFE plus the existing c2patool/ExifTool inspector on both manifests. Preserve each raw score and tool log.
3. `scripts/export_tool_observations.py` aligns outputs by `sample_id` and image SHA-256, hides implementation names from actor input, and writes semantic tool JSONL.
4. `scripts/run_actor0.py` runs the development autonomous loop. If and only if the parse gate passes, freeze the prompt with `scripts/freeze_actor0_prompt.py`.
5. Run the frozen evaluation once with `image_only`, `forced_all`, and `autonomous` conditions. B1 is the frozen direct PROBE output.
6. `scripts/analyze_actor0.py` computes required final, tool-use, sequence, conflict, interpretation, metadata-misuse, oversearch, premature-stop, and PROBE-failure analyses.

Evaluation labels must never be included in a prompt or tool input. Do not change prompts, Tool Cards, generation settings, thresholds, or preprocessing after the evaluation begins.
