# Actor-B Orchestration Report

## Reproducibility

- Runtime metadata and exact code revisions are recorded with this run; use the freeze manifest for a frozen Actor release.
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
  "accepted_steps": 125,
  "total_steps": 125,
  "parse_success": 1.0,
  "legal_tool_call_rate": 1.0,
  "tool_call_requests": 95,
  "average_tool_calls": 3.1666666666666665,
  "premature_stop_rate": 0.06666666666666667,
  "repeated_tool_call_attempt_rate": 0.0,
  "multi_step_completion_rate": 1.0,
  "final_balanced_accuracy": 0.725,
  "global_directional_attribution_steps": 16,
  "global_directional_attribution_step_rate": 0.128,
  "global_directional_attribution_samples": 10,
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
  "tool_call_distribution": {
    "4": 13,
    "3": 9,
    "2": 8
  },
  "tool_sequence_distribution": {
    "global_forensic_analyzer > local_texture_analyzer > complementary_forensic_analyzer > provenance_inspector": 3,
    "global_forensic_analyzer > local_texture_analyzer > complementary_forensic_analyzer": 2,
    "provenance_inspector > local_texture_analyzer > global_forensic_analyzer": 7,
    "provenance_inspector > local_texture_analyzer > global_forensic_analyzer > complementary_forensic_analyzer": 7,
    "provenance_inspector > global_forensic_analyzer > local_texture_analyzer > complementary_forensic_analyzer": 2,
    "global_forensic_analyzer > local_texture_analyzer > provenance_inspector > complementary_forensic_analyzer": 1,
    "global_forensic_analyzer > local_texture_analyzer": 8
  },
  "format_errors": 8,
  "forced_or_missing_final": 0,
  "by_label": {
    "real": {
      "n": 10,
      "recall": 0.5
    },
    "fake": {
      "n": 20,
      "recall": 0.95
    }
  }
}
```

Premature STOP is a diagnostic flag: no directional tool was called, or unresolved conflicts remained while an unused directional tool was available. Global directional attribution counts only explicit `real`/`fake` source directions; `inconclusive` is non-directional. Free-text interpretations need manual review. These errors do not automatically trigger SFT.

## Decision status

`B0_REVIEW_REQUIRED`

This set is for Actor orchestration decisions only. It is not an accuracy benchmark and must not support headline accuracy claims.
