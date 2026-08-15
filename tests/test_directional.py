"""Invariants for the E30 directional backtester.

These pin the properties that make the numbers admissible as evidence:
no lookahead, adversarial intrabar ordering, and costs on both legs.
"""

import unittest

import numpy as np

from dynamic_grid import directional as d
from dynamic_grid.indicators import ATR


def _bars(closes, spread=0.0):
    """Build an (n,4) OHLC array from a close series."""
    c = np.asarray(closes, dtype=float)
    return np.column_stack([c, c + spread, c - spread, c])


class TestIndicators(unittest.TestCase):
    def test_atr_matches_streaming_implementation(self):
        rng = np.random.default_rng(7)
        c = 100 + np.cumsum(rng.normal(0, 1, 200))
        h, l = c + 2, c - 2
        vec = d.atr_series(h, l, c, period=14)
        stream = ATR(14)
        for i in range(len(c)):
            stream.update(h[i], l[i], c[i])
            if stream.value is not None:
                self.assertAlmostEqual(vec[i], stream.value, places=9)

    def test_rolling_max_excludes_current_bar(self):
        v = np.array([1.0, 5.0, 2.0, 9.0, 3.0])
        out = d.rolling_max_prev(v, 2)
        self.assertTrue(np.isnan(out[0]) and np.isnan(out[1]))
        self.assertEqual(out[2], 5.0)   # max(1,5), 2 itself excluded
        self.assertEqual(out[3], 5.0)   # max(5,2)
        self.assertEqual(out[4], 9.0)   # max(2,9)

    def test_rsi_bounds_and_monotone_series(self):
        up = d.rsi_series(np.arange(1, 60, dtype=float))
        self.assertAlmostEqual(up[-1], 100.0, places=6)
        down = d.rsi_series(np.arange(60, 1, -1, dtype=float))
        self.assertAlmostEqual(down[-1], 0.0, places=6)


class TestNoLookahead(unittest.TestCase):
    def test_rewriting_the_future_cannot_change_past_trades(self):
        rng = np.random.default_rng(11)
        c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, 600)))
        bars = _bars(c, spread=1.0)
        cut = 400
        for name in d.CANDIDATES:
            base = d.run(bars, name, start=250)
            altered = bars.copy()
            altered[cut:, :] *= 3.0  # a completely different future
            after = d.run(altered, name, start=250)
            past_base = [t for t in base.trades if t.exit_idx < cut]
            past_after = [t for t in after.trades if t.exit_idx < cut]
            self.assertEqual(
                [(t.entry_idx, t.exit_idx, round(t.entry_price, 6),
                  round(t.exit_price, 6)) for t in past_base],
                [(t.entry_idx, t.exit_idx, round(t.entry_price, 6),
                  round(t.exit_price, 6)) for t in past_after],
                msg=f"{name} leaked future information",
            )


class TestAdversarialFills(unittest.TestCase):
    def _one_position(self, bars, stop, target, entry_i=0):
        class Sig(d._Base):
            def __init__(self):
                self.stop = None
                self.target = None

            def entry(self, i):
                return i == entry_i

            def on_entry(self, i, price):
                self.stop, self.target = stop, target

        return d._simulate(bars, 0, Sig(), 10_000.0, "probe")

    def test_bar_touching_stop_and_target_books_the_stop(self):
        bars = np.array([
            [100.0, 100.0, 100.0, 100.0],
            [100.0, 130.0, 80.0, 120.0],   # touches both 90 and 120
            [120.0, 120.0, 120.0, 120.0],
        ])
        res = self._one_position(bars, stop=90.0, target=120.0)
        self.assertEqual(res.trades[0].reason, "stop")
        self.assertEqual(res.trades[0].exit_price, 90.0)

    def test_gap_through_stop_fills_at_the_open_not_the_stop(self):
        bars = np.array([
            [100.0, 100.0, 100.0, 100.0],
            [70.0, 75.0, 65.0, 70.0],      # gapped straight through 90
            [70.0, 70.0, 70.0, 70.0],
        ])
        res = self._one_position(bars, stop=90.0, target=None)
        self.assertEqual(res.trades[0].exit_price, 70.0)

    def test_gap_through_target_fills_at_the_open_not_the_target(self):
        bars = np.array([
            [100.0, 100.0, 100.0, 100.0],
            [140.0, 145.0, 138.0, 142.0],  # gapped above the 120 target
            [142.0, 142.0, 142.0, 142.0],
        ])
        res = self._one_position(bars, stop=None, target=120.0)
        self.assertEqual(res.trades[0].exit_price, 140.0)


class TestCosts(unittest.TestCase):
    def test_both_legs_are_charged(self):
        bars = _bars([100.0] * 5)
        res = d.run(bars, "B0_buy_hold", start=0)
        # flat price, so the whole loss is the round trip
        expected = (1 - d.COST_PER_SIDE) / (1 + d.COST_PER_SIDE) - 1.0
        self.assertAlmostEqual(res.total_return, expected, places=9)
        self.assertAlmostEqual(res.trades[0].net_return, expected, places=9)
        self.assertLess(res.final_equity, 10_000.0)

    def test_expectancy_matches_mean_net_trade(self):
        rng = np.random.default_rng(3)
        c = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.03, 800)))
        res = d.run(_bars(c, spread=0.5), "M2_donchian20_3R", start=250)
        self.assertGreater(res.n_trades, 0)
        self.assertAlmostEqual(
            res.expectancy,
            float(np.mean([t.net_return for t in res.trades])), places=12)
        if res.wins and res.losses:
            self.assertAlmostEqual(res.rr, res.avg_win / res.avg_loss, places=12)


class TestWarmup(unittest.TestCase):
    def test_warmup_bars_book_no_trade_and_leave_the_curve_alone(self):
        rng = np.random.default_rng(5)
        c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 500)))
        bars = _bars(c, spread=0.5)
        res = d.run(bars, "M3_sma200_hold", start=300)
        self.assertEqual(len(res.equity), 200)
        self.assertTrue(all(t.entry_idx >= 300 for t in res.trades))


if __name__ == "__main__":
    unittest.main()
