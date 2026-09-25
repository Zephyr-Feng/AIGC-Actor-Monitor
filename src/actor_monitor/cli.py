"""Command-line entry point for intervention-ledger evaluation."""

from __future__ import annotations

import argparse
import json

from .evaluation import evaluate_policy
from .io import read_outcomes, read_predictions
from .schema import UtilitySpec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--baseline-arm", default="A0")
    parser.add_argument("--threshold", type=float, default=0.0)
    parser.add_argument("--max-intervention-fraction", type=float, default=1.0)
    parser.add_argument("--correct-reward", type=float, default=1.0)
    parser.add_argument("--error-cost", type=float, default=1.0)
    parser.add_argument("--abstain-cost", type=float, default=0.25)
    parser.add_argument("--compute-cost-weight", type=float, default=0.0)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    report = evaluate_policy(
        read_outcomes(args.ledger),
        read_predictions(args.predictions),
        baseline_arm=args.baseline_arm,
        threshold=args.threshold,
        max_intervention_fraction=args.max_intervention_fraction,
        utility=UtilitySpec(
            correct_reward=args.correct_reward,
            error_cost=args.error_cost,
            abstain_cost=args.abstain_cost,
            compute_cost_weight=args.compute_cost_weight,
        ),
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

