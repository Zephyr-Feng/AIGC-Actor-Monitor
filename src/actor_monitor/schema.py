"""Serializable records used by the intervention ledger and evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UtilitySpec:
    """Utility weights fixed before policy selection."""

    correct_reward: float = 1.0
    error_cost: float = 1.0
    abstain_cost: float = 0.25
    compute_cost_weight: float = 0.0


@dataclass(frozen=True)
class Outcome:
    """Observed outcome for one paired experimental unit under one arm."""

    episode_id: str
    arm: str
    correct: bool
    abstained: bool = False
    compute_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Outcome":
        return cls(
            episode_id=str(raw["episode_id"]),
            arm=str(raw["arm"]),
            correct=bool(raw["correct"]),
            abstained=bool(raw.get("abstained", False)),
            compute_cost=float(raw.get("compute_cost", 0.0)),
            metadata=dict(raw.get("metadata") or {}),
        )

    def utility(self, spec: UtilitySpec) -> float:
        if self.abstained:
            task_utility = -spec.abstain_cost
        elif self.correct:
            task_utility = spec.correct_reward
        else:
            task_utility = -spec.error_cost
        return task_utility - spec.compute_cost_weight * self.compute_cost


@dataclass(frozen=True)
class MonitorPrediction:
    """Predicted arm-specific utility gains relative to the baseline arm."""

    episode_id: str
    predicted_gain: dict[str, float]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MonitorPrediction":
        gains = {str(k): float(v) for k, v in raw["predicted_gain"].items()}
        return cls(episode_id=str(raw["episode_id"]), predicted_gain=gains)

