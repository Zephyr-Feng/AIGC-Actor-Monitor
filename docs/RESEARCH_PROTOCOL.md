# Research protocol: choosing whether and how to intervene at a fixed checkpoint

> **历史协议（MVP v2，非现行实验指令）。** 本文保留旧版固定检查点 `A0/A1/A2` 干预收益方案的数据契约和实现细节。当前研究方向以[项目主方案](Actor_Monitor_MVP_Protocol.md)为准；旧版完整方案见[历史快照](archive/Actor_Monitor_MVP_Protocol_v2.md)。本文的动作、指标和阶段安排不能直接用于新的 FaithBench / Monitor 实验。

## 1. Scientific question

Given a trajectory prefix `Z` from an evidence-using multimodal Actor, estimate which action maximizes expected incremental utility under the chosen intervention budget:

```text
pi(Z) = argmax_a E[DeltaR(a) - lambda * DeltaC(a) | Z]
```

The immediate question is whether a learned policy can select among **acceptance and multiple label-blind interventions** at one fixed checkpoint, improving held-out correctness and utility while controlling harmful interventions and compute. A distinct claim that multi-arm selection adds value requires improvement over the best validation-selected fixed action under a matched intervention budget. Choosing an earlier versus later checkpoint needs a separate sequential experiment. See the [MVP protocol](Actor_Monitor_MVP_Protocol.md) and the [idea review](IDEA_REVIEW.md).

Before collecting intervention data, audit and screen reusable public forensic experts as defined in the MVP protocol. Freeze one base evidence package for the checkpoint and one complementary evidence package used only by `A2`. Component analysis supports the Actor setup and is not a separate project objective.

## 2. Unit and estimand

An episode is `(sample_id, actor_model, prompt_version, decoding_seed)`; the independent sampling unit for inference is the source-image group, which contains all derived images and seeds. For every reached checkpoint, run the same frozen Actor prefix and then branch into all intervention arms. Record episodes that never reach the checkpoint so system-level claims retain their initial denominator. This paired branching produces an intervention ledger.

For arm `a`, define realized correctness gain and incremental cost:

```text
Delta_a = R(Y(a)) - R(Y(A0))
DeltaC_a = C(a) - C(A0)
DeltaU_a = Delta_a - lambda * DeltaC_a
```

The Monitor predicts `DeltaU_a` from information available before the branch. Post-intervention text, final answers, labels, complementary evidence and arm outcomes are forbidden features.

With stochastic decoding, use several preregistered seeds and treat the seed as part of the unit. Never rerun only failed arms.

## 3. Initial intervention set

All wording is frozen before the confirmation run and must not reveal a target label.

- `A0 accept`：不增加证据或审计步骤，沿当前轨迹完成回答。
- `A1 audit`：不调用新专家；对已有证据的适用范围、校准状态、缺失、冲突和引用一致性进行结构化审计，再让 Actor 完成回答。
- `A2 acquire_complementary_evidence`：调用预先冻结且对所有样本相同的补充证据包，再要求 Actor 比较当前假设与最有力替代假设。

`A1` 是低成本的证据审计，`A2` 是较高成本的固定补充取证。Monitor 不在 A2 内自由选择工具。Actor 的初步判断、证据摘要、干预提示和最终解释统一为中文；`real` / `fake` 只作为机器可读标签。具体规则以 [MVP protocol](Actor_Monitor_MVP_Protocol.md) 为准。排除暗示目标标签的定向提示。

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

Primary comparison: held-out utility and accuracy over the best fixed action at a matched intervention budget. Gain over `A0` is required but insufficient for the main claim.

Required secondary metrics:

- task accuracy and macro-F1;
- intervention rate and arm distribution;
- help rate: baseline wrong, selected arm correct;
- harm rate: baseline correct, selected arm wrong;
- accuracy gain at fixed intervention budgets;
- regret to the per-sample oracle;
- calibration of predicted gain;
- bootstrap confidence interval computed by source unit.

Baselines:

- never intervene;
- always apply `A1` or `A2`;
- validation-selected best fixed arm;
- random policy matched on intervention budget;
- confidence-only heuristic;
- conflict-only heuristic;
- invoke all available experts;
- oracle arm selector as an unattainable upper bound.

## 7. Staged experiment

### Stage D: discovery

Use existing teammate results and legacy trajectories only to define features, arms and failure taxonomies. No headline claims.

### Stage 0: reusable-component audit

Check official repositories, weights, licenses, task fit, dataset overlap, interfaces and single-4090 feasibility. No new component proceeds to model inference before this audit.

### Stage 1: frozen-expert screening

On development data, measure each candidate expert's balanced accuracy, real/fake error direction, calibration, cross-generator behavior, failures, cost and complementarity. Freeze a small base evidence package and a fixed complementary package. This step configures the environment and is not a separate research contribution.

### Stage P: paired pilot

Run a new development sample through `A0`, `A1` and `A2` from the same frozen trajectory. Preregister the minimum practical difference, output-validity requirement, maximum sample size and stopping rule. The pilot asks:

1. Does either intervention correct some baseline errors without excessive harm?
2. Does the best action vary by sample?
3. Is oracle headroom materially above the best fixed arm?

If the best fixed arm captures nearly all oracle utility, interventions have no unique corrections, or output validity fails, a learned Monitor is unnecessary and the project should stop or return to action design.

### Stage C: confirmation

Freeze datasets, arm wording, feature schema, model family and selection threshold before final testing. Train on the training set, select thresholds on validation, and evaluate once on the independent test set. The main comparison is Monitor versus the best fixed action under a matched intervention rate or token budget.

## 8. Ledger formats

Outcome JSONL contains one row per unit and arm:

```json
{"episode_id":"img001|seed0","arm":"A0","correct":true,"abstained":false,"compute_cost":1.0,"metadata":{"source":"coco"}}
{"episode_id":"img001|seed0","arm":"A1","correct":true,"abstained":false,"compute_cost":1.2,"metadata":{"source":"coco"}}
```

Prediction JSONL contains one row per unit. Values are predicted utility gains relative to `A0`:

```json
{"episode_id":"img001|seed0","predicted_gain":{"A1":0.12,"A2":-0.08}}
```

These rows illustrate the field format. Every reached episode in the MVP ledger must contain `A0`, `A1` and `A2` outcomes from the same saved trajectory.
