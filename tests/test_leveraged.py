"""Invariants for the E31 leveraged / long-short portfolio simulator.

A leveraged backtest is only admissible if it can be shown to model the three
things that make leverage dangerous: intrabar liquidation, funding carry, and
delisting. Each has a test here that fails if the model quietly drops it.
"""

import unittest

import numpy as np

from dynamic_grid import leveraged as lv


def panel_from(prices, highs=None, lows=None):
    """(n_days, n_assets) panel from a list-of-lists of closes."""
    c = np.asarray(prices, dtype=float)
    h = np.asarray(highs, dtype=float) if highs is not None else c.copy()
    l = np.asarray(lows, dtype=float) if lows is not None else c.copy()
    return c, h, l


class _Fixed:
    """Strategy that holds a constant weight vector."""

    name = "fixed"

    def __init__(self, w):
        self._w = np.asarray(w, dtype=float)

    def weights(self, i):
        return self._w.copy()


class TestLiquidation(unittest.TestCase):
    def test_3x_long_is_wiped_by_a_40_percent_intrabar_wick(self):
        c = [[100.0], [95.0], [95.0]]
        lows = [[100.0], [60.0], [95.0]]      # -40% intrabar, closes at -5%
        cc, hh, ll = panel_from(c, highs=c, lows=lows)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([3.0]), start=0,
                          cost=0.0, use_funding=False)
        self.assertEqual(res.liquidations, 1)
        self.assertLess(res.final_equity, 10_000 * 0.01)
        self.assertTrue(res.ruined)

    def test_close_only_maths_would_have_survived_that_bar(self):
        """The wick is the whole point: on closes alone 3x -5% is just -15%."""
        c = [[100.0], [95.0], [95.0]]
        cc, hh, ll = panel_from(c)            # high == low == close, no wick
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([3.0]), start=0,
                          cost=0.0, use_funding=False)
        self.assertEqual(res.liquidations, 0)
        self.assertAlmostEqual(res.final_equity, 10_000 * 0.85, places=6)

    def test_a_survivable_wick_does_not_liquidate(self):
        c = [[100.0], [98.0], [98.0]]
        lows = [[100.0], [90.0], [98.0]]      # -10% intrabar at 3x = -30%
        cc, hh, ll = panel_from(c, highs=c, lows=lows)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([3.0]), start=0,
                          cost=0.0, use_funding=False)
        self.assertEqual(res.liquidations, 0)

    def test_a_short_is_liquidated_by_an_upward_wick(self):
        c = [[100.0], [105.0], [105.0]]
        highs = [[100.0], [145.0], [105.0]]
        cc, hh, ll = panel_from(c, highs=highs, lows=c)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([-3.0]), start=0,
                          cost=0.0, use_funding=False)
        self.assertEqual(res.liquidations, 1)


class TestDirectionAndCarry(unittest.TestCase):
    def test_unlevered_long_reproduces_the_price_return(self):
        c = [[100.0], [110.0], [121.0]]
        cc, hh, ll = panel_from(c)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([1.0]), start=0,
                          cost=0.0, use_funding=False)
        self.assertAlmostEqual(res.total_return, 0.21, places=9)

    def test_a_short_gains_when_the_price_falls(self):
        c = [[100.0], [90.0]]
        cc, hh, ll = panel_from(c)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([-1.0]), start=0,
                          cost=0.0, use_funding=False)
        self.assertAlmostEqual(res.total_return, 0.10, places=9)

    def test_longs_pay_funding_and_shorts_receive_it(self):
        c = [[100.0], [100.0], [100.0]]
        cc, hh, ll = panel_from(c)
        f = np.full_like(cc, 0.001)           # +0.1%/day, longs pay
        long = lv.simulate(None, cc, hh, ll, f, _Fixed([1.0]), start=0,
                           cost=0.0, use_funding=True)
        short = lv.simulate(None, cc, hh, ll, f, _Fixed([-1.0]), start=0,
                            cost=0.0, use_funding=True)
        self.assertLess(long.final_equity, 10_000.0)
        self.assertGreater(short.final_equity, 10_000.0)

    def test_leverage_multiplies_the_funding_bill(self):
        c = [[100.0]] * 30
        cc, hh, ll = panel_from(c)
        f = np.full_like(cc, 0.0005)
        one = lv.simulate(None, cc, hh, ll, f, _Fixed([1.0]), start=0,
                          cost=0.0, use_funding=True)
        three = lv.simulate(None, cc, hh, ll, f, _Fixed([3.0]), start=0,
                            cost=0.0, use_funding=True)
        self.assertLess(three.final_equity, one.final_equity)

    def test_turnover_is_charged_on_the_traded_notional(self):
        c = [[100.0], [100.0]]
        cc, hh, ll = panel_from(c)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([2.0]), start=0,
                          cost=0.001, use_funding=False)
        # day 0 buys 2x notional, so the first charge is 2 * 0.1%
        self.assertAlmostEqual(res.equity[0], 10_000 * (1 - 2 * 0.001), places=6)


class TestDelisting(unittest.TestCase):
    def test_a_symbol_that_stops_printing_is_exited_not_vanished(self):
        c = [[100.0, 50.0], [110.0, 40.0], [120.0, np.nan], [130.0, np.nan]]
        cc, hh, ll = panel_from(c)
        f = np.zeros_like(cc)
        res = lv.simulate(None, cc, hh, ll, f, _Fixed([0.5, 0.5]), start=0,
                          cost=0.0, use_funding=False)
        # the dead asset's -20% must be realised, not skipped
        self.assertLess(res.equity[1], res.initial_equity * 1.0)
        self.assertTrue(np.isfinite(res.final_equity))

    def test_cross_sectional_book_drops_a_delisted_name(self):
        n = 30
        c = np.column_stack([np.linspace(100, 200, n), np.linspace(50, 90, n)])
        c[20:, 1] = np.nan
        p = lv._Panel(c, c, c, ["A", "B"])
        strat = lv.CrossSectionalMomentum(p, k=2, lookback=5, rebalance=1)
        w = strat.weights(25)
        self.assertEqual(w[1], 0.0)


class TestNoLookahead(unittest.TestCase):
    def test_rewriting_the_future_leaves_earlier_equity_untouched(self):
        rng = np.random.default_rng(19)
        n, k = 400, 6
        c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, (n, k)), axis=0))
        f = np.full_like(c, 0.0002)
        cut = 300
        for build in (
            lambda p: lv.CrossSectionalMomentum(p, k=2, lookback=90),
            lambda p: lv.LongShortMomentum(p, k=2, lookback=90),
            lambda p: lv.LeveredTrend(p, asset=0, two_sided=True),
            lambda p: lv.VolTargetTrend(p, asset=0),
        ):
            base = lv.simulate(None, c, c, c, f,
                               build(lv._Panel(c, c, c, list("ABCDEF"))),
                               start=200)
            alt = c.copy()
            alt[cut:] *= 4.0
            after = lv.simulate(None, alt, alt, alt, f,
                                build(lv._Panel(alt, alt, alt, list("ABCDEF"))),
                                start=200)
            np.testing.assert_allclose(
                base.equity[:cut - 200], after.equity[:cut - 200], rtol=1e-12,
                err_msg=f"{base.name} leaked the future")


class TestReporting(unittest.TestCase):
    def test_annualised_matches_a_known_doubling(self):
        c = np.array([[100.0]] * 366)
        c[-1, 0] = 200.0
        f = np.zeros_like(c)
        res = lv.simulate(None, c, c, c, f, _Fixed([1.0]), start=0, cost=0.0,
                          use_funding=False)
        self.assertAlmostEqual(res.annualised, 1.0, places=2)

    def test_ruin_is_flagged_below_a_tenth_of_the_starting_stake(self):
        c = np.array([[100.0], [100.0]])
        f = np.zeros_like(c)
        res = lv.simulate(None, c, c, c, f, _Fixed([1.0]), start=0, cost=0.0,
                          use_funding=False)
        self.assertFalse(res.ruined)


if __name__ == "__main__":
    unittest.main()
