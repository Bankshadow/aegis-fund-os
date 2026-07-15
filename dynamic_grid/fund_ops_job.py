"""One safe daily-close workflow for the read-only fund-operations MVP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

from .fund_ops import ReadOnlyPlatformConnector
from .fund_reporting import DailyCloseReport, build_daily_close, write_daily_close
from .fund_storage import SQLiteLedgerStore
from .fund_v2_store import FundV2Store
from .reconciliation import ReconciliationResult, reconcile_positions


@dataclass(frozen=True)
class DailyCloseRun:
    events_inserted: int
    reconciliation: ReconciliationResult
    report: DailyCloseReport


def run_read_only_daily_close(*, connector: ReadOnlyPlatformConnector,
                              store: SQLiteLedgerStore,
                              portfolio_id: str, marks: Mapping[str, float],
                              report_path: str | Path,
                              report_date: date | None = None,
                              exception_store: FundV2Store | None = None,
                              exception_owner: str = "sync") -> DailyCloseRun:
    """Sync once, persist idempotently, reconcile, then write the report.

    This workflow intentionally accepts only a `ReadOnlyPlatformConnector` and
    contains no execution pathway.
    """
    platform = getattr(connector, "platform")
    account_id = getattr(connector, "account_id")
    sync = connector.sync(store.get_cursor(platform, account_id))
    inserted = store.append_many(list(sync.events))
    store.set_cursor(sync.platform, sync.account_id, sync.cursor)
    ledger = store.load_ledger(portfolio_id)
    reconciliation = reconcile_positions(
        ledger, sync.balances, marks,
        reporting_asset=getattr(connector, "reporting_asset", None),
        derivative_positions=sync.positions)
    if exception_store is not None and reconciliation.exceptions:
        close_date = (report_date or date.today()).isoformat()
        for item in reconciliation.exceptions:
            exception_store.add_exception(
                portfolio_id, close_date, item.asset, item.reason, exception_owner)
    report = build_daily_close(ledger, marks, reconciliation, report_date,
                               data_as_of=sync.synced_at, platform=sync.platform,
                               account_id=sync.account_id, balances=tuple(sync.balances))
    write_daily_close(report, report_path)
    return DailyCloseRun(inserted, reconciliation, report)
