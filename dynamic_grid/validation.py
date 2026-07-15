"""Combinatorial purged screening for strategy candidates.

This is a validation gate, not an optimizer. The failure rate is empirical and
must not be mislabelled as a formal probability-of-overfitting estimate.
"""

from dataclasses import dataclass
from itertools import combinations
from statistics import median
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class ValidationFold:
    test_groups: tuple[int, ...]
    selected: str
    train_score: float
    test_score: float
    test_rank: int
    candidate_count: int


@dataclass(frozen=True)
class ValidationReport:
    folds: tuple[ValidationFold, ...]
    median_test_score: float
    selection_failure_rate: float


class ValidationGate:
    """Human-readable promotion gate for a pre-approved candidate set."""

    def __init__(self, min_folds: int = 3, min_median_score: float = 0.0,
                 max_selection_failure_rate: float = 0.50):
        self.min_folds = min_folds
        self.min_median_score = min_median_score
        self.max_selection_failure_rate = max_selection_failure_rate

    def passes(self, report: ValidationReport) -> bool:
        return (len(report.folds) >= self.min_folds
                and report.median_test_score >= self.min_median_score
                and report.selection_failure_rate <= self.max_selection_failure_rate)


def _score(result) -> float:
    return float(result.total_return - 2.0 * result.max_drawdown)


def combinatorial_purged_screen(
        ohlc: np.ndarray,
        candidates: dict[str, Callable[[np.ndarray], object]],
        *, n_groups: int = 6, n_test_groups: int = 2,
        purge_groups: int = 1) -> ValidationReport:
    """Screen candidates across combinatorial train/test blocks.

    Each callable receives a contiguous OHLC block and returns an object with
    ``total_return`` and ``max_drawdown`` (e.g. ``BacktestResult``).
    """
    if len(candidates) < 2:
        raise ValueError("screening needs at least two candidates")
    if not 2 <= n_test_groups < n_groups:
        raise ValueError("n_test_groups must be in [2, n_groups)")
    groups = [group for group in np.array_split(ohlc, n_groups) if len(group)]
    if len(groups) != n_groups:
        raise ValueError("not enough bars for the requested number of groups")
    folds = []
    for test_groups in combinations(range(n_groups), n_test_groups):
        purged = set(test_groups)
        for group in test_groups:
            purged.update(range(max(0, group - purge_groups),
                                min(n_groups, group + purge_groups + 1)))
        train_groups = [i for i in range(n_groups) if i not in purged]
        if not train_groups:
            continue
        train_scores, test_scores = {}, {}
        for name, evaluate in candidates.items():
            train_scores[name] = float(np.mean([_score(evaluate(groups[i]))
                                                for i in train_groups]))
            test_scores[name] = float(np.mean([_score(evaluate(groups[i]))
                                               for i in test_groups]))
        selected = max(train_scores, key=train_scores.get)
        ranked = sorted(test_scores, key=test_scores.get, reverse=True)
        folds.append(ValidationFold(
            test_groups=test_groups, selected=selected,
            train_score=train_scores[selected], test_score=test_scores[selected],
            test_rank=ranked.index(selected) + 1, candidate_count=len(candidates),
        ))
    if not folds:
        raise ValueError("purge settings left no valid validation folds")
    failure_rate = sum(f.test_rank > (f.candidate_count + 1) / 2 for f in folds) / len(folds)
    return ValidationReport(
        folds=tuple(folds),
        median_test_score=float(median(f.test_score for f in folds)),
        selection_failure_rate=float(failure_rate),
    )
