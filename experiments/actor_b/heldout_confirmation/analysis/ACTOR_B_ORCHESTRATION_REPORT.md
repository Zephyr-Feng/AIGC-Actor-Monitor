# Actor-B Orchestration Report

## Reproducibility

- Runtime metadata and exact code revisions are recorded with this run; use the freeze manifest for a frozen Actor release.
- Model revision: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`
- Prompt SHA-256: `739abe138a0a40b1c21a77308565165bb309a0f45d28f1cf2d0da5354e8da1ea`
- Schema SHA-256: `d0ea87912099ccc058045f266bc904517f8abc209eea54ac707c44e2fc55b9b5`
- Sample manifest SHA-256: `fe53bd24557f04705b6a26788e7a57c3f3ab5cc8981029b49ba952eb6ab80531`
- Tool results SHA-256: `94e0b02b7d582057cac32ea8c416f348c9b60ee3854594216c3c7d562a51b919`
- Tools: frozen PROBE Evidence-only v1, PatchCraft, SAFE, provenance inspector

## Orchestration metrics

```json
{
  "records": 60,
  "accepted_steps": 244,
  "total_steps": 249,
  "parse_success": 0.9166666666666666,
  "legal_tool_call_rate": 1.0,
  "tool_call_requests": 189,
  "average_tool_calls": 3.15,
  "premature_stop_rate": 0.08333333333333333,
  "repeated_tool_call_attempt_rate": 0.0,
  "multi_step_completion_rate": 0.9166666666666666,
  "final_balanced_accuracy": 0.6625,
  "global_directional_attribution_steps": 28,
  "global_directional_attribution_step_rate": 0.11475409836065574,
  "global_directional_attribution_samples": 15,
  "first_tool_counts": {
    "global_forensic_analyzer": 28,
    "provenance_inspector": 32
  },
  "tool_call_counts": {
    "global_forensic_analyzer": 60,
    "local_texture_analyzer": 60,
    "provenance_inspector": 45,
    "complementary_forensic_analyzer": 24
  },
  "tool_call_distribution": {
    "2": 12,
    "4": 21,
    "3": 27
  },
  "tool_sequence_distribution": {
    "global_forensic_analyzer > local_texture_analyzer": 12,
    "provenance_inspector > local_texture_analyzer > global_forensic_analyzer > complementary_forensic_analyzer": 13,
    "provenance_inspector > local_texture_analyzer > global_forensic_analyzer": 15,
    "global_forensic_analyzer > local_texture_analyzer > complementary_forensic_analyzer": 3,
    "global_forensic_analyzer > local_texture_analyzer > complementary_forensic_analyzer > provenance_inspector": 5,
    "global_forensic_analyzer > local_texture_analyzer > provenance_inspector": 7,
    "provenance_inspector > global_forensic_analyzer > local_texture_analyzer": 2,
    "provenance_inspector > global_forensic_analyzer > local_texture_analyzer > complementary_forensic_analyzer": 2,
    "global_forensic_analyzer > local_texture_analyzer > provenance_inspector > complementary_forensic_analyzer": 1
  },
  "format_errors": 26,
  "forced_or_missing_final": 5,
  "by_label": {
    "real": {
      "n": 20,
      "recall": 0.5
    },
    "fake": {
      "n": 40,
      "recall": 0.825
    }
  }
}
```

Premature STOP is a diagnostic flag: no directional tool was called, or unresolved conflicts remained while an unused directional tool was available. Global directional attribution counts only explicit `real`/`fake` source directions; `inconclusive` is non-directional. Free-text interpretations need manual review. These errors do not automatically trigger SFT.

## Decision status

`B0_REVIEW_REQUIRED`

This set is for Actor orchestration decisions only. It is not an accuracy benchmark and must not support headline accuracy claims.
