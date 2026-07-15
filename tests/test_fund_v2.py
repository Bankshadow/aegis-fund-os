import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from dynamic_grid.fund_v2_store import FundV2Store
from dynamic_grid.track_record import metrics
from dynamic_grid.paper_execution import PaperBroker, PaperRiskPolicy
from dynamic_grid.fund_ops import PlatformBalance
from dynamic_grid.fund_v2 import ApprovedFxValuation
from dynamic_grid.operations_snapshot import build_operations_snapshot, write_operations_snapshot

class FundV2StoreTests(unittest.TestCase):
    def test_operations_snapshot_is_ready_only_when_report_and_exceptions_are_clean(self):
        report = {
            "status": "clean", "data_as_of": "2026-07-15T00:00:00+00:00",
            "generated_at": "2026-07-15T00:01:00+00:00",
            "reporting_cash_balance": 100.0,
            "positions": [{"quantity": 2.0, "market_price": 50.0}],
        }
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(__import__("json").dumps(report), encoding="utf-8")
            store = FundV2Store(Path(directory) / "fund.sqlite")
            snapshot = build_operations_snapshot(
                report_path=report_path, exception_store=store,
                portfolio_id="main", report_date="2026-07-15",
                reporting_currency="USD", fx_rates={"EUR/USD": 1.08})
            self.assertEqual(snapshot["status"], "ready")
            self.assertEqual(snapshot["fx"]["totalBaseValue"], 200.0)
            store.add_exception("main", "2026-07-15", "EUR", "missing mark", "ops")
            provisional = build_operations_snapshot(
                report_path=report_path, exception_store=store,
                portfolio_id="main", report_date="2026-07-15",
                reporting_currency="USD", fx_rates={"EUR/USD": 1.08})
            self.assertEqual(provisional["status"], "provisional")
            output = Path(directory) / "operations_snapshot.json"
            write_operations_snapshot(provisional, output)
            self.assertEqual(__import__("json").loads(output.read_text())["status"], "provisional")

    def test_approved_fx_valuation_is_fail_closed(self):
        valuation = ApprovedFxValuation("USDT", datetime(2026, 7, 15), {"BNB/USDT": 600})
        self.assertEqual(valuation.convert("BNB", 0.01), 6.0)
        self.assertEqual(valuation.value_balances([PlatformBalance("USDT", 10, 10)]), 10.0)
        with self.assertRaisesRegex(ValueError, "ETH/USDT"):
            valuation.convert("ETH", 1)

    def test_exception_must_be_resolved_before_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store=FundV2Store(Path(directory)/"fund.sqlite")
            store.record_close("main","2026-07-15",10_100,100,"provisional")
            store.add_exception("main","2026-07-15","USDT","cash mismatch","ops")
            with self.assertRaises(ValueError): store.lock_close("main","2026-07-15","approver")
            store.resolve_exception(1,"matched source statement","approver")
            store.lock_close("main","2026-07-15","approver")
            self.assertEqual(store.close_history("main")[0]["status"],"locked")

    def test_exception_resolution_is_durable_deduplicated_and_four_eyes(self):
        with tempfile.TemporaryDirectory() as directory:
            store=FundV2Store(Path(directory)/"fund.sqlite")
            first=store.add_exception("main","2026-07-15","ETH","missing FX","ops")
            second=store.add_exception("main","2026-07-15","ETH","missing FX","ops")
            self.assertEqual(first, second)
            with self.assertRaises(PermissionError):
                store.resolve_exception(first,"rate supplied","ops")
            store.resolve_exception(first,"rate supplied","reviewer")
            rows=store.list_exceptions("main","2026-07-15")
            self.assertEqual(rows[0]["status"],"resolved")
            self.assertEqual(rows[0]["approved_by"],"reviewer")

    def test_track_record_and_paper_kill_switch(self):
        result=metrics([{"report_date":"2026-07-01","nav":100,"net_pnl":0},{"report_date":"2026-07-02","nav":110,"net_pnl":10},{"report_date":"2026-07-03","nav":99,"net_pnl":-11}])
        self.assertAlmostEqual(result["twr"],-0.01)
        broker=PaperBroker(PaperRiskPolicy(frozenset({"BTC/USDT"}),1000))
        broker.submit("BTC/USDT","buy",0.01,50000)
        broker.kill_switch()
        with self.assertRaises(PermissionError): broker.submit("BTC/USDT","buy",0.01,50000)
