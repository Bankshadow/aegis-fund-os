import tempfile
import unittest
from pathlib import Path

from dynamic_grid.fund_v2_store import (FundV2Store, periods_covering,
                                        reporting_period)


class ReportingPeriodTests(unittest.TestCase):
    def test_month_and_quarter_identifiers(self):
        self.assertEqual(reporting_period("2026-07-15", "month"), "2026-07")
        self.assertEqual(reporting_period("2026-07-15", "quarter"), "2026-Q3")
        self.assertEqual(reporting_period("2026-01-01", "quarter"), "2026-Q1")
        self.assertEqual(reporting_period("2026-12-31", "quarter"), "2026-Q4")

    def test_a_date_belongs_to_both_its_month_and_quarter(self):
        self.assertEqual(periods_covering("2026-07-15"), ("2026-07", "2026-Q3"))

    def test_malformed_input_fails_closed(self):
        for bad in ["2026/07/15", "not-a-date", "2026-13-01", ""]:
            with self.assertRaises(ValueError):
                reporting_period(bad)

    def test_unknown_granularity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "granularity"):
            reporting_period("2026-07-15", "weekly")


class PeriodLockTests(unittest.TestCase):
    def store(self, directory):
        return FundV2Store(Path(directory) / "fund.sqlite")

    def seeded(self, store, dates=("2026-07-15",), lock=True):
        for date in dates:
            store.record_close("main", date, 10_000.0, 100.0, "clean")
            if lock:
                store.lock_close("main", date, "checker")

    def test_locking_a_month_requires_its_daily_closes_to_be_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            store.record_close("main", "2026-07-15", 10_000.0, 100.0, "clean")
            with self.assertRaisesRegex(ValueError, "still unlocked"):
                store.lock_period("main", "2026-07", "approver")
            store.lock_close("main", "2026-07-15", "checker")
            self.assertEqual(store.lock_period("main", "2026-07", "approver"), 1)

    def test_locking_an_empty_period_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "no closes recorded"):
                self.store(directory).lock_period("main", "2026-07", "approver")

    def test_open_exception_blocks_the_period_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            store.record_close("main", "2026-07-15", 10_000.0, 100.0, "provisional")
            store.add_exception("main", "2026-07-15", "USDT", "cash mismatch", "ops")
            # the daily close cannot lock while the exception is open
            with self.assertRaises(ValueError):
                store.lock_close("main", "2026-07-15", "checker")
            with self.assertRaises(ValueError):
                store.lock_period("main", "2026-07", "approver")

    def test_a_sealed_month_blocks_back_dated_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            self.seeded(store)
            store.lock_period("main", "2026-07", "approver")
            # numbers inside the sealed month can no longer move
            with self.assertRaisesRegex(PermissionError, "2026-07 is locked"):
                store.record_close("main", "2026-07-20", 12_000.0, 500.0, "clean")
            with self.assertRaisesRegex(PermissionError, "is locked"):
                store.add_exception("main", "2026-07-20", "BTC", "late find", "ops")
            with self.assertRaisesRegex(PermissionError, "is locked"):
                store.lock_close("main", "2026-07-20", "checker")

    def test_a_sealed_quarter_also_blocks_dates_in_its_other_months(self):
        # Sealing 2026-Q3 must stop a write dated in August, whose month period
        # ("2026-08") was never sealed on its own.
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            self.seeded(store, dates=("2026-07-15",))
            store.lock_period("main", "2026-Q3", "approver")
            with self.assertRaisesRegex(PermissionError, "2026-Q3 is locked"):
                store.record_close("main", "2026-08-10", 11_000.0, 200.0, "clean")

    def test_other_periods_stay_writable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            self.seeded(store)
            store.lock_period("main", "2026-07", "approver")
            store.record_close("main", "2026-09-01", 11_000.0, 200.0, "clean")
            self.assertEqual(len(store.close_history("main")), 2)

    def test_resealing_a_period_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            self.seeded(store)
            store.lock_period("main", "2026-07", "approver")
            with self.assertRaisesRegex(ValueError, "already locked"):
                store.lock_period("main", "2026-07", "someone-else")

    def test_lock_is_recorded_and_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.store(directory)
            self.seeded(store)
            store.lock_period("main", "2026-07", "approver")
            locks = store.locked_periods("main")
            self.assertEqual(len(locks), 1)
            self.assertEqual(locks[0]["period"], "2026-07")
            self.assertEqual(locks[0]["locked_by"], "approver")
            self.assertTrue(locks[0]["locked_at"])


if __name__ == "__main__":
    unittest.main()
