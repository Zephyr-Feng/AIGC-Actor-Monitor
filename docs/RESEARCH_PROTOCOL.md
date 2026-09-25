# Research protocol: predicting when and how to intervene

## 1. Scientific question

Given a trajectory prefix `Z` from an evidence-using multimodal Actor, estimate which action maximizes expected utility:

```text
pi(Z) = argmax_a E[U(Y(a)) | Z]
```

The publishable claim is not that a Monitor detects errors. It is that a learned policy selects among **no intervention and multiple label-blind interventions**, improving held-out utility while controlling harmful interventions and compute.

## 2. Unit and estimand

The unit is `(sample_id, actor_model, prompt_version, decoding_seed)`. For every unit, run the same frozen Actor prefix and then branch into all intervention arms. This paired branching produces an intervention ledger.

For arm `a`, define realized gain:

```text
Delta_a = U(Y(a)) - U(Y(A0))
```

The Monitor predicts `Delta_a` from information available before the branch. Post-intervention text, final answers, labels and arm outcomes are forbidden features.

With stochastic decoding, use several preregistered seeds and treat the seed as part of the unit. Never rerun only failed arms.

## 3. Initial intervention set

All wording is frozen before the confirmation run and must not reveal a target label.

- `A0 none`: continue without intervention.
- `A1 factual_verify`: ask the Actor to verify every quoted value against its displayed reference interval and correct only factual mismatches.
- `A2 conflict_reconcile`: state only that available evidence sources may disagree; require an explicit reliability comparison before deciding.
- `A3 symmetric_countercase`: require the strongest case for both `real` and `fake`, then a final decision based on which case is better supported.
- `A4 defer`: abstain or route to a fixed external decision rule. Its cost is included in utility.

`A1` targets evidence reading, `A2` targets weighting, and `A3` targets premature commitment. Separating them makes “how to intervene” identifiable. Directional prompts such as “reconsider whether this is fake” are excluded because they confound intervention quality with label leakage.

## 4. Pre-intervention features

Start with a small, auditable feature set:

- Actor confidence and margin, if available without an extra answer-generation step;
- tool-family scores, missingness and cross-tool disagreement;
- tool-versus-current-hypothesis disagreement;
- mechanically checkable citation/range consistency;
- number and order of tool calls, token count and latency;
- prompt/model/tool versions.

Hidden-state probes are a later ablation, not a dependency of the core result. The first result should remain reproducible from logged trajectories alone.

## 5. Data controls

- Match real/fake images on resolution, codec, quality and resize history, or pass both labels through the same randomized but label-independent channel pipeline.
- Split by source image and generator family, not by derived file, to prevent near-duplicate leakage.
- Keep a generator-OOD and a dataset-OOD test set untouched until the policy and thresholds are frozen.
- Report a direct detector baseline. If replacing the Actor with the detector dominates the Monitor, the claimed system value is weak even if uplift over the Actor is positive.

## 6. Evaluation

Primary metric: mean held-out utility gain over `A0`.

Required secondary metrics:

- task accuracy and non-abstain coverage;
- intervention rate and arm distribution;
- help rate: baseline wrong, selected arm correct;
- harm rate: baseline correct, selected arm wrong;
- utility gain at fixed intervention budgets;
- regret to the per-sample oracle;
- worst-group gain across source/generator groups;
- calibration of predicted gain;
- bootstrap confidence interval computed by source unit.

Baselines:

- never intervene;
- always apply each arm;
- random policy matched on intervention budget;
- confidence-only and disagreement-only heuristics;
- direct detector / fixed ensemble;
- oracle arm selector as an unattainable upper bound.

## 7. Staged experiment

### Stage D: discovery

Use existing teammate results and legacy trajectories only to define features, arms and failure taxonomies. No headline claims.

### Stage P: paired pilot

Run a small channel-matched sample through all frozen arms. The pilot asks only:

1. Does any arm have non-zero help without catastrophic harm?
2. Is there treatment heterogeneity—that is, does the best arm vary by sample?
3. Is oracle headroom materially above the best fixed arm?

If the best fixed arm captures nearly all oracle gain, a learned Monitor is unnecessary and the project should stop or be reframed.

### Stage C: confirmation

Before looking at the held-out outcomes, freeze datasets, arm wording, utility weights, feature schema, model family, selection threshold and statistical tests. Train on discovery, select on validation, and evaluate once on ID and two OOD axes.

## 8. Ledger formats

Outcome JSONL contains one row per unit and arm:

```json
{"episode_id":"img001|seed0","arm":"A0","correct":true,"abstained":false,"compute_cost":1.0,"metadata":{"source":"coco"}}
{"episode_id":"img001|seed0","arm":"A1","correct":true,"abstained":false,"compute_cost":1.2,"metadata":{"source":"coco"}}
```

Prediction JSONL contains one row per unit. Values are predicted utility gains relative to `A0`:

```json
{"episode_id":"img001|seed0","predicted_gain":{"A1":0.12,"A2":-0.08,"A3":0.04,"A4":-0.20}}
```

Every episode must contain `A0`; predictions may omit arms that were not available at decision time.

