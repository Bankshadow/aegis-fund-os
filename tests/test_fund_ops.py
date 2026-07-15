from datetime import datetime, timezone
import tempfile
from pathlib import Path
import unittest

from dynamic_grid.fund_ops import AppendOnlyLedger, EventType, LedgerEvent


TIME = datetime(2026, 7, 15, tzinfo=timezone.utc)


class FundOperationsTests(unittest.TestCase):
    def fill(self, event_id, side, quantity, price, fee=0.0):
        return LedgerEvent.trade_fill(
            event_id=event_id, external_id=f"binance:{event_id}", platform="binance",
            account_id="acct-1", portfolio_id="main", strategy_id="grid",
            instrument="BTC/USDT", side=side, quantity=quantity, price=price,
            fee=fee, occurred_at=TIME)

    def test_snapshot_reports_gross_net_and_open_position(self):
        ledger = AppendOnlyLedger()
        ledger.append(self.fill("fill-1", "buy", 2.0, 100.0, fee=1.0))
        ledger.append(self.fill("fill-2", "sell", 1.0, 120.0, fee=1.0))
        ledger.append(LedgerEvent.cash_event(
            event_id="funding-1", external_id="binance:funding-1",
            event_type=EventType.FUNDING, platform="binance", account_id="acct-1",
            portfolio_id="main", cash_amount=-2.0, occurred_at=TIME))

        snapshot = ledger.snapshot({"BTC/USDT": 110.0})

        self.assertEqual(snapshot.realized_gross_pnl, 20.0)
        self.assertEqual(snapshot.unrealized_gross_pnl, 10.0)
        self.assertEqual(snapshot.trade_fees, 2.0)
        self.assertEqual(snapshot.carry_pnl, -2.0)
        self.assertEqual(snapshot.net_pnl, 26.0)
        self.assertEqual(snapshot.reporting_cash_balance, -84.0)
        self.assertEqual(snapshot.positions[0].quantity, 1.0)

    def test_external_id_makes_sync_idempotent(self):
        ledger = AppendOnlyLedger()
        event = self.fill("fill-1", "buy", 1.0, 100.0)
        self.assertTrue(ledger.append(event))
        self.assertFalse(ledger.append(event))
        self.assertEqual(len(ledger.events), 1)

    def test_transfer_is_excluded_from_performance_pnl(self):
        ledger = AppendOnlyLedger()
        ledger.append(LedgerEvent.cash_event(
            event_id="transfer-1", external_id="bank:transfer-1",
            event_type=EventType.TRANSFER, platform="bank", account_id="acct-1",
            portfolio_id="main", cash_amount=10_000.0, occurred_at=TIME))
        snapshot = ledger.snapshot({})
        self.assertEqual(snapshot.net_pnl, 0.0)
        self.assertEqual(snapshot.reporting_cash_balance, 10_000.0)

    def test_sell_fails_closed_when_inventory_is_missing(self):
        ledger = AppendOnlyLedger()
        ledger.append(self.fill("fill-1", "sell", 1.0, 100.0))
        with self.assertRaisesRegex(ValueError, "exceeds recorded inventory"):
            ledger.snapshot({})

    def test_derivative_fills_support_short_realized_and_unrealized_pnl(self):
        ledger = AppendOnlyLedger()
        ledger.append(LedgerEvent.derivative_fill(
            event_id="future-1", external_id="future-1", platform="binance_usdm",
            account_id="futures", portfolio_id="main", instrument="BTCUSDT",
            side="sell", quantity=2.0, price=100.0, fee=1.0, occurred_at=TIME))
        ledger.append(LedgerEvent.derivative_fill(
            event_id="future-2", external_id="future-2", platform="binance_usdm",
            account_id="futures", portfolio_id="main", instrument="BTCUSDT",
            side="buy", quantity=1.0, price=90.0, fee=1.0, occurred_at=TIME))
        snapshot = ledger.snapshot({"BTCUSDT": 80.0})
        self.assertEqual(snapshot.realized_gross_pnl, 10.0)
        self.assertEqual(snapshot.unrealized_gross_pnl, 20.0)
        self.assertEqual(snapshot.positions[0].kind, "derivative")

    def test_jsonl_export_preserves_source_identifiers(self):
        ledger = AppendOnlyLedger()
        ledger.append(self.fill("fill-1", "buy", 1.0, 100.0))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger.export_jsonl(path)
            line = path.read_text(encoding="utf-8")
        self.assertIn('"external_id": "binance:fill-1"', line)
        self.assertIn('"event_type": "trade_fill"', line)


if __name__ == "__main__":
    unittest.main()
