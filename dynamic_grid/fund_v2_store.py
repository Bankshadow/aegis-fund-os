"""Durable MVP-v2 portfolio close, exception, and audit records."""
from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

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
            """); conn.commit()
        finally: conn.close()
    def record_close(self, portfolio_id, report_date, nav, net_pnl, status):
        # Idempotent: re-running a daily close updates NAV/status unless the close
        # is already locked, which is preserved so a signed NAV cannot be rewritten.
        conn=self._connect()
        try:
            conn.execute(
                "INSERT INTO portfolio_closes(portfolio_id,report_date,nav,net_pnl,status) VALUES(?,?,?,?,?) "
                "ON CONFLICT(portfolio_id,report_date) DO UPDATE SET nav=excluded.nav,net_pnl=excluded.net_pnl,status=excluded.status WHERE locked=0",
                (portfolio_id,report_date,nav,net_pnl,status)); conn.commit()
        finally: conn.close()
    def add_exception(self, portfolio_id, report_date, asset, reason, owner):
        conn=self._connect()
        try:
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
            open_count=conn.execute("SELECT count(*) FROM reconciliation_exceptions WHERE portfolio_id=? AND report_date=? AND status='open'",(portfolio_id,report_date)).fetchone()[0]
            if open_count: raise ValueError("cannot lock close with open exceptions")
            conn.execute("UPDATE portfolio_closes SET locked=1,approved_by=?,status='locked' WHERE portfolio_id=? AND report_date=?",(approver,portfolio_id,report_date))
            conn.execute("INSERT INTO fund_audit VALUES(?,?,?,?)",(datetime.now(timezone.utc).isoformat(),approver,"lock_close",f"{portfolio_id}:{report_date}")); conn.commit()
        finally: conn.close()
    def close_history(self, portfolio_id):
        conn=self._connect()
        try: return [dict(row) for row in conn.execute("SELECT * FROM portfolio_closes WHERE portfolio_id=? ORDER BY report_date",(portfolio_id,))]
        finally: conn.close()
