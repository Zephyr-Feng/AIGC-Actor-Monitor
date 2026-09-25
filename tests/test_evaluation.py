from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.evaluation import evaluate_policy
from actor_monitor.schema import MonitorPrediction, Outcome, UtilitySpec


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        # A1 helps e1, harms e2, and changes nothing for e3/e4.
        self.outcomes = [
            Outcome("e1", "A0", False), Outcome("e1", "A1", True),
            Outcome("e2", "A0", True), Outcome("e2", "A1", False),
            Outcome("e3", "A0", True), Outcome("e3", "A1", True),
            Outcome("e4", "A0", False), Outcome("e4", "A1", False),
        ]

    def test_selective_policy_captures_help_without_harm(self) -> None:
        predictions = [
            MonitorPrediction("e1", {"A1": 0.9}),
            MonitorPrediction("e2", {"A1": -0.8}),
            MonitorPrediction("e3", {"A1": -0.1}),
            MonitorPrediction("e4", {"A1": -0.2}),
        ]
        report = evaluate_policy(self.outcomes, predictions)
        self.assertEqual(report.selected_arms, {"A0": 3, "A1": 1})
        self.assertEqual(report.baseline_accuracy, 0.5)
        self.assertEqual(report.policy_accuracy, 0.75)
        self.assertEqual(report.help_rate, 1.0)
        self.assertEqual(report.harm_rate, 0.0)
        self.assertEqual(report.mean_utility_gain, 0.5)

    def test_budget_keeps_highest_predicted_gain(self) -> None:
        predictions = [
            MonitorPrediction("e1", {"A1": 0.9}),
            MonitorPrediction("e2", {"A1": 0.8}),
            MonitorPrediction("e3", {"A1": 0.7}),
            MonitorPrediction("e4", {"A1": 0.6}),
        ]
        report = evaluate_policy(
            self.outcomes, predictions, max_intervention_fraction=0.25
        )
        self.assertEqual(report.selected_arms, {"A0": 3, "A1": 1})
        self.assertEqual(report.policy_accuracy, 0.75)

    def test_abstention_and_compute_cost_enter_utility(self) -> None:
        outcomes = [
            Outcome("e1", "A0", False, compute_cost=1.0),
            Outcome("e1", "A4", False, abstained=True, compute_cost=2.0),
        ]
        predictions = [MonitorPrediction("e1", {"A4": 0.1})]
        report = evaluate_policy(
            outcomes,
            predictions,
            utility=UtilitySpec(
                error_cost=1.0, abstain_cost=0.25, compute_cost_weight=0.1
            ),
        )
        self.assertAlmostEqual(report.baseline_mean_utility, -1.1)
        self.assertAlmostEqual(report.policy_mean_utility, -0.45)
        self.assertAlmostEqual(report.mean_utility_gain, 0.65)

    def test_duplicate_arm_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate outcome"):
            evaluate_policy(
                [Outcome("e1", "A0", True), Outcome("e1", "A0", False)], []
            )


if __name__ == "__main__":
    unittest.main()

