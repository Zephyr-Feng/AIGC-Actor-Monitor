"""Small JSONL readers kept dependency-free for auditable evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, TypeVar

from .schema import MonitorPrediction, Outcome

T = TypeVar("T")


def _read_jsonl(path: str | Path, parser: Callable[[dict], T]) -> list[T]:
    records: list[T] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                records.append(parser(raw))
            except Exception as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return records


def read_outcomes(path: str | Path) -> list[Outcome]:
    return _read_jsonl(path, Outcome.from_dict)


def read_predictions(path: str | Path) -> list[MonitorPrediction]:
    return _read_jsonl(path, MonitorPrediction.from_dict)

