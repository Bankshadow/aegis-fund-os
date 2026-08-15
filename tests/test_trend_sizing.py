"""Invariants for the E39 sizing layer. Run before any result is read."""

import unittest

import numpy as np

from dynamic_grid import trend_sizing as ts


class StrengthTests(unittest.TestCase):

    def test_raw_strength_is_nan_until_the_average_is_seeded(self):
        out = ts.raw_strength(np.linspace(100, 200, 300))
        self.assertTrue(np.isnan(out[:199]).all())
        self.assertFalse(np.isnan(out[220]))

    def test_raw_strength_is_positive_above_the_average(self):
        close = np.linspace(100, 300, 400)
        out = ts.raw_strength(close)
        self.assertGreater(out[350], 0.0)

    def test_percentile_rank_stays_in_the_unit_interval(self):
        rng = np.random.default_rng(0)
        values = rng.normal(0, 1, 800)
        out = ts.percentile_rank(values)
        live = out[~np.isnan(out)]
        self.assertGreaterEqual(live.min(), 0.0)
        self.assertLessEqual(live.max(), 1.0)

    def test_percentile_rank_averages_about_a_half(self):
        # This is why A2 needs no rescaling to sit near A1's exposure.
        rng = np.random.default_rng(1)
        out = ts.percentile_rank(rng.normal(0, 1, 3000))
        self.assertAlmostEqual(float(np.nanmean(out)), 0.5, delta=0.05)

    def test_percentile_rank_is_causal(self):
        rng = np.random.default_rng(2)
        values = rng.normal(0, 1, 600)
        base = ts.percentile_rank(values)
        tampered = values.copy()
        tampered[400:] += 50.0
        np.testing.assert_allclose(base[:400], ts.percentile_rank(tampered)[:400],
                                   equal_nan=True)

    def test_the_newest_bar_ranks_top_when_it_is_the_highest(self):
        values = np.concatenate([np.zeros(100), [99.0]])
        self.assertAlmostEqual(ts.percentile_rank(values)[-1], 1.0)


class ArmTests(unittest.TestCase):

    def rising(self, n=600):
        return np.array([100.0 * (1.003 ** i) for i in range(n)])

    def test_every_arm_stays_long_only_within_zero_and_one(self):
        rng = np.random.default_rng(3)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 900))) + 20
        for name, weights in (("a1", ts.a1_binary(close)),
                              ("a2", ts.a2_graded(close)),
                              ("a3", ts.a3_inverse_vol(close)),
                              ("a4", ts.a4_constant(close, 0.5))):
            live = weights[~np.isnan(weights)]
            self.assertGreaterEqual(live.min(), 0.0, name)
            self.assertLessEqual(live.max(), 1.0, name)

    def test_binary_is_only_ever_zero_or_one(self):
        close = self.rising()
        live = ts.a1_binary(close)
        live = live[~np.isnan(live)]
        self.assertEqual(set(np.unique(live)) - {0.0, 1.0}, set())

    def test_graded_actually_grades(self):
        # If A2 only ever produced 0 and 1 it would just be A1 in disguise.
        rng = np.random.default_rng(4)
        close = np.abs(100 + np.cumsum(rng.normal(0.05, 2, 1200))) + 20
        live = ts.a2_graded(close)
        live = live[~np.isnan(live)]
        strictly_between = np.count_nonzero((live > 0.01) & (live < 0.99))
        self.assertGreater(strictly_between, 0.5 * len(live))

    def test_inverse_vol_shrinks_when_volatility_rises(self):
        calm = np.array([100.0 * (1.0005 ** i) for i in range(300)])
        rng = np.random.default_rng(5)
        wild = np.abs(100 + np.cumsum(rng.normal(0, 5, 300))) + 50
        self.assertGreater(np.nanmean(ts.a3_inverse_vol(calm)),
                           np.nanmean(ts.a3_inverse_vol(wild)))

    def test_rescaling_uses_only_the_warmup_window(self):
        rng = np.random.default_rng(6)
        weights = np.clip(rng.uniform(0, 1, 1000), 0, 1)
        scaled = ts.rescale_from_warmup(weights, 0.5, warmup=252)
        tampered = weights.copy()
        tampered[252:] = 1.0
        scaled2 = ts.rescale_from_warmup(tampered, 0.5, warmup=252)
        np.testing.assert_allclose(scaled[:252], scaled2[:252])


class PremiseTests(unittest.TestCase):

    def test_a_constructed_monotonic_relationship_is_detected(self):
        # Positive control. The relationship must be FORWARD-looking: strength
        # at bar i has to drive the bars *after* i, and has to persist across
        # the horizon, or a 21-bar forward return dilutes it into nothing.
        rng = np.random.default_rng(7)
        n = 3000
        drift = np.cumsum(rng.normal(0, 0.05, n))          # slow-moving regime
        strength = (drift - drift.min()) / (drift.max() - drift.min())
        steps = np.zeros(n)
        steps[1:] = (strength[:-1] - 0.5) * 0.004 + rng.normal(0, 0.001, n - 1)
        close = 100 * np.exp(np.cumsum(steps))
        out = ts.decile_forward_returns(close, strength, horizon=21, warmup=252)
        self.assertGreater(out["spearman"], 0.5)
        self.assertGreater(out["permutation_percentile"], 0.9)

    def test_pure_noise_does_not_look_monotonic(self):
        rng = np.random.default_rng(8)
        n = 3000
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        strength = rng.uniform(0, 1, n)
        out = ts.decile_forward_returns(close, strength, horizon=21, warmup=252)
        self.assertLess(out["permutation_percentile"], 0.95)

    def test_every_decile_is_populated(self):
        rng = np.random.default_rng(9)
        n = 2000
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        strength = rng.uniform(0, 1, n)
        out = ts.decile_forward_returns(close, strength, horizon=21, warmup=252)
        self.assertEqual(len(out["decile_means"]), 10)
        self.assertTrue(all(c > 0 for c in out["decile_counts"]))


if __name__ == "__main__":
    unittest.main()
