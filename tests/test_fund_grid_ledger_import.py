"""Tests for the D1 -> fund-ops ledger bridge."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

GOLDEN = (Path(__file__).resolve().parents[1] / "fund-command-center-local" / "test"
          / "fixtures" / "grid-ledger-export.golden.json")

from dynamic_grid.fund_ops import AppendOnlyLedger
from dynamic_grid.grid_ledger_import import (GridLedgerImportError, ImportResult,
                                             import_grid_fills,
                                             parse_grid_ledger_export)


def _fill(**overrides):
    fill = {
        "externalId": "aegis-BOT-abc-EXE-1-0",
        "exchangeOrderId": "111",
        "strategyId": "BOT-abc",
        "platform": "binance-spot-testnet",
        "accountId": "ACC-TESTNET-1",
        "portfolioId": "PF-GRID",
        "instrument": "BTCUSDT",
        "side": "buy",
        "quantity": "0.001",
        "price": "62950.10",
        "fee": "0.0629",
        "feeAsset": "USDT",
        "occurredAt": "2026-07-20T10:05:00Z",
        "sourceRef": "d1:grid_bot_orders:ORD-1",
    }
    fill.update(overrides)
    return fill


def _document(fills=None, **overrides):
    fills = [_fill()] if fills is None else fills
    document = {
        "version": 1,
        "generatedAt": "2026-07-23T00:00:00Z",
        "platform": "binance-spot-testnet",
        "accountId": "ACC-TESTNET-1",
        "portfolioId": "PF-GRID",
        "reportingCurrency": "USDT",
        "fills": fills,
        "rejected": [],
        "sourceRowCount": len(fills),
    }
    document.update(overrides)
    return document


class GridLedgerImportTests(unittest.TestCase):
    def test_imports_a_fill_with_real_execution_detail(self):
        ledger = AppendOnlyLedger()
        result = import_grid_fills(ledger, _document())
        self.assertIsInstance(result, ImportResult)
        self.assertEqual(result.appended, 1)
        self.assertEqual(result.duplicates, 0)
        event = ledger.events[0]
        self.assertEqual(event.price, 62950.10)
        self.assertEqual(event.quantity, 0.001)
        self.assertEqual(event.fee, 0.0629)
        self.assertEqual(event.side, "buy")
        self.assertEqual(event.instrument, "BTCUSDT")

    def test_bot_id_carries_through_as_strategy_for_attribution(self):
        ledger = AppendOnlyLedger()
        import_grid_fills(ledger, _document())
        self.assertEqual(ledger.events[0].strategy_id, "BOT-abc")

    def test_reimporting_the_same_export_appends_nothing(self):
        ledger = AppendOnlyLedger()
        import_grid_fills(ledger, _document())
        again = import_grid_fills(ledger, _document())
        self.assertEqual(again.appended, 0)
        self.assertEqual(again.duplicates, 1)
        self.assertEqual(len(ledger.events), 1)

    def test_export_carrying_rejected_rows_is_refused_entirely(self):
        # A partial import yields a NAV that is quietly wrong.
        document = _document()
        document["rejected"] = [
            {"orderId": "ORD-9", "clientOrderId": "c9", "botId": "BOT-abc",
             "reason": "MISSING_FILL_DETAIL", "detail": "apply migration 0005"}
        ]
        ledger = AppendOnlyLedger()
        with self.assertRaises(GridLedgerImportError) as caught:
            import_grid_fills(ledger, document)
        self.assertIn("rejected row", str(caught.exception))
        self.assertEqual(len(ledger.events), 0)

    def test_fee_in_a_non_reporting_asset_is_refused(self):
        ledger = AppendOnlyLedger()
        with self.assertRaises(GridLedgerImportError) as caught:
            import_grid_fills(ledger, _document([_fill(feeAsset="BNB")]))
        self.assertIn("operator-approved mark", str(caught.exception))
        self.assertEqual(len(ledger.events), 0)

    def test_zero_fee_in_another_asset_is_allowed(self):
        ledger = AppendOnlyLedger()
        result = import_grid_fills(ledger, _document([_fill(fee="0", feeAsset="BNB")]))
        self.assertEqual(result.appended, 1)

    def test_unsupported_version_is_refused(self):
        with self.assertRaises(GridLedgerImportError):
            parse_grid_ledger_export(_document(version=2))

    def test_self_inconsistent_export_is_refused(self):
        with self.assertRaises(GridLedgerImportError) as caught:
            parse_grid_ledger_export(_document(sourceRowCount=5))
        self.assertIn("inconsistent with itself", str(caught.exception))

    def test_duplicate_external_id_inside_one_document_is_refused(self):
        with self.assertRaises(GridLedgerImportError) as caught:
            parse_grid_ledger_export(_document([_fill(), _fill()]))
        self.assertIn("duplicated", str(caught.exception))

    def test_naive_timestamp_is_refused(self):
        with self.assertRaises(GridLedgerImportError) as caught:
            parse_grid_ledger_export(_document([_fill(occurredAt="2026-07-20T10:05:00")]))
        self.assertIn("timezone-aware", str(caught.exception))

    def test_non_positive_or_non_finite_numbers_are_refused(self):
        for bad in ({"quantity": "0"}, {"price": "-1"}, {"fee": "-0.01"},
                    {"quantity": "abc"}, {"price": "NaN"}):
            with self.subTest(bad=bad):
                with self.assertRaises(GridLedgerImportError):
                    parse_grid_ledger_export(_document([_fill(**bad)]))

    def test_missing_keys_are_named(self):
        document = _document()
        del document["reportingCurrency"]
        with self.assertRaises(GridLedgerImportError) as caught:
            parse_grid_ledger_export(document)
        self.assertIn("reportingCurrency", str(caught.exception))

        fill = _fill()
        del fill["price"]
        with self.assertRaises(GridLedgerImportError) as caught:
            parse_grid_ledger_export(_document([fill]))
        self.assertIn("price", str(caught.exception))

    def test_a_malformed_document_leaves_the_ledger_untouched(self):
        ledger = AppendOnlyLedger()
        import_grid_fills(ledger, _document())
        before = copy.copy(ledger.events)
        with self.assertRaises(GridLedgerImportError):
            import_grid_fills(
                ledger,
                _document([_fill(externalId="new-1"), _fill(externalId="new-2", price="0")]),
            )
        self.assertEqual(ledger.events, before, "no partial write may survive a failure")

    def test_imported_fills_feed_the_snapshot(self):
        # The whole point: a grid fill must reach P/L, not stop at the bridge.
        ledger = AppendOnlyLedger()
        import_grid_fills(
            ledger,
            _document([
                _fill(),
                _fill(externalId="aegis-BOT-abc-EXE-1-1", side="sell", price="63500.00",
                      occurredAt="2026-07-20T11:00:00Z"),
            ]),
        )
        snapshot = ledger.snapshot({"BTCUSDT": 63500.0})
        self.assertGreater(snapshot.realized_gross_pnl, 0)


class GridLedgerCrossLanguageContractTests(unittest.TestCase):
    """The seam between the TypeScript exporter and this importer.

    The other tests here use hand-written documents, which proves this module is
    strict but not that it agrees with the producer.  This one consumes a golden
    file emitted by ``grid-ledger-export.ts`` itself, so a schema change on
    either side breaks a test instead of silently breaking the track record.
    Regenerate it from the TypeScript exporter, never by hand.
    """

    def setUp(self):
        self.assertTrue(GOLDEN.exists(), f"golden export missing at {GOLDEN}")
        self.document = json.loads(GOLDEN.read_text(encoding="utf-8"))

    def test_the_typescript_exporter_output_imports_unchanged(self):
        ledger = AppendOnlyLedger()
        result = import_grid_fills(ledger, self.document)
        self.assertEqual(result.appended, 2)
        self.assertEqual(result.duplicates, 0)

    def test_a_round_trip_produces_realized_pnl_attributable_to_the_bot(self):
        ledger = AppendOnlyLedger()
        import_grid_fills(ledger, self.document)
        self.assertEqual({event.strategy_id for event in ledger.events}, {"BOT-abc"})
        snapshot = ledger.snapshot({"BTCUSDT": 63510.25})
        # buy 62950.10 -> sell 63510.25 on 0.001 BTC, gross 0.56 USDT.
        self.assertAlmostEqual(snapshot.realized_gross_pnl, 0.56015, places=4)
        # And the fees are the exchange's real commissions, not an estimate.
        self.assertAlmostEqual(sum(event.fee for event in ledger.events), 0.1264, places=4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
