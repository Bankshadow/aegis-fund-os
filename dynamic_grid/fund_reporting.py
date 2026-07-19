"""Daily-close report and static dashboard artifact for the operations MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Mapping

from .fund_ops import AppendOnlyLedger, LedgerEvent, PlatformBalance
from .reconciliation import ReconciliationResult, ReconciliationStatus


@dataclass(frozen=True)
class DailyCloseReport:
    report_date: str
    generated_at: str
    data_as_of: str | None
    platform: str | None
    account_id: str | None
    status: str
    realized_gross_pnl: float
    unrealized_gross_pnl: float
    trade_fees: float
    carry_pnl: float
    adjustment_pnl: float
    net_pnl: float
    reporting_cash_balance: float
    balances: tuple[dict, ...]
    ledger_events: tuple[dict, ...]
    positions: tuple[dict, ...]
    reconciliation_exceptions: tuple[dict, ...]
    # Appended with defaults so a report JSON written before NAV existed can still
    # be reconstructed (fund_v2_cli filters keys and relies on these defaults).
    nav: float = 0.0
    nav_complete: bool = True
    nav_missing_marks: tuple[str, ...] = ()


def compute_nav(snapshot) -> tuple[float, tuple[str, ...]]:
    """Value the portfolio in the reporting currency, fail-closed on missing marks.

    NAV = reporting cash + Σ spot market value (quantity × mark) + Σ derivative
    mark-to-market (unrealized). An open position with no approved mark
    (``market_price is None``) is never valued at zero silently: its instrument
    is returned in the missing-marks list so the close can be marked provisional.
    """
    nav = snapshot.reporting_cash_balance
    missing: list[str] = []
    for position in snapshot.positions:
        if position.market_price is None:
            missing.append(position.instrument)
            continue
        if position.kind == "derivative":
            nav += position.unrealized_gross_pnl
        else:
            nav += position.quantity * position.market_price
    return nav, tuple(sorted(set(missing)))


def build_daily_close(ledger: AppendOnlyLedger, marks: Mapping[str, float],
                      reconciliation: ReconciliationResult,
                      report_date: date | None = None,
                      data_as_of: datetime | None = None,
                      platform: str | None = None, account_id: str | None = None,
                      balances: tuple[PlatformBalance, ...] = ()) -> DailyCloseReport:
    snapshot = ledger.snapshot(marks)
    nav, nav_missing = compute_nav(snapshot)
    return DailyCloseReport(
        report_date=(report_date or date.today()).isoformat(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_as_of=None if data_as_of is None else data_as_of.isoformat(),
        platform=platform, account_id=account_id,
        status=reconciliation.status.value,
        realized_gross_pnl=snapshot.realized_gross_pnl,
        unrealized_gross_pnl=snapshot.unrealized_gross_pnl,
        trade_fees=snapshot.trade_fees, carry_pnl=snapshot.carry_pnl,
        adjustment_pnl=snapshot.adjustment_pnl, net_pnl=snapshot.net_pnl,
        reporting_cash_balance=snapshot.reporting_cash_balance,
        nav=nav, nav_complete=not nav_missing, nav_missing_marks=nav_missing,
        balances=tuple(asdict(balance) for balance in balances),
        ledger_events=tuple(_event_dict(event) for event in ledger.events),
        positions=tuple(asdict(position) for position in snapshot.positions),
        reconciliation_exceptions=tuple(asdict(item) for item in reconciliation.exceptions))


def write_daily_close(report: DailyCloseReport, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")


def _event_dict(event: LedgerEvent) -> dict:
    data = asdict(event)
    data["occurred_at"] = event.occurred_at.isoformat()
    data["event_type"] = event.event_type.value
    return data
