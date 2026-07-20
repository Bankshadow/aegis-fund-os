"""Durable MVP-v2 portfolio close, exception, and audit records."""
from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


def reporting_period(report_date: str, granularity: str = "month") -> str:
    """Map a report date to its reporting period: ``YYYY-MM`` or ``YYYY-Qn``.

    Fails closed on a malformed date rather than silently bucketing a close into
    the wrong period, which would let a back-dated write slip past a sealed one.
    """
    try:
        year, month = int(report_date[0:4]), int(report_date[5:7])
        if report_date[4] != "-":
            raise ValueError
    except (ValueError, IndexError):
        raise ValueError(f"invalid report_date {report_date!r}; expected YYYY-MM-DD") from None
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month in report_date {report_date!r}")
    if granularity == "month":
        return f"{year:04d}-{month:02d}"
    if granularity == "quarter":
        return f"{year:04d}-Q{(month - 1) // 3 + 1}"
    raise ValueError("granularity must be 'month' or 'quarter'")


def periods_covering(report_date: str) -> tuple[str, str]:
    """Both period identifiers a date belongs to (month and quarter).

    A date must be checked against both, because a period may have been sealed at
    either granularity.
    """
    return reporting_period(report_date, "month"), reporting_period(report_date, "quarter")


class FundV2Store:
    def __init__(self, path: str | Path):
        self.path=str(path); self._init()
    def _connect(self):
        conn=sqlite3.connect(self.path); conn.row_factory=sqlite3.Row; return conn
    def _init(self):
        conn=self._connect()
        try:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS portfolio_closes (portfolio_id TEXT, report_date TEXT, nav REAL, net_pnl REAL, status TEXT, locked INTEGER DEFAULT 0, approved_by TEXT, PRIMARY KEY(portfolio_id,report_date));
            CREATE TABLE IF NOT EXISTS reconciliation_exceptions (id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_id TEXT, report_date TEXT, asset TEXT, reason TEXT, owner TEXT, status TEXT DEFAULT 'open', resolution TEXT, approved_by TEXT);
            CREATE TABLE IF NOT EXISTS fund_audit (occurred_at TEXT, actor TEXT, action TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS reporting_period_locks (portfolio_id TEXT, period TEXT, locked_by TEXT, locked_at TEXT, PRIMARY KEY(portfolio_id,period));
            """); conn.commit()
        finally: conn.close()

    def _sealed_period(self, conn, portfolio_id: str, report_date: str) -> str | None:
        """Return the sealed period covering this date, if any (month or quarter)."""
        month, quarter = periods_covering(report_date)
        row = conn.execute(
            "SELECT period FROM reporting_period_locks WHERE portfolio_id=? AND period IN (?,?)",
            (portfolio_id, month, quarter)).fetchone()
        return None if row is None else row["period"]

    def _reject_if_sealed(self, conn, portfolio_id: str, report_date: str, action: str) -> None:
        sealed = self._sealed_period(conn, portfolio_id, report_date)
        if sealed is not None:
            raise PermissionError(
                f"cannot {action} for {report_date}: reporting period {sealed} is locked")

    def lock_period(self, portfolio_id: str, period: str, approver: str) -> int:
        """Seal a reporting period so its numbers can no longer move.

        Requires that the period actually contains closes, that every one of them
        is already locked (the daily close carries the maker/checker control), and
        that no exception in the period is still open. Sealing is idempotent-safe:
        re-sealing an already sealed period is rejected rather than silently
        rewriting who signed it.
        """
        conn = self._connect()
        try:
            if conn.execute("SELECT 1 FROM reporting_period_locks WHERE portfolio_id=? AND period=?",
                            (portfolio_id, period)).fetchone() is not None:
                raise ValueError(f"reporting period {period} is already locked")
            closes = [dict(row) for row in conn.execute(
                "SELECT report_date,locked FROM portfolio_closes WHERE portfolio_id=?", (portfolio_id,))]
            in_period = [c for c in closes if period in periods_covering(c["report_date"])]
            if not in_period:
                raise ValueError(f"no closes recorded for reporting period {period}")
            unlocked = [c["report_date"] for c in in_period if not c["locked"]]
            if unlocked:
                raise ValueError(
                    f"cannot lock {period}: daily closes still unlocked: {', '.join(sorted(unlocked))}")
            dates = [c["report_date"] for c in in_period]
            placeholders = ",".join("?" for _ in dates)
            open_count = conn.execute(
                f"SELECT count(*) FROM reconciliation_exceptions WHERE portfolio_id=? AND status='open' "
                f"AND report_date IN ({placeholders})", (portfolio_id, *dates)).fetchone()[0]
            if open_count:
                raise ValueError(f"cannot lock {period} with {open_count} open exception(s)")
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO reporting_period_locks VALUES(?,?,?,?)",
                         (portfolio_id, period, approver, now))
            conn.execute("INSERT INTO fund_audit VALUES(?,?,?,?)",
                         (now, approver, "lock_period", f"{portfolio_id}:{period}"))
            conn.commit()
            return len(in_period)
        finally:
            conn.close()

    def locked_periods(self, portfolio_id: str) -> list[dict]:
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM reporting_period_locks WHERE portfolio_id=? ORDER BY period",
                (portfolio_id,))]
        finally:
            conn.close()
    def record_close(self, portfolio_id, report_date, nav, net_pnl, status):
        # Idempotent: re-running a daily close updates NAV/status unless the close
        # is already locked, which is preserved so a signed NAV cannot be rewritten.
        conn=self._connect()
        try:
            self._reject_if_sealed(conn, portfolio_id, report_date, "record a close")
            conn.execute(
                "INSERT INTO portfolio_closes(portfolio_id,report_date,nav,net_pnl,status) VALUES(?,?,?,?,?) "
                "ON CONFLICT(portfolio_id,report_date) DO UPDATE SET nav=excluded.nav,net_pnl=excluded.net_pnl,status=excluded.status WHERE locked=0",
                (portfolio_id,report_date,nav,net_pnl,status)); conn.commit()
        finally: conn.close()
    def add_exception(self, portfolio_id, report_date, asset, reason, owner):
        conn=self._connect()
        try:
            self._reject_if_sealed(conn, portfolio_id, report_date, "add an exception")
            row=conn.execute("SELECT id FROM reconciliation_exceptions WHERE portfolio_id=? AND report_date=? AND asset=? AND reason=? AND status='open'",(portfolio_id,report_date,asset,reason)).fetchone()
            if row is not None: return int(row["id"])
            cursor=conn.execute("INSERT INTO reconciliation_exceptions(portfolio_id,report_date,asset,reason,owner) VALUES(?,?,?,?,?)",(portfolio_id,report_date,asset,reason,owner)); conn.commit()
            return int(cursor.lastrowid)
        finally: conn.close()
    def resolve_exception(self, exception_id, resolution, approver):
        conn=self._connect()
        try:
            row=conn.execute("SELECT owner,status FROM reconciliation_exceptions WHERE id=?",(exception_id,)).fetchone()
            if row is None: raise ValueError("exception not found")
            if row["status"] != "open": raise ValueError("exception is not open")
            if row["owner"] == approver: raise PermissionError("exception owner cannot approve its own resolution")
            conn.execute("UPDATE reconciliation_exceptions SET status='resolved',resolution=?,approved_by=? WHERE id=?",(resolution,approver,exception_id))
            conn.execute("INSERT INTO fund_audit VALUES(?,?,?,?)",(datetime.now(timezone.utc).isoformat(),approver,"resolve_exception",str(exception_id))); conn.commit()
        finally: conn.close()
    def list_exceptions(self, portfolio_id, report_date, status=None):
        conn=self._connect()
        try:
            query="SELECT * FROM reconciliation_exceptions WHERE portfolio_id=? AND report_date=?"
            params=[portfolio_id,report_date]
            if status is not None: query += " AND status=?"; params.append(status)
            return [dict(row) for row in conn.execute(query+" ORDER BY id",params)]
        finally: conn.close()
    def lock_close(self, portfolio_id, report_date, approver):
        conn=self._connect()
        try:
            self._reject_if_sealed(conn, portfolio_id, report_date, "lock a close")
            open_count=conn.execute("SELECT count(*) FROM reconciliation_exceptions WHERE portfolio_id=? AND report_date=? AND status='open'",(portfolio_id,report_date)).fetchone()[0]
            if open_count: raise ValueError("cannot lock close with open exceptions")
            conn.execute("UPDATE portfolio_closes SET locked=1,approved_by=?,status='locked' WHERE portfolio_id=? AND report_date=?",(approver,portfolio_id,report_date))
            conn.execute("INSERT INTO fund_audit VALUES(?,?,?,?)",(datetime.now(timezone.utc).isoformat(),approver,"lock_close",f"{portfolio_id}:{report_date}")); conn.commit()
        finally: conn.close()
    def close_history(self, portfolio_id):
        conn=self._connect()
        try: return [dict(row) for row in conn.execute("SELECT * FROM portfolio_closes WHERE portfolio_id=? ORDER BY report_date",(portfolio_id,))]
        finally: conn.close()
