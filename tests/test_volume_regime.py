"""Invariants for the E36 volume-regime measurement.

Load-bearing: classification at bar i must not use volume/close/ATR from the
future. If that breaks, the study sees tomorrow and manufactures an edge.
"""

import unittest

import numpy as np

from dynamic_grid import volume_regime as v


def make_ohlcv(n=80, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    close = np.abs(close) + 10
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    quote = rng.uniform(1e8, 2e8, n)
    return high, low, close, quote


class AtrTests(unittest.TestCase):

    def test_atr_at_i_ignores_bar_i_and_beyond(self):
        high, low, close, _ = make_ohlcv(40)
        atr = v.atr_sma(high, low, close, 14)
        self.assertTrue(np.isnan(atr[13]))
        self.assertFalse(np.isnan(atr[14]))
        # Tamper the future; atr through bar 20 must be unchanged.
        atr_before = atr[:21].copy()
        high2, low2, close2 = high.copy(), low.copy(), close.copy()
        high2[21:] *= 5
        low2[21:] *= 0.2
        close2[21:] *= 3
        atr2 = v.atr_sma(high2, low2, close2, 14)
        np.testing.assert_allclose(atr_before, atr2[:21], equal_nan=True)


class ClassifyTests(unittest.TestCase):

    def test_increasing_needs_strictly_rising_window(self):
        n = 40
        high = np.full(n, 110.0)
        low = np.full(n, 90.0)
        close = np.linspace(100, 120, n)
        quote = np.full(n, 1e8)
        # Last 5 volumes strictly rising at i=30
        quote[26:31] = [1e8, 1.1e8, 1.2e8, 1.3e8, 1.4e8]
        atr = v.atr_sma(high, low, close, 14)
        self.assertEqual(v.classify_bar(quote, close, atr, 30, 5), "INCREASING")

    def test_spike_requires_both_volume_and_price(self):
        n = 40
        high = np.full(n, 110.0)
        low = np.full(n, 90.0)
        close = np.full(n, 100.0)
        quote = np.full(n, 1e8)
        # Big volume alone at i=30, flat price → not SPIKE
        quote[30] = 5e8
        atr = v.atr_sma(high, low, close, 14)
        # close[30]==close[29] → None (no direction)
        self.assertIsNone(v.classify_bar(quote, close, atr, 30, 5))
        # Price moves a tiny bit: still not 1 ATR
        close = close.copy()
        close[30] = 100.5
        high = np.maximum(high, close)
        atr = v.atr_sma(high, low, close, 14)
        label = v.classify_bar(quote, close, atr, 30, 5)
        self.assertNotEqual(label, "SPIKE")

    def test_spike_fires_when_both_thresholds_met(self):
        n = 40
        close = np.full(n, 100.0)
        # Build ATR ~ 2 via wide ranges historically
        high = np.full(n, 101.0)
        low = np.full(n, 99.0)
        for i in range(n):
            high[i] = 102.0
            low[i] = 98.0
        quote = np.full(n, 1e8)
        # 3 ATR price jump and 3x volume
        close = close.copy()
        close[30] = 100 + 8.0   # ATR SMA of TR~4 → need >= 4 move in log≈level terms
        high[30] = close[30]
        quote[30] = 4e8
        atr = v.atr_sma(high, low, close, 14)
        # Ensure atr is finite and threshold reachable
        self.assertTrue(np.isfinite(atr[30]))
        self.assertEqual(v.classify_bar(quote, close, atr, 30, 5), "SPIKE")

    def test_future_volume_cannot_change_past_labels(self):
        high, low, close, quote = make_ohlcv(100, seed=3)
        labels = v.classify_series(quote, close, high, low, 10)
        cut = 60
        before = labels[:cut]
        quote2 = quote.copy()
        quote2[cut:] *= 10
        close2 = close.copy()
        close2[cut:] *= 1.5
        after = v.classify_series(quote2, close2, high, low, 10)[:cut]
        self.assertEqual(before, after)

    def test_partition_is_exclusive(self):
        high, low, close, quote = make_ohlcv(120, seed=5)
        labels = v.classify_series(quote, close, high, low, 10)
        for lab in labels:
            if lab is not None:
                self.assertIn(lab, v.REGIMES)

    def test_observations_never_look_past_i_plus_h(self):
        high, low, close, quote = make_ohlcv(100, seed=7)
        obs = v.observations(quote, close, high, low, 10, horizons=(5,))
        for rows in obs.values():
            for row in rows:
                self.assertLessEqual(row.index + 5, len(close) - 1)


class BootstrapTests(unittest.TestCase):

    def test_identical_groups_have_zero_diff(self):
        # All scores equal → observed diff is exactly 0 (percentile is moot:
        # every shuffle draw is also 0, so strict < gives 0.0).
        rows = [
            v.BarLabel(i, "INCREASING", 1, {10: 0.01}, {10: -0.01})
            for i in range(40)
        ]
        rng = np.random.default_rng(0)
        out = v.bootstrap_diff_percentile(rows[:20], rows[20:], 10,
                                          "continuation", 2000, rng)
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out["diff"], 0.0, places=12)
        self.assertEqual(out["a_mean"], out["b_mean"])


if __name__ == "__main__":
    unittest.main()
