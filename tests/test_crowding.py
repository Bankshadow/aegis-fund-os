"""Invariants for the E39 crowding panel. Run before any result is read.

The load-bearing ones are causality: an 8h funding print must not leak into
earlier bars, and the impulse test must not measure itself.
"""

import unittest

import numpy as np

from dynamic_grid import crowding as cr


def panel(n=200, seed=0):
    rng = np.random.default_rng(seed)
    close = np.abs(100 + np.cumsum(rng.normal(0, 1, n))) + 50
    return cr.Panel(
        times=np.arange(n, dtype=np.int64) * 3_600_000,
        close=close, high=close * 1.002, low=close * 0.998,
        long_short=np.full(n, 1.6), oi_value=np.linspace(1e9, 2e9, n),
        funding=np.full(n, 0.0002),
    )


class ForwardFillTests(unittest.TestCase):

    def test_a_settlement_only_reaches_later_bars(self):
        times = np.arange(10, dtype=np.int64)
        out = cr.forward_fill(times, np.array([3, 7], dtype=np.int64),
                              np.array([0.5, 0.9]))
        self.assertTrue(np.isnan(out[:3]).all(), "bars before the first print must be NaN")
        np.testing.assert_allclose(out[3:7], 0.5)
        np.testing.assert_allclose(out[7:], 0.9)

    def test_a_settlement_exactly_on_a_bar_counts_for_that_bar(self):
        out = cr.forward_fill(np.array([0, 1, 2], dtype=np.int64),
                              np.array([1], dtype=np.int64), np.array([0.4]))
        self.assertTrue(np.isnan(out[0]))
        self.assertAlmostEqual(out[1], 0.4)

    def test_later_settlements_cannot_change_earlier_bars(self):
        times = np.arange(20, dtype=np.int64)
        base = cr.forward_fill(times, np.array([2, 9], dtype=np.int64), np.array([0.1, 0.2]))
        more = cr.forward_fill(times, np.array([2, 9, 15], dtype=np.int64),
                               np.array([0.1, 0.2, 9.9]))
        np.testing.assert_allclose(base[:15], more[:15], equal_nan=True)


class AtrTests(unittest.TestCase):

    def test_atr_excludes_the_current_bar(self):
        # A huge bar at i must not raise its own threshold.
        n = 40
        close = np.full(n, 100.0)
        high, low = close.copy(), close.copy()
        high[30] = 500.0
        band = cr.atr_prior(high, low, close)
        self.assertAlmostEqual(band[30], 0.0, places=9,
                               msg="bar 30's own range leaked into its ATR")
        self.assertGreater(band[31], 0.0)

    def test_atr_is_nan_until_the_window_is_full(self):
        band = cr.atr_prior(*[np.linspace(100, 120, 30)] * 3)
        self.assertTrue(np.isnan(band[:cr.ATR_PERIOD]).all())

    def test_atr_is_causal(self):
        rng = np.random.default_rng(1)
        close = np.abs(100 + np.cumsum(rng.normal(0, 1, 200))) + 20
        base = cr.atr_prior(close * 1.01, close * 0.99, close)
        tampered = close.copy()
        tampered[150:] *= 5
        after = cr.atr_prior(tampered * 1.01, tampered * 0.99, tampered)
        np.testing.assert_allclose(base[:150], after[:150], equal_nan=True)


class SignalTests(unittest.TestCase):

    def test_full_is_a_subset_of_every_single_factor_arm(self):
        rng = np.random.default_rng(2)
        p = panel(400, seed=3)
        p.long_short[:] = rng.uniform(1.0, 2.0, len(p))
        p.funding[:] = rng.uniform(0.0, 0.0003, len(p))
        s = cr.signals(p)
        for weaker in ("S_fund", "S_ls", "S_oi", "S_imp"):
            self.assertTrue(np.all(s["S_full"] <= s[weaker]),
                            f"S_full is not a subset of {weaker}")

    def test_nan_inputs_never_fire_a_signal(self):
        p = panel(200)
        p.long_short[:50] = np.nan
        p.funding[:50] = np.nan
        s = cr.signals(p)
        self.assertFalse(s["S_full"][:50].any())
        self.assertFalse(s["S_fund"][:50].any())

    def test_oi_expansion_needs_a_full_24_bar_lookback(self):
        p = panel(60)
        self.assertFalse(cr.oi_expanding(p)[:cr.OI_LOOKBACK].any())

    def test_thresholds_are_the_declared_ones(self):
        self.assertEqual(cr.LS_THRESHOLD, 1.50)
        self.assertEqual(cr.FUNDING_THRESHOLD, 0.0001)
        self.assertEqual(cr.OI_LOOKBACK, 24)
        self.assertEqual(cr.IMPULSE_ATR_MULT, 0.5)


class FadeTests(unittest.TestCase):

    def test_fade_is_positive_when_price_falls(self):
        close = np.array([100.0, 90.0, 80.0])
        np.testing.assert_allclose(cr.fade(close, 1)[0], 0.10)

    def test_fade_is_negative_when_price_rises(self):
        close = np.array([100.0, 110.0, 120.0])
        self.assertAlmostEqual(cr.fade(close, 1)[0], -0.10)

    def test_the_tail_has_no_forward_window(self):
        self.assertTrue(np.isnan(cr.fade(np.arange(1, 11, dtype=float), 4)[-4:]).all())


class PermutationTests(unittest.TestCase):

    def test_a_real_gap_scores_high(self):
        rng = np.random.default_rng(4)
        a = rng.normal(0.05, 0.01, 200)
        b = rng.normal(0.00, 0.01, 200)
        self.assertGreater(cr.label_permutation_percentile(a, b, draws=2000), 0.95)

    def test_two_samples_from_one_distribution_score_near_the_middle(self):
        rng = np.random.default_rng(5)
        pool = rng.normal(0, 0.01, 400)
        p = cr.label_permutation_percentile(pool[:200], pool[200:], draws=2000)
        self.assertGreater(p, 0.05)
        self.assertLess(p, 0.95)

    def test_an_empty_group_is_not_scored(self):
        self.assertTrue(np.isnan(cr.label_permutation_percentile(
            np.array([]), np.array([1.0, 2.0]))))


if __name__ == "__main__":
    unittest.main()
