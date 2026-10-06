# Actor-B0 Baseline Report

## Reproducibility

- Code base commit: `1f84902`; runner and evaluator have local post-commit changes.
- Model revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`
- Prompt SHA-256: `739abe138a0a40b1c21a77308565165bb309a0f45d28f1cf2d0da5354e8da1ea`
- Schema SHA-256: `d0ea87912099ccc058045f266bc904517f8abc209eea54ac707c44e2fc55b9b5`
- Sample manifest SHA-256: `455c011e8146cdccb04696bed3ad1b2c521e5424fd22d4e7edcd38e68cc8a915`
- Tool results SHA-256: `ffda7e8c15885922b3ceb510eae6bfe4eb4a296fdf0dc74aff206987778c34e9`
- Tools: frozen PROBE Evidence-only v1, PatchCraft, SAFE, provenance inspector

## Orchestration metrics

```json
{
  "records": 30,
  "parse_success": 0.9333333333333333,
  "legal_tool_call_rate": 1.0,
  "tool_call_requests": 95,
  "average_tool_calls": 3.1666666666666665,
  "premature_stop_rate": 0.03333333333333333,
  "repeated_tool_call_attempt_rate": 0.0,
  "multi_step_completion_rate": 0.9333333333333333,
  "final_balanced_accuracy": 0.65,
  "global_directional_attribution_steps": 15,
  "global_directional_attribution_step_rate": 0.12,
  "global_directional_attribution_samples": 9,
  "first_tool_counts": {
    "global_forensic_analyzer": 14,
    "provenance_inspector": 16
  },
  "tool_call_counts": {
    "global_forensic_analyzer": 30,
    "local_texture_analyzer": 30,
    "complementary_forensic_analyzer": 15,
    "provenance_inspector": 20
  },
  "format_errors": 10,
  "forced_or_missing_final": 2,
  "by_label": {
    "real": {
      "n": 10,
      "recall": 0.4
    },
    "fake": {
      "n": 20,
      "recall": 0.9
    }
  }
}
```

Premature STOP is a diagnostic flag: no directional tool was called, or unresolved conflicts remained while an unused directional tool was available. Global directional attribution counts only explicit `real`/`fake` source directions; `inconclusive` is non-directional. Free-text interpretations need manual review. These errors do not automatically trigger SFT.

## Decision status

`B0_REVIEW_REQUIRED`

This sanity set is for Actor orchestration decisions only. It is not a confirmation benchmark and must not support headline accuracy claims.
