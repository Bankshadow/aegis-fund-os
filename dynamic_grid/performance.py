"""Performance measurement for the fund-operations track record.

Complements the existing time-weighted return (`fund_v2.time_weighted_return`,
which neutralises the effect of contributions) with the three pieces the MVP plan
still lacked:

* **Money-weighted return** — the internal rate of return actually earned on the
  capital that was invested, dated cash flow by dated cash flow.
* **Strategy attribution** — which strategy produced the P/L, by partitioning the
  ledger and reusing the same tested snapshot engine per strategy.
* **Benchmark comparison** — the excess return over a passive alternative, so a
  positive number is only credited when it beats simply holding.

Every function is pure and fails closed rather than returning a misleading zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from .fund_ops import AppendOnlyLedger, PnLSnapshot

_DAYS_PER_YEAR = 365.0
UNATTRIBUTED = "unattributed"


def _net_present_value(rate: float, flows: Sequence[tuple[datetime, float]],
                       start: datetime) -> float:
    total = 0.0
    for when, amount in flows:
        years = (when - start).total_seconds() / (_DAYS_PER_YEAR * 86400.0)
        total += amount / ((1.0 + rate) ** years)
    return total


def money_weighted_return(flows: Sequence[tuple[datetime, float]],
                          tolerance: float = 1e-9,
                          max_iterations: int = 200) -> float:
    """Annualised money-weighted return (XIRR) of dated cash flows.

    Sign convention is the investor's: capital paid in is negative, capital
    received back is positive, and the closing NAV is included as a final
    positive flow.  Solved by bisection, which needs no derivative and cannot
    diverge the way Newton's method can on irregular flows.

    Fails closed when the inputs cannot define a return: fewer than two flows,
    all flows the same sign (no break-even rate exists), or no sign change
    bracketed within a plausible range.
    """
    dated = sorted(flows, key=lambda item: item[0])
    if len(dated) < 2:
        raise ValueError("money-weighted return needs at least two dated cash flows")
    if not any(amount > 0 for _, amount in dated) or not any(amount < 0 for _, amount in dated):
        raise ValueError("money-weighted return needs both negative and positive cash flows")

    start = dated[0][0]
    low, high = -0.9999, 1.0
    npv_low = _net_present_value(low, dated, start)
    npv_high = _net_present_value(high, dated, start)
    # Expand the upper bound until the root is bracketed (very profitable runs).
    expansions = 0
    while npv_low * npv_high > 0 and expansions < 60:
        high *= 2.0
        npv_high = _net_present_value(high, dated, start)
        expansions += 1
    if npv_low * npv_high > 0:
        raise ValueError("money-weighted return is not bracketed; check the cash flows")

    for _ in range(max_iterations):
        middle = (low + high) / 2.0
        npv_middle = _net_present_value(middle, dated, start)
        if abs(npv_middle) < tolerance:
            return middle
        if npv_low * npv_middle <= 0:
            high = middle
        else:
            low, npv_low = middle, npv_middle
    return (low + high) / 2.0


def attribute_by_strategy(ledger: AppendOnlyLedger,
                          marks: Mapping[str, float]) -> dict[str, PnLSnapshot]:
    """Split the ledger into one P/L snapshot per strategy.

    Events are partitioned by `strategy_id` and each partition is replayed
    through the same `AppendOnlyLedger.snapshot` used for the fund total, so
    inventory is matched within a strategy and attribution can never disagree
    with the engine that produces the headline number.  Events with no strategy
    are grouped under `unattributed` rather than being dropped.
    """
    groups: dict[str, AppendOnlyLedger] = {}
    for event in ledger.events:
        groups.setdefault(event.strategy_id or UNATTRIBUTED, AppendOnlyLedger()).append(event)
    return {name: group.snapshot(marks) for name, group in sorted(groups.items())}


@dataclass(frozen=True)
class BenchmarkComparison:
    portfolio_return: float
    benchmark_return: float
    excess_return: float
    outperformed: bool


def benchmark_comparison(portfolio_return: float, benchmark_start: float,
                         benchmark_end: float) -> BenchmarkComparison:
    """Compare a portfolio return against buying and holding the benchmark.

    A non-positive starting level cannot define a return, so it fails closed
    instead of reporting a fabricated 0% benchmark that would flatter the fund.
    """
    if benchmark_start <= 0:
        raise ValueError("benchmark start level must be positive")
    benchmark = benchmark_end / benchmark_start - 1.0
    excess = portfolio_return - benchmark
    return BenchmarkComparison(portfolio_return, benchmark, excess, excess > 0)
