# Legacy baseline audit

Audit date: 2026-09-25. The server scripts were rerun read-only against the existing trajectories; no new model inference was started.

## What is reusable

- A real image/no-image rollout distinction rather than a prompt-only simulation.
- A structured, append-only trajectory containing tool calls, raw values, calibration metadata and interventions.
- A model-independent tool environment and deterministic collection scripts.
- The teammate repository's frozen protocols, invalid-run bookkeeping and paired-control mindset.

## What is not yet evidence for the Monitor hypothesis

### Actor performance and tool disagreement

| Split | Accuracy | Tool/answer disagreement | Error rate under disagreement |
|---|---:|---:|---:|
| ID | 92/120 = 76.7% | 45/120 = 37.5% | 20/45 = 44.4% |
| OOD | 81/120 = 67.5% | 40/120 = 33.3% | 16/40 = 40.0% |

Disagreement is correlated with error, but it is not a sufficient intervention target: most disagreement cases are still correct. A blanket override would therefore harm many samples.

### Numeric-reading failure

The L1 checker compared claims of the form “value is inside/outside reference interval” with the values and intervals actually shown to the Actor.

| Split | Checkable claims | Consistent | False alarms | Misses | Episodes with at least one false alarm |
|---|---:|---:|---:|---:|---:|
| ID | 228 | 29.4% | 153 | 8 | 71/120 = 59.2% |
| OOD | 294 | 43.2% | 161 | 6 | 87/120 = 72.5% |

This means the current trajectory signal mixes at least two mechanisms: failure to read evidence and failure to weight correctly read evidence. It cannot identify “evidence weighting imbalance” on its own.

### Channel confounding

The source datasets differ strongly in resolution and compression history:

| Source | Typical geometry | Median file size | Median JPEG luma-q |
|---|---|---:|---:|
| ID real / COCO | varied, often 640px | 151.3 KB | 1 |
| ID fake / SDXL | 1024×1024 | 124.1 KB | 8 |
| OOD real / Chameleon | varied, often 500px | 28.5 KB | 8 |
| OOD fake / Chameleon | varied | 64.8 KB | 8 |

Low-level forensic tools can exploit these acquisition-channel differences. Before making a causal claim about Actor oversight, confirmation data must be channel-matched or transformed through a label-independent common pipeline.

## Decision

Treat the old M3 results as hypothesis-generating only. Do not train the final Monitor on them and do not report their accuracy as confirmation of the core claim. The new experiment must collect paired potential outcomes under frozen, label-blind interventions and use only pre-intervention features.

