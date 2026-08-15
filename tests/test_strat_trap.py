"""Invariants for the E44 S003 engine. Run before any result is read.

The two rules that silently inflate a fade backtest are the entry-bar exemption
and the optimistic intrabar model, so most of these pin exactly those.
"""

import unittest

import numpy as np

from dynamic_grid import strat_trap as st


def bars(rows):
    """rows = [(date, open, high, low, close), ...]"""
    dates = [r[0] for r in rows]
    a = np.array([[r[1], r[2], r[3], r[4]] for r in rows], dtype=float)
    return dates, a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def flat_prefix(n, price=100.0, start_day=1):
    """Warm-up filler that produces inside bars (no signal)."""
    return [(f"2024-01-{start_day + i:02d}" if start_day + i < 32
             else f"2024-02-{start_day + i - 31:02d}",
             price, price + 1, price - 1, price) for i in range(n)]


class ClassificationTests(unittest.TestCase):

    def test_inside_outside_and_breaks(self):
        _, o, h, l, c = bars([("d1", 10, 20, 10, 15),
                              ("d2", 10, 19, 11, 15),   # inside
                              ("d3", 10, 25, 5, 15),    # outside
                              ("d4", 10, 30, 6, 15),    # 2U (h>h1, l>=l1)
                              ("d5", 10, 29, 5, 15)])   # 2D (l<l1, h<=h1)
        self.assertEqual(st.strat_type(h, l)[1:], ["1", "3", "2U", "2D"])

    def test_the_first_bar_has_no_classification(self):
        _, o, h, l, c = bars([("d1", 1, 2, 0, 1), ("d2", 1, 3, 0, 1)])
        self.assertIsNone(st.strat_type(h, l)[0])


class StopTests(unittest.TestCase):

    def setUp(self):
        self.dates = ["d0", "d1"]
        self.atr = np.array([np.nan, 10.0])

    def plan(self, side, high, low, close):
        o = np.array([0.0, close]); h = np.array([0.0, high])
        l = np.array([0.0, low]); c = np.array([0.0, close])
        return st.plan_trade("X", 1, self.dates, o, h, l, c, self.atr, side)

    def test_long_stop_sits_below_the_low_by_the_buffer(self):
        t = self.plan(+1, high=110.0, low=95.0, close=100.0)
        self.assertAlmostEqual(t.stop, 95.0 - 0.25 * 10.0)
        self.assertAlmostEqual(t.r, 100.0 - t.stop)

    def test_a_tight_bar_is_floored_to_half_an_atr(self):
        # low is only 1 away, so the 0.5*ATR floor must bind.
        t = self.plan(+1, high=101.0, low=99.0, close=100.0)
        self.assertAlmostEqual(t.stop, 100.0 - 0.5 * 10.0)

    def test_short_stop_sits_above_the_high(self):
        t = self.plan(-1, high=105.0, low=90.0, close=100.0)
        self.assertAlmostEqual(t.stop, 105.0 + 0.25 * 10.0)
        self.assertAlmostEqual(t.r, t.stop - 100.0)

    def test_a_trade_wider_than_three_atr_is_skipped(self):
        self.assertIsNone(self.plan(+1, high=110.0, low=60.0, close=100.0))

    def test_targets_are_one_two_three_r_in_the_trade_direction(self):
        t = self.plan(+1, high=110.0, low=95.0, close=100.0)
        self.assertAlmostEqual(t.tp1, 100.0 + t.r)
        self.assertAlmostEqual(t.tp3, 100.0 + 3 * t.r)
        s = self.plan(-1, high=105.0, low=90.0, close=100.0)
        self.assertAlmostEqual(s.tp3, 100.0 - 3 * s.r)


class ManagementTests(unittest.TestCase):

    # A 2D bar that stays inside the 3xATR risk cap: low dips under the prior
    # low but not far, so R ~ 2.5 against ATR ~ 2. A deeper wick would be
    # skipped by the spec's own max_risk_atr rule, which is what an earlier
    # version of this fixture got wrong.
    SIGNAL = ("2024-09-01", 99.0, 100.5, 98.0, 100.0)

    def signal_then(self, following):
        rows = flat_prefix(st.WARMUP + 1)
        rows.append(self.SIGNAL)
        rows.extend(following)
        return bars(rows)

    def planned(self):
        dates, o, h, l, c = self.signal_then([("2024-09-02", 100, 100.2, 99.8, 100)])
        return st.run_symbol("X", dates, o, h, l, c).trades[0]

    def test_the_signal_bar_can_never_reach_its_own_stop(self):
        # Structural, not incidental: the stop is placed at least 0.25*ATR
        # BELOW the signal bar's low, so "do not manage the entry bar" can never
        # be violated by a stop-out on that bar.
        t = self.planned()
        self.assertLess(t.stop, 98.0)

    def test_no_trade_ever_opens_and_closes_on_the_same_bar(self):
        rng = np.random.default_rng(1)
        n = 800
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, n))) + 50
        o = close * (1 + rng.normal(0, 0.01, n))
        h = np.maximum(o, close) * (1 + np.abs(rng.normal(0, 0.02, n)))
        l = np.minimum(o, close) * (1 - np.abs(rng.normal(0, 0.02, n)))
        dates = [f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
        res = st.run_symbol("X", dates, o, h, l, close)
        self.assertTrue(res.trades, "the fixture must produce trades")
        for t in res.closed:
            self.assertGreater(t.exit_bar, t.entry_bar)

    def test_tp3_closes_the_trade_at_three_r(self):
        r = self.planned().r
        target = 100.0 + 3 * r
        dates, o, h, l, c = self.signal_then(
            [("2024-09-02", 100, target + 1, 99.5, target)])
        t = st.run_symbol("X", dates, o, h, l, c).trades[0]
        self.assertEqual(t.reason, "TP3")
        self.assertAlmostEqual(t.pnl_r_gross, 3.0, places=9)

    def test_a_stop_out_books_minus_one_r_gross(self):
        stop = self.planned().stop
        dates, o, h, l, c = self.signal_then(
            [("2024-09-02", 100, 100.2, stop - 1, stop - 0.5)])
        t = st.run_symbol("X", dates, o, h, l, c).trades[0]
        self.assertEqual(t.reason, "SL")
        self.assertAlmostEqual(t.pnl_r_gross, -1.0, places=9)

    def test_touching_tp2_moves_the_stop_to_entry(self):
        base = self.planned()
        tp2, tp3 = base.tp2, base.tp3
        dates, o, h, l, c = self.signal_then([
            ("2024-09-02", 100, tp2 + 0.01, 99.9, tp2),      # arms BE, not TP3
            ("2024-09-03", 100, 100.1, base.stop - 5, 95.0),  # would have been SL
        ])
        self.assertLess(tp2 + 0.01, tp3)
        t = st.run_symbol("X", dates, o, h, l, c).trades[0]
        self.assertTrue(t.be_armed)
        self.assertEqual(t.reason, "BE_SL")
        self.assertAlmostEqual(t.pnl_r_gross, 0.0, places=9)

    def test_a_bar_that_arms_be_does_not_also_stop_out_under_tp_first(self):
        # Spec 5.7. The bar tags TP2 and dips below entry in the same candle.
        base = self.planned()
        dates, o, h, l, c = self.signal_then(
            [("2024-09-02", 100, base.tp2 + 0.01, base.entry - 1, 100.0)])
        t = st.run_symbol("X", dates, o, h, l, c).trades[0]
        self.assertTrue(t.be_armed)
        self.assertEqual(t.reason, "EOD", "it should survive the arming bar")

    def test_optimistic_and_pessimistic_models_disagree_on_a_both_bar(self):
        base = self.planned()
        dates, o, h, l, c = self.signal_then(
            [("2024-09-02", 100, base.tp3 + 1, base.stop - 1, 100.0)])
        opt = st.run_symbol("X", dates, o, h, l, c, intrabar="tp_first").trades[0]
        pes = st.run_symbol("X", dates, o, h, l, c, intrabar="sl_first").trades[0]
        self.assertEqual(opt.reason, "TP3")
        # A bar wide enough to span TP3 also spans TP2, so BE arms first and the
        # pessimistic exit lands on the moved stop, not the original one.
        self.assertEqual(pes.reason, "BE_SL")
        self.assertGreater(opt.pnl_r_gross, pes.pnl_r_gross)

    def test_a_tp3_bar_always_arms_break_even_first(self):
        # Why `sl_first` never actually races TP3 against the ORIGINAL stop:
        # TP2 lies between the entry and TP3, so reaching TP3 tags TP2 on the
        # same bar and the stop has already moved to break-even. E56 reported
        # this as an empirical zero; it is structural. Pinned so the docstring
        # on manage_bar cannot drift away from the code.
        base = self.planned()
        dates, o, h, l, c = self.signal_then(
            [("2024-09-02", 100, base.tp3 + 1, base.stop - 1, 100.0)])
        t = st.run_symbol("X", dates, o, h, l, c, intrabar="sl_first").trades[0]
        self.assertTrue(t.be_armed)
        self.assertEqual(t.reason, "BE_SL")
        self.assertAlmostEqual(t.exit_price, t.entry, places=9,
                               msg="it must be the break-even stop, not the original")

    def test_without_the_be_rule_sl_first_really_is_a_tp_vs_stop_race(self):
        # The half of the name that is still true: turn break-even off and the
        # tie-break governs the ORIGINAL stop, which is why the mode is not
        # renamed to something break-even flavoured.
        flat = st.Params(be_rule="none")
        quiet = self.signal_then([("2024-09-02", 100, 100.2, 99.8, 100)])
        base = st.run_symbol("X", *quiet, params=flat).trades[0]
        dates, o, h, l, c = self.signal_then(
            [("2024-09-02", 100, base.tp3 + 1, base.stop - 1, 100.0)])
        opt = st.run_symbol("X", dates, o, h, l, c, intrabar="tp_first",
                            params=flat).trades[0]
        pes = st.run_symbol("X", dates, o, h, l, c, intrabar="sl_first",
                            params=flat).trades[0]
        self.assertEqual(opt.reason, "TP3")
        self.assertEqual(pes.reason, "SL")
        self.assertFalse(pes.be_armed)
        self.assertAlmostEqual(pes.exit_price, base.stop, places=9)

    def test_an_open_trade_at_the_end_is_marked_eod(self):
        t = self.planned()
        self.assertEqual(t.reason, "EOD")

    def test_a_trade_wider_than_three_atr_is_skipped_in_the_full_run(self):
        # The fixture bug this test was born from: a deep 2D wick looks like a
        # perfect signal but the spec's risk cap throws it away.
        rows = flat_prefix(st.WARMUP + 1)
        rows.append(("2024-09-01", 100.0, 100.5, 90.0, 101.0))   # 2D but far too wide
        dates, o, h, l, c = bars(rows + [("2024-09-02", 101, 101.2, 100.8, 101)])
        self.assertEqual(st.run_symbol("X", dates, o, h, l, c).trades, [])


class EntryRuleTests(unittest.TestCase):

    # Both kept inside the 3xATR risk cap, like ManagementTests.SIGNAL.
    RED_2U = ("2024-09-01", 101.0, 102.0, 99.5, 100.0)
    GREEN_2D = ("2024-09-01", 99.0, 100.5, 98.0, 100.0)

    def run_with(self, row):
        dates, o, h, l, c = bars(flat_prefix(st.WARMUP + 1) + [row]
                                 + [("2024-09-02", 100, 100.2, 99.8, 100)])
        return st.run_symbol("X", dates, o, h, l, c)

    def test_a_red_2u_goes_short_and_a_green_2d_goes_long(self):
        self.assertEqual(self.run_with(self.RED_2U).trades[0].side, -1)
        self.assertEqual(self.run_with(self.GREEN_2D).trades[0].side, +1)

    def test_a_green_2u_and_a_red_2d_produce_nothing(self):
        for row in (("2024-09-01", 99.0, 102.0, 99.5, 101.0),    # 2U green
                    ("2024-09-01", 101.0, 100.5, 98.0, 99.0)):   # 2D red
            self.assertEqual(self.run_with(row).trades, [])

    def test_a_doji_is_skipped(self):
        self.assertEqual(self.run_with(("2024-09-01", 100.0, 100.5, 98.0, 100.0)).trades, [])

    def test_no_signal_fires_before_the_warmup(self):
        rows = flat_prefix(50)
        rows.append(("2024-03-01", 99.0, 100.5, 98.0, 100.0))
        dates, o, h, l, c = bars(rows + [("2024-03-02", 100, 100.2, 99.8, 100)])
        self.assertEqual(st.run_symbol("X", dates, o, h, l, c).trades, [])

    def test_only_one_position_is_open_per_asset(self):
        rng = np.random.default_rng(0)
        n = 600
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, n))) + 50
        o = close * (1 + rng.normal(0, 0.005, n))
        h = np.maximum(o, close) * 1.02
        l = np.minimum(o, close) * 0.98
        dates = [f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
        res = st.run_symbol("X", dates, o, h, l, close)
        for a, b in zip(res.trades, res.trades[1:]):
            self.assertGreaterEqual(b.entry_bar, a.exit_bar)


class FeeTests(unittest.TestCase):

    def test_fees_are_charged_in_r_units_both_sides(self):
        t = st.Trade(symbol="X", side=1, entry_bar=0, entry_date="d", entry=100.0,
                     stop=90.0, r=10.0, tp1=110.0, tp2=120.0, tp3=130.0)
        st.close_trade(t, 1, ["d0", "d1"], 130.0, "TP3")
        self.assertAlmostEqual(t.fee_r, (2 * st.FEE_SIDE * 100.0) / 10.0)
        self.assertAlmostEqual(t.pnl_r_net, 3.0 - t.fee_r)


class FoldTests(unittest.TestCase):

    BOUNDS = ("2024-08-01", "2025-02-01", "2025-08-01", "2026-08-01")

    def test_dates_land_in_the_declared_folds(self):
        self.assertEqual(st.fold_of("2024-09-15", self.BOUNDS), 0)
        self.assertEqual(st.fold_of("2025-03-01", self.BOUNDS), 1)
        self.assertEqual(st.fold_of("2026-07-31", self.BOUNDS), 2)

    def test_dates_outside_the_folds_are_excluded(self):
        self.assertEqual(st.fold_of("2024-05-01", self.BOUNDS), -1)
        self.assertEqual(st.fold_of("2026-08-05", self.BOUNDS), -1)


if __name__ == "__main__":
    unittest.main()
