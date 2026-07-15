"""SQLite persistence for the fund-operations append-only ledger."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from .fund_ops import AppendOnlyLedger, EventType, LedgerEvent


class SQLiteLedgerStore:
    """Durable event store.  Events are inserted once and never updated."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger_events (
                    event_id TEXT PRIMARY KEY,
                    external_id TEXT NOT NULL UNIQUE,
                    occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    portfolio_id TEXT NOT NULL,
                    strategy_id TEXT,
                    instrument TEXT,
                    side TEXT,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    fee REAL NOT NULL,
                    cash_amount REAL NOT NULL,
                    source_ref TEXT,
                    metadata_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_scope_time "
                         "ON ledger_events(portfolio_id, occurred_at)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    cursor TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(platform, account_id)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def append(self, event: LedgerEvent) -> bool:
        values = asdict(event)
        values["occurred_at"] = event.occurred_at.isoformat()
        values["event_type"] = event.event_type.value
        values["metadata_json"] = json.dumps(values.pop("metadata"), sort_keys=True)
        conn = self._connect()
        try:
            try:
                conn.execute("""
                    INSERT INTO ledger_events VALUES (
                        :event_id, :external_id, :occurred_at, :event_type, :platform,
                        :account_id, :portfolio_id, :strategy_id, :instrument, :side,
                        :quantity, :price, :fee, :cash_amount, :source_ref, :metadata_json)
                """, values)
            except sqlite3.IntegrityError:
                conn.rollback()
                return False
            conn.commit()
        finally:
            conn.close()
        return True

    def append_many(self, events: list[LedgerEvent]) -> int:
        return sum(1 for event in events if self.append(event))

    def get_cursor(self, platform: str, account_id: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT cursor FROM sync_cursors WHERE platform = ? AND account_id = ?",
                               (platform, account_id)).fetchone()
            return None if row is None else row["cursor"]
        finally:
            conn.close()

    def set_cursor(self, platform: str, account_id: str, cursor: str | None) -> None:
        conn = self._connect()
        try:
            conn.execute("""
                INSERT INTO sync_cursors(platform, account_id, cursor, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(platform, account_id) DO UPDATE SET
                    cursor = excluded.cursor, updated_at = excluded.updated_at
            """, (platform, account_id, cursor, datetime.now().astimezone().isoformat()))
            conn.commit()
        finally:
            conn.close()

    def load_ledger(self, portfolio_id: str | None = None) -> AppendOnlyLedger:
        query = "SELECT * FROM ledger_events"
        params: tuple[str, ...] = ()
        if portfolio_id is not None:
            query += " WHERE portfolio_id = ?"
            params = (portfolio_id,)
        query += " ORDER BY occurred_at, event_id"
        ledger = AppendOnlyLedger()
        conn = self._connect()
        try:
            for row in conn.execute(query, params):
                ledger.append(LedgerEvent(
                    event_id=row["event_id"], external_id=row["external_id"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    event_type=EventType(row["event_type"]), platform=row["platform"],
                    account_id=row["account_id"], portfolio_id=row["portfolio_id"],
                    strategy_id=row["strategy_id"], instrument=row["instrument"],
                    side=row["side"], quantity=row["quantity"], price=row["price"],
                    fee=row["fee"], cash_amount=row["cash_amount"],
                    source_ref=row["source_ref"], metadata=json.loads(row["metadata_json"])))
        finally:
            conn.close()
        return ledger
