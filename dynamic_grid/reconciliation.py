"""Daily reconciliation between the internal ledger and a platform snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from .fund_ops import AppendOnlyLedger, PlatformBalance, PlatformPosition


class ReconciliationStatus(str, Enum):
    CLEAN = "clean"
    PROVISIONAL = "provisional"


@dataclass(frozen=True)
class ReconciliationException:
    asset: str
    expected: float
    observed: float
    difference: float
    reason: str


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    exceptions: tuple[ReconciliationException, ...]


def reconcile_positions(ledger: AppendOnlyLedger, balances: Sequence[PlatformBalance],
                        marks: Mapping[str, float], tolerance: float = 1e-8,
                        reporting_asset: str | None = None,
                        derivative_positions: Sequence[PlatformPosition] = ()) -> ReconciliationResult:
    """Compare spot inventory and, optionally, reporting-currency cash."""
    observed = {balance.asset: balance.total for balance in balances}
    expected: dict[str, float] = {}
    snapshot = ledger.snapshot(marks)
    for position in snapshot.positions:
        if position.kind == "derivative":
            continue
        asset = position.instrument.split("/", 1)[0]
        expected[asset] = expected.get(asset, 0.0) + position.quantity
    if reporting_asset is not None:
        expected[reporting_asset] = snapshot.reporting_cash_balance
    exceptions = []
    for asset in sorted(set(expected) | set(observed)):
        difference = observed.get(asset, 0.0) - expected.get(asset, 0.0)
        if abs(difference) > tolerance:
            exceptions.append(ReconciliationException(
                asset, expected.get(asset, 0.0), observed.get(asset, 0.0), difference,
                "balance differs from ledger inventory or reporting cash"))
    internal_derivatives = {p.instrument: p.quantity for p in snapshot.positions if p.kind == "derivative"}
    remote_derivatives = {p.instrument: p.quantity for p in derivative_positions}
    for instrument in sorted(set(internal_derivatives) | set(remote_derivatives)):
        difference = remote_derivatives.get(instrument, 0.0) - internal_derivatives.get(instrument, 0.0)
        if abs(difference) > tolerance:
            exceptions.append(ReconciliationException(
                instrument, internal_derivatives.get(instrument, 0.0),
                remote_derivatives.get(instrument, 0.0), difference,
                "derivative position differs from ledger executions"))
    status = ReconciliationStatus.CLEAN if not exceptions else ReconciliationStatus.PROVISIONAL
    return ReconciliationResult(status, tuple(exceptions))
