"""Offline evaluation of selective, multi-arm intervention policies."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from math import floor
from typing import Iterable

from .schema import MonitorPrediction, Outcome, UtilitySpec


@dataclass(frozen=True)
class EvaluationReport:
    n_episodes: int
    baseline_arm: str
    baseline_accuracy: float
    policy_accuracy: float
    policy_coverage: float
    intervention_rate: float
    help_rate: float
    harm_rate: float
    baseline_mean_utility: float
    policy_mean_utility: float
    mean_utility_gain: float
    oracle_mean_utility: float
    oracle_headroom: float
    regret_to_oracle: float
    selected_arms: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


def _index_outcomes(
    outcomes: Iterable[Outcome], baseline_arm: str
) -> dict[str, dict[str, Outcome]]:
    indexed: dict[str, dict[str, Outcome]] = {}
    for row in outcomes:
        arms = indexed.setdefault(row.episode_id, {})
        if row.arm in arms:
            raise ValueError(
                f"duplicate outcome for episode={row.episode_id!r}, arm={row.arm!r}"
            )
        arms[row.arm] = row
    missing = sorted(ep for ep, arms in indexed.items() if baseline_arm not in arms)
    if missing:
        raise ValueError(f"baseline arm {baseline_arm!r} missing for {len(missing)} episodes")
    if not indexed:
        raise ValueError("outcome ledger is empty")
    return indexed


def _index_predictions(
    predictions: Iterable[MonitorPrediction],
) -> dict[str, MonitorPrediction]:
    indexed: dict[str, MonitorPrediction] = {}
    for row in predictions:
        if row.episode_id in indexed:
            raise ValueError(f"duplicate prediction for episode={row.episode_id!r}")
        indexed[row.episode_id] = row
    return indexed


def _candidate(
    episode_id: str,
    arms: dict[str, Outcome],
    prediction: MonitorPrediction | None,
    baseline_arm: str,
) -> tuple[str, float] | None:
    if prediction is None:
        return None
    valid = [
        (arm, gain)
        for arm, gain in prediction.predicted_gain.items()
        if arm != baseline_arm and arm in arms
    ]
    if not valid:
        return None
    # Stable tie-break avoids result drift from JSON key order.
    return max(valid, key=lambda item: (item[1], item[0]))


def evaluate_policy(
    outcomes: Iterable[Outcome],
    predictions: Iterable[MonitorPrediction],
    *,
    utility: UtilitySpec | None = None,
    baseline_arm: str = "A0",
    threshold: float = 0.0,
    max_intervention_fraction: float = 1.0,
) -> EvaluationReport:
    """Evaluate a policy using paired observed outcomes for every selected arm.

    The policy takes the highest predicted-gain available arm when its gain is
    strictly above ``threshold``. If a budget is specified, only the globally
    highest-scoring candidates are treated.
    """

    if not 0.0 <= max_intervention_fraction <= 1.0:
        raise ValueError("max_intervention_fraction must be in [0, 1]")

    spec = utility or UtilitySpec()
    ledger = _index_outcomes(outcomes, baseline_arm)
    pred_by_id = _index_predictions(predictions)

    candidates: list[tuple[float, str, str]] = []
    for episode_id, arms in ledger.items():
        candidate = _candidate(
            episode_id, arms, pred_by_id.get(episode_id), baseline_arm
        )
        if candidate is None:
            continue
        arm, gain = candidate
        if gain > threshold:
            candidates.append((gain, episode_id, arm))

    budget = floor(len(ledger) * max_intervention_fraction)
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected = {episode_id: arm for _, episode_id, arm in candidates[:budget]}

    baseline_rows: list[Outcome] = []
    policy_rows: list[Outcome] = []
    oracle_utilities: list[float] = []
    helped = harmed = treated = 0
    arm_counts: Counter[str] = Counter()

    for episode_id in sorted(ledger):
        arms = ledger[episode_id]
        baseline = arms[baseline_arm]
        selected_arm = selected.get(episode_id, baseline_arm)
        chosen = arms[selected_arm]

        baseline_rows.append(baseline)
        policy_rows.append(chosen)
        arm_counts[selected_arm] += 1
        oracle_utilities.append(max(row.utility(spec) for row in arms.values()))

        if selected_arm != baseline_arm:
            treated += 1
            if not baseline.correct and chosen.correct and not chosen.abstained:
                helped += 1
            if baseline.correct and (not chosen.correct or chosen.abstained):
                harmed += 1

    n = len(baseline_rows)
    baseline_utility = sum(row.utility(spec) for row in baseline_rows) / n
    policy_utility = sum(row.utility(spec) for row in policy_rows) / n
    oracle_utility = sum(oracle_utilities) / n

    return EvaluationReport(
        n_episodes=n,
        baseline_arm=baseline_arm,
        baseline_accuracy=sum(row.correct and not row.abstained for row in baseline_rows) / n,
        policy_accuracy=sum(row.correct and not row.abstained for row in policy_rows) / n,
        policy_coverage=sum(not row.abstained for row in policy_rows) / n,
        intervention_rate=treated / n,
        help_rate=helped / treated if treated else 0.0,
        harm_rate=harmed / treated if treated else 0.0,
        baseline_mean_utility=baseline_utility,
        policy_mean_utility=policy_utility,
        mean_utility_gain=policy_utility - baseline_utility,
        oracle_mean_utility=oracle_utility,
        oracle_headroom=oracle_utility - baseline_utility,
        regret_to_oracle=oracle_utility - policy_utility,
        selected_arms=dict(sorted(arm_counts.items())),
    )

