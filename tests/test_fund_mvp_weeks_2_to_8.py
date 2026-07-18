from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from dynamic_grid.binance_connector import (ApprovedMarksFeeConverter,
                                             BinanceReadOnlyCredentials,
                                             BinanceSpotReadOnlyConnector)
from dynamic_grid.binance_futures_connector import BinanceUsdmFundingReadOnlyConnector
from dynamic_grid.fund_controls import AccessController, Operation, Role
from dynamic_grid.fund_ops import AppendOnlyLedger, LedgerEvent, PlatformBalance
from dynamic_grid.fund_reporting import build_daily_close, write_daily_close
from dynamic_grid.fund_ops import ConnectorSync, EventType
from dynamic_grid.fund_ops_job import run_read_only_daily_close
from fund_ops_cli import build_parser, parse_marks
from dynamic_grid.fund_storage import SQLiteLedgerStore
from dynamic_grid.fund_v2_store import FundV2Store
from dynamic_grid.reconciliation import ReconciliationStatus, reconcile_positions


TIME = datetime(2026, 7, 15, tzinfo=timezone.utc)


def fill(event_id="fill-1", side="buy", quantity=1.0, price=100.0):
    return LedgerEvent.trade_fill(
        event_id=event_id, external_id=f"source:{event_id}", platform="binance",
        account_id="acct-1", portfolio_id="main", instrument="BTC/USDT",
        side=side, quantity=quantity, price=price, occurred_at=TIME)


class FakeBinanceTransport:
    """Minimal Binance GET stub for Spot account, trades, and capital history."""

    def __init__(self, *, trades=None, deposits=None, withdraws=None, balances=None,
                 dividends=None):
        self.trades = trades if trades is not None else [{
            "id": 77, "orderId": 88, "time": 1784073600000, "isBuyer": True,
            "qty": "1", "price": "100", "commission": "0.1",
            "commissionAsset": "USDT",
        }]
        self.deposits = deposits if deposits is not None else []
        self.withdraws = withdraws if withdraws is not None else []
        self.dividends = dividends if dividends is not None else []
        self.balances = balances if balances is not None else [
            {"asset": "BTC", "free": "1.0", "locked": "0"},
            {"asset": "USDT", "free": "100", "locked": "0"},
        ]
        self.calls: list[tuple[str, dict]] = []

    def get(self, path, params, api_key):
        self.calls.append((path, dict(params)))
        self.last = (path, params, api_key)
        if path == "/api/v3/account":
            return {"balances": self.balances}
        if path == "/api/v3/myTrades":
            return list(self.trades)
        if path == "/sapi/v1/capital/deposit/hisrec":
            return list(self.deposits)
        if path == "/sapi/v1/capital/withdraw/history":
            return list(self.withdraws)
        if path == "/sapi/v1/asset/assetDividend":
            return {"rows": list(self.dividends), "total": len(self.dividends)}
        raise AssertionError(f"unexpected path {path}")


class FakeReadOnlyConnector:
    platform = "test"
    account_id = "acct-1"

    def __init__(self):
        self.cursors = []

    def sync(self, cursor=None):
        self.cursors.append(cursor)
        return ConnectorSync("test", "acct-1", TIME, "cursor-1",
                             [PlatformBalance("BTC", 1.0, 1.0)], [fill()])


class FakeUsdmTransport:
    def __init__(self, income=None, positions=None, transfers=None, trades=None):
        self.income = income if income is not None else [{
            "symbol": "BTCUSDT", "incomeType": "FUNDING_FEE", "income": "-1.25",
            "asset": "USDT", "time": 1784073600000, "tranId": "fund-1",
        }]
        self.positions = positions if positions is not None else []
        self.transfers = transfers if transfers is not None else []
        self.trades = trades if trades is not None else []
        self.calls = []

    def get(self, path, params, api_key):
        self.calls.append((path, dict(params), api_key))
        if path == "/fapi/v2/balance":
            return [{"asset": "USDT", "balance": "500", "availableBalance": "420"}]
        if path == "/fapi/v3/positionRisk":
            return list(self.positions)
        if path == "/fapi/v1/income":
            if params.get("incomeType") == "TRANSFER":
                return list(self.transfers)
            return list(self.income)
        if path == "/fapi/v1/userTrades":
            return list(self.trades)
        raise AssertionError(f"unexpected path {path}")


class FundMvpWeeksTwoToEightTests(unittest.TestCase):
    def test_sqlite_store_is_durable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteLedgerStore(Path(directory) / "ledger.sqlite")
            self.assertTrue(store.append(fill()))
            self.assertFalse(store.append(fill()))
            snapshot = store.load_ledger("main").snapshot({"BTC/USDT": 110.0})
        self.assertEqual(snapshot.net_pnl, 10.0)

    def test_binance_read_only_connector_maps_balance_and_fills(self):
        transport = FakeBinanceTransport()
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        sync = connector.sync()
        self.assertEqual(sync.platform, "binance")
        self.assertEqual(sync.balances[0].asset, "BTC")
        self.assertEqual(sync.events[0].instrument, "BTC/USDT")
        self.assertEqual(sync.events[0].fee, 0.1)
        self.assertTrue(transport.last[1]["signature"])

    def test_approved_marks_fee_converter_converts_bnb(self):
        converter = ApprovedMarksFeeConverter({"BNB/USDT": 600.0})
        self.assertAlmostEqual(converter("BNB", 0.01, TIME), 6.0)

    def test_approved_marks_fee_converter_fails_closed_without_mark(self):
        converter = ApprovedMarksFeeConverter({"BTC/USDT": 65000.0})
        with self.assertRaises(ValueError) as ctx:
            converter("BNB", 0.01, TIME)
        self.assertIn("BNB/USDT", str(ctx.exception))

    def test_binance_bnb_commission_uses_fee_converter(self):
        transport = FakeBinanceTransport(trades=[{
            "id": 77, "orderId": 88, "time": 1784073600000, "isBuyer": True,
            "qty": "1", "price": "100", "commission": "0.01",
            "commissionAsset": "BNB",
        }])
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport,
            fee_converter=ApprovedMarksFeeConverter({"BNB/USDT": 600.0}))
        sync = connector.sync()
        fills = [e for e in sync.events if e.event_type is EventType.TRADE_FILL]
        self.assertEqual(len(fills), 1)
        self.assertAlmostEqual(fills[0].fee, 6.0)

    def test_binance_bnb_commission_without_converter_raises(self):
        transport = FakeBinanceTransport(trades=[{
            "id": 77, "orderId": 88, "time": 1784073600000, "isBuyer": True,
            "qty": "1", "price": "100", "commission": "0.01",
            "commissionAsset": "BNB",
        }])
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        with self.assertRaises(ValueError) as ctx:
            connector.sync()
        self.assertIn("unpriced commission asset BNB", str(ctx.exception))

    def test_binance_syncs_usdt_deposit_and_withdraw_as_transfer(self):
        transport = FakeBinanceTransport(
            deposits=[{
                "id": "dep-1", "coin": "USDT", "amount": "1000", "status": 1,
                "insertTime": 1784073600000, "txId": "tx-dep-1",
            }],
            withdraws=[{
                "id": "wd-1", "coin": "USDT", "amount": "100",
                "transactionFee": "1", "status": 6,
                "applyTime": "2026-07-15 00:00:00", "txId": "tx-wd-1",
            }],
            balances=[
                {"asset": "BTC", "free": "1.0", "locked": "0"},
                {"asset": "USDT", "free": "798.9", "locked": "0"},
            ],
        )
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        sync = connector.sync()
        transfers = [e for e in sync.events if e.event_type is EventType.TRANSFER]
        self.assertEqual(len(transfers), 2)
        by_id = {e.external_id: e for e in transfers}
        self.assertAlmostEqual(by_id["binance:deposit:dep-1"].cash_amount, 1000.0)
        self.assertAlmostEqual(by_id["binance:withdraw:wd-1"].cash_amount, -101.0)

        ledger = AppendOnlyLedger()
        for event in sync.events:
            ledger.append(event)
        # buy 1 BTC @ 100 fee 0.1 + deposit 1000 - withdraw 101 = cash 798.9
        recon = reconcile_positions(
            ledger, list(sync.balances), {}, reporting_asset="USDT")
        self.assertEqual(recon.status, ReconciliationStatus.CLEAN)
        snap = ledger.snapshot({})
        # transfer must not affect performance P/L; only fee reduces net
        self.assertAlmostEqual(snap.net_pnl, -0.1)
        self.assertAlmostEqual(snap.reporting_cash_balance, 798.9)

    def test_binance_non_reporting_deposit_fails_closed(self):
        transport = FakeBinanceTransport(deposits=[{
            "id": "dep-btc", "coin": "BTC", "amount": "0.5", "status": 1,
            "insertTime": 1784073600000, "txId": "tx-btc",
        }])
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        with self.assertRaises(ValueError) as ctx:
            connector.sync()
        self.assertIn("non-reporting capital asset BTC", str(ctx.exception))

    def test_binance_non_reporting_capital_uses_approved_fx(self):
        transport = FakeBinanceTransport(
            deposits=[{
                "id": "dep-btc", "coin": "BTC", "amount": "0.5", "status": 1,
                "insertTime": 1784073600000, "txId": "tx-btc",
            }],
            withdraws=[{
                "id": "wd-eth", "coin": "ETH", "amount": "2",
                "transactionFee": "0.01", "status": 6,
                "applyTime": "2026-07-15 00:00:00", "txId": "tx-eth",
            }],
        )
        rates = {"BTC/USDT": 100_000.0, "ETH/USDT": 3_000.0}
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport,
            capital_fx=lambda asset, amount, when: amount * rates[f"{asset}/USDT"])
        sync = connector.sync()
        by_id = {e.external_id: e for e in sync.events}
        deposit = by_id["binance:deposit:dep-btc"]
        self.assertEqual(deposit.event_type, EventType.TRANSFER)
        self.assertAlmostEqual(deposit.cash_amount, 50_000.0)  # 0.5 BTC * 100k
        self.assertEqual(deposit.metadata["original_asset"], "BTC")
        withdraw = by_id["binance:withdraw:wd-eth"]
        self.assertAlmostEqual(withdraw.cash_amount, -6_030.0)  # (2 + 0.01) ETH * 3k

    def test_binance_syncs_reporting_dividend_as_rebate(self):
        transport = FakeBinanceTransport(dividends=[{
            "id": "div-1", "asset": "USDT", "amount": "12.5",
            "divTime": 1784073600000, "tranId": "tran-1", "enInfo": "Launchpool",
        }])
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        sync = connector.sync()
        rebates = [e for e in sync.events if e.event_type is EventType.REBATE]
        self.assertEqual(len(rebates), 1)
        self.assertAlmostEqual(rebates[0].cash_amount, 12.5)
        self.assertEqual(rebates[0].external_id, "binance:dividend:div-1")
        # carry income lifts net P/L but is not a capital transfer
        ledger = AppendOnlyLedger()
        for event in sync.events:
            ledger.append(event)
        snap = ledger.snapshot({})
        self.assertAlmostEqual(snap.carry_pnl, 12.5)

    def test_binance_foreign_dividend_fails_closed_without_fx(self):
        transport = FakeBinanceTransport(dividends=[{
            "id": "div-2", "asset": "BNB", "amount": "0.3",
            "divTime": 1784073600000, "tranId": "tran-2",
        }])
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        with self.assertRaises(ValueError) as ctx:
            connector.sync()
        self.assertIn("non-reporting capital asset BNB", str(ctx.exception))

    def test_binance_transfer_events_are_idempotent_in_store(self):
        transport = FakeBinanceTransport(deposits=[{
            "id": "dep-1", "coin": "USDT", "amount": "500", "status": 1,
            "insertTime": 1784073600000, "txId": "tx-dep-1",
        }])
        connector = BinanceSpotReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="acct-1",
            portfolio_id="main", symbols=("BTCUSDT",), transport=transport)
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteLedgerStore(Path(directory) / "ledger.sqlite")
            first = connector.sync()
            second = connector.sync()
            inserted = sum(1 for e in first.events if store.append(e))
            again = sum(1 for e in second.events if store.append(e))
        self.assertGreaterEqual(inserted, 1)
        self.assertEqual(again, 0)

    def test_usdm_funding_connector_maps_income_to_funding_event(self):
        transport = FakeUsdmTransport()
        connector = BinanceUsdmFundingReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="futures-1",
            portfolio_id="main", transport=transport)
        sync = connector.sync()
        self.assertEqual(sync.platform, "binance_usdm")
        self.assertEqual(sync.balances[0].available, 420.0)
        self.assertEqual(sync.events[0].event_type, EventType.FUNDING)
        self.assertEqual(sync.events[0].cash_amount, -1.25)
        self.assertEqual(sync.cursor, "1784073600000")
        income_call = [call for call in transport.calls if call[0] == "/fapi/v1/income"][0]
        self.assertEqual(income_call[1]["incomeType"], "FUNDING_FEE")
        self.assertTrue(income_call[1]["signature"])

    def test_usdm_funding_connector_fails_closed_on_foreign_currency(self):
        connector = BinanceUsdmFundingReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="futures-1",
            portfolio_id="main", transport=FakeUsdmTransport([{
                "symbol": "BTCBUSD", "incomeType": "FUNDING_FEE", "income": "1",
                "asset": "BUSD", "time": 1784073600000, "tranId": "fund-busd",
            }]))
        with self.assertRaisesRegex(ValueError, "non-reporting funding asset BUSD"):
            connector.sync()

    def test_usdm_sync_includes_collateral_transfers_and_remote_positions(self):
        transport = FakeUsdmTransport(
            positions=[{"symbol": "BTCUSDT", "positionAmt": "0.2", "entryPrice": "60000",
                        "markPrice": "61000", "unRealizedProfit": "200"}],
            transfers=[{"incomeType": "TRANSFER", "income": "1000", "asset": "USDT",
                        "time": 1784073600000, "tranId": "collateral-1"}])
        sync = BinanceUsdmFundingReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="futures-1",
            portfolio_id="main", transport=transport).sync()
        self.assertEqual(sync.positions[0].quantity, 0.2)
        transfer = [event for event in sync.events if event.event_type is EventType.TRANSFER][0]
        self.assertEqual(transfer.cash_amount, 1000.0)

    def test_usdm_sync_maps_fills_and_reconciles_remote_position(self):
        transport = FakeUsdmTransport(
            positions=[{"symbol": "BTCUSDT", "positionAmt": "0.2", "entryPrice": "60000",
                        "markPrice": "61000", "unRealizedProfit": "200"}],
            trades=[{"id": 9, "orderId": 10, "time": 1784073600000,
                     "buyer": True, "qty": "0.2", "price": "60000",
                     "commission": "0.1", "commissionAsset": "USDT"}],
        )
        connector = BinanceUsdmFundingReadOnlyConnector(
            BinanceReadOnlyCredentials("key", "secret"), account_id="futures-1",
            portfolio_id="main", transport=transport, symbols=("BTCUSDT",))
        sync = connector.sync()
        fills = [event for event in sync.events if event.event_type is EventType.DERIVATIVE_FILL]
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].source_ref, "order:10")
        ledger = AppendOnlyLedger()
        for event in sync.events:
            ledger.append(event)
        result = reconcile_positions(ledger, [], {"BTCUSDT": 61000},
                                     derivative_positions=sync.positions)
        self.assertEqual(result.status, ReconciliationStatus.CLEAN)

    def test_reconciliation_marks_mismatches_as_provisional(self):
        ledger = AppendOnlyLedger()
        ledger.append(fill())
        clean = reconcile_positions(ledger, [PlatformBalance("BTC", 1.0, 1.0)], {})
        mismatch = reconcile_positions(ledger, [PlatformBalance("BTC", 0.8, 0.8)], {})
        self.assertEqual(clean.status, ReconciliationStatus.CLEAN)
        self.assertEqual(mismatch.status, ReconciliationStatus.PROVISIONAL)
        self.assertAlmostEqual(mismatch.exceptions[0].difference, -0.2)

    def test_cash_reconciliation_requires_recorded_cash_flows(self):
        ledger = AppendOnlyLedger()
        ledger.append(LedgerEvent.cash_event(
            event_id="deposit-1", external_id="bank:deposit-1", event_type=EventType.TRANSFER,
            platform="bank", account_id="acct-1", portfolio_id="main", cash_amount=1_000.0,
            occurred_at=TIME))
        ledger.append(fill())
        clean = reconcile_positions(ledger, [PlatformBalance("BTC", 1.0, 1.0),
                                               PlatformBalance("USDT", 900.0, 900.0)], {},
                                    reporting_asset="USDT")
        self.assertEqual(clean.status, ReconciliationStatus.CLEAN)

    def test_daily_close_contains_provisional_status_and_drilldown(self):
        ledger = AppendOnlyLedger()
        ledger.append(fill())
        reconciliation = reconcile_positions(
            ledger, [PlatformBalance("BTC", 0.9, 0.9)], {"BTC/USDT": 120.0})
        report = build_daily_close(ledger, {"BTC/USDT": 120.0}, reconciliation,
                                   report_date=date(2026, 7, 15))
        self.assertEqual(report.status, "provisional")
        self.assertEqual(report.net_pnl, 20.0)
        self.assertEqual(report.positions[0]["instrument"], "BTC/USDT")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily-close.json"
            write_daily_close(report, path)
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["status"], "provisional")

    def test_mvp_controls_never_authorize_order_placement(self):
        controls = AccessController()
        controls.authorize("operator-1", Role.OPERATOR, Operation.SYNC_READ_ONLY)
        with self.assertRaises(PermissionError):
            controls.authorize("admin-1", Role.ADMIN, Operation.PLACE_ORDER)
        self.assertEqual(controls.audit_events[-1].outcome, "denied")

    def test_daily_close_job_persists_cursor_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteLedgerStore(Path(directory) / "ledger.sqlite")
            connector = FakeReadOnlyConnector()
            output = Path(directory) / "report.json"
            first = run_read_only_daily_close(connector=connector, store=store,
                portfolio_id="main", marks={"BTC/USDT": 110.0}, report_path=output)
            second = run_read_only_daily_close(connector=connector, store=store,
                portfolio_id="main", marks={"BTC/USDT": 110.0}, report_path=output)
            self.assertEqual(first.events_inserted, 1)
            self.assertEqual(second.events_inserted, 0)
            self.assertEqual(connector.cursors, [None, "cursor-1"])
            rendered = json.loads(output.read_text())
            self.assertEqual(rendered["data_as_of"], TIME.isoformat())
            self.assertEqual(rendered["platform"], "test")
            self.assertEqual(rendered["ledger_events"][0]["external_id"], "source:fill-1")

    def test_daily_close_persists_reconciliation_exceptions(self):
        class MismatchConnector(FakeReadOnlyConnector):
            def sync(self, cursor=None):
                self.cursors.append(cursor)
                return ConnectorSync("test", "acct-1", TIME, "cursor-1",
                                     [PlatformBalance("BTC", 0.8, 0.8)], [fill()])

        with tempfile.TemporaryDirectory() as directory:
            ledger_store = SQLiteLedgerStore(Path(directory) / "ledger.sqlite")
            exception_store = FundV2Store(Path(directory) / "fund.sqlite")
            run_read_only_daily_close(
                connector=MismatchConnector(), store=ledger_store, portfolio_id="main",
                marks={"BTC/USDT": 110.0}, report_path=Path(directory) / "report.json",
                report_date=date(2026, 7, 15), exception_store=exception_store,
                exception_owner="maker")
            rows = exception_store.list_exceptions("main", "2026-07-15", "open")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["owner"], "maker")

    def test_cli_marks_require_symbol_price_pairs(self):
        self.assertEqual(parse_marks(["BTC/USDT=65000", "ETH/USDT=3500"]),
                         {"BTC/USDT": 65000.0, "ETH/USDT": 3500.0})
        with self.assertRaises(Exception):
            parse_marks(["invalid"])

    def test_cli_allows_usdm_funding_without_symbols_or_marks(self):
        args = build_parser().parse_args([
            "--account-id", "futures-1", "--source", "usdm-funding"])
        self.assertEqual(args.source, "usdm-funding")
        self.assertEqual(args.symbol, None)


if __name__ == "__main__":
    unittest.main()
