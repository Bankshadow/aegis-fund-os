"""Invariants for E32's trend overlays.

These are the properties that make the E32 numbers listenable at all. If one of
them breaks, the result is not "slightly off" — it is a different experiment.
"""

import unittest

import numpy as np

from dynamic_grid import trend_overlay as t


def panel(series_list):
    """(n_days, n_assets) close panel from a list of per-asset price lists."""
    return np.array(series_list, dtype=float).T


class RollingStatsTests(unittest.TestCase):

    def test_sma_is_nan_until_the_window_is_full(self):
        s = t.Stats(panel([[1.0] * 10]))
        sma = s.sma(5)
        self.assertTrue(np.isnan(sma[:4, 0]).all())
        self.assertFalse(np.isnan(sma[4, 0]))

    def test_sma_matches_the_plain_mean_and_includes_the_current_bar(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        s = t.Stats(panel([prices]))
        got = s.sma(3)[4, 0]
        self.assertAlmostEqual(got, float(np.mean(prices[2:5])))

    def test_sma_is_causal_truncating_the_future_changes_nothing(self):
        rng = np.random.default_rng(0)
        prices = list(np.cumsum(rng.normal(0, 1, 300)) + 100)
        full = t.Stats(panel([prices])).sma(50)
        cut = t.Stats(panel([prices[:200]])).sma(50)
        np.testing.assert_allclose(full[:200, 0], cut[:200, 0], equal_nan=True)

    def test_a_gap_in_the_series_keeps_the_average_undefined(self):
        prices = [1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0]
        sma = t.Stats(panel([prices])).sma(3)
        self.assertTrue(np.isnan(sma[3, 0]))   # window still contains the gap
        self.assertFalse(np.isnan(sma[5, 0]))  # window has moved past it

    def test_volatility_rises_with_dispersion(self):
        calm = [100.0 + 0.1 * i for i in range(40)]
        wild = [100.0 * (1.1 if i % 2 else 0.9) ** 1 + i for i in range(40)]
        vc = t.Stats(panel([calm])).vol(20)[30, 0]
        vw = t.Stats(panel([wild])).vol(20)[30, 0]
        self.assertLess(vc, vw)


class SingleAssetOverlayTests(unittest.TestCase):

    def test_sma_regime_is_flat_below_and_levered_above(self):
        down = [100.0 - i for i in range(60)]
        up = [100.0 + i for i in range(60)]
        flat = t.SmaRegime(t.Stats(panel([down])), window=20, leverage=3.0)
        held = t.SmaRegime(t.Stats(panel([up])), window=20, leverage=3.0)
        self.assertEqual(flat.weights(50)[0], 0.0)
        self.assertEqual(held.weights(50)[0], 3.0)

    def test_weights_never_read_a_future_bar(self):
        rng = np.random.default_rng(3)
        prices = list(np.cumsum(rng.normal(0, 1, 300)) + 200)
        tampered = list(prices)
        tampered[150:] = [p * 10 for p in tampered[150:]]
        a = t.SmaRegime(t.Stats(panel([prices])), window=50, leverage=2.0)
        b = t.SmaRegime(t.Stats(panel([tampered])), window=50, leverage=2.0)
        for i in range(60, 150):
            self.assertEqual(a.weights(i)[0], b.weights(i)[0])

    def test_vol_target_shrinks_the_position_and_respects_the_cap(self):
        calm = [100.0 * (1.001 ** i) for i in range(300)]
        strat = t.VolTargetSma(t.Stats(panel([calm])), window=200, target=0.40,
                               cap=3.0)
        w = strat.weights(250)[0]
        self.assertGreater(w, 0.0)
        self.assertLessEqual(w, 3.0)

    def test_vol_target_is_smaller_when_the_market_is_more_violent(self):
        rng = np.random.default_rng(11)
        base = np.cumprod(1 + rng.normal(0.004, 0.01, 300)) * 100
        loud = np.cumprod(1 + rng.normal(0.004, 0.05, 300)) * 100
        quiet_w = t.VolTargetSma(t.Stats(panel([list(base)])), window=100).weights(280)[0]
        loud_w = t.VolTargetSma(t.Stats(panel([list(loud)])), window=100).weights(280)[0]
        if quiet_w > 0 and loud_w > 0:
            self.assertLess(loud_w, quiet_w)


class BasketTests(unittest.TestCase):

    def test_basket_goes_to_cash_when_nothing_trends(self):
        """The property that separates this from E31's cross-sectional book."""
        falling = [[100.0 - i for i in range(120)] for _ in range(4)]
        basket = t.TimeSeriesMomentumBasket(t.Stats(panel(falling)), window=50,
                                            leverage=2.0, rebalance=1)
        np.testing.assert_allclose(basket.weights(100), np.zeros(4))

    def test_gross_leverage_matches_the_target_when_names_qualify(self):
        rising = [[100.0 + i * (j + 1) for i in range(120)] for j in range(4)]
        basket = t.TimeSeriesMomentumBasket(t.Stats(panel(rising)), window=50,
                                            leverage=2.0, rebalance=1)
        self.assertAlmostEqual(float(np.abs(basket.weights(100)).sum()), 2.0)

    def test_inverse_vol_gives_the_calmer_name_the_larger_weight(self):
        rng = np.random.default_rng(5)
        calm = np.cumprod(1 + rng.normal(0.003, 0.005, 200)) * 100
        wild = np.cumprod(1 + rng.normal(0.003, 0.05, 200)) * 100
        stats = t.Stats(panel([list(calm), list(wild)]))
        w = t.TimeSeriesMomentumBasket(stats, window=50, leverage=1.0,
                                       weighting="invvol", rebalance=1).weights(180)
        if w[0] > 0 and w[1] > 0:
            self.assertGreater(w[0], w[1])

    def test_a_delisted_name_is_dropped_not_carried(self):
        a = [100.0 + i for i in range(120)]
        b = [100.0 + i for i in range(100)] + [np.nan] * 20
        basket = t.TimeSeriesMomentumBasket(t.Stats(panel([a, b])), window=50,
                                            leverage=1.0, rebalance=1)
        self.assertEqual(basket.weights(110)[1], 0.0)

    def test_cash_sleeve_scales_exactly(self):
        up = [100.0 + i for i in range(60)]
        inner = t.SmaRegime(t.Stats(panel([up])), window=20, leverage=3.0)
        self.assertAlmostEqual(t.CashSleeve(inner, 0.5).weights(50)[0], 1.5)


class ConditionalGapTests(unittest.TestCase):
    """The screen in E33. If it peeks, the whole experiment is void."""

    def test_gap_is_causal_truncating_the_future_changes_nothing(self):
        rng = np.random.default_rng(21)
        prices = list(np.cumprod(1 + rng.normal(0.002, 0.03, 900)) * 100)
        full = t.Stats(panel([prices])).conditional_gap(300, 100)
        cut = t.Stats(panel([prices[:600]])).conditional_gap(300, 100)
        np.testing.assert_allclose(full[:600, 0], cut[:600, 0], equal_nan=True)

    def test_gap_at_i_uses_close_i_but_never_close_i_plus_one(self):
        """The admissible line: at close[i] the move into close[i] is known, the
        move out of it is not. Moving a LATER bar must change nothing at i."""
        rng = np.random.default_rng(22)
        base = list(np.cumprod(1 + rng.normal(0.002, 0.03, 900)) * 100)
        later = list(base)
        later[701] = later[701] * 3.0
        a = t.Stats(panel([base])).conditional_gap(300, 100)
        b = t.Stats(panel([later])).conditional_gap(300, 100)
        self.assertFalse(np.isnan(a[700, 0]))
        self.assertAlmostEqual(a[700, 0], b[700, 0])

        same_bar = list(base)
        same_bar[700] = same_bar[700] * 3.0
        c = t.Stats(panel([same_bar])).conditional_gap(300, 100)
        self.assertNotAlmostEqual(a[700, 0], c[700, 0])   # allowed, and expected

    def test_gap_is_undefined_without_enough_days_in_both_states(self):
        rising = [100.0 + i for i in range(500)]     # never below its own SMA
        gap = t.Stats(panel([rising])).conditional_gap(300, 100)
        self.assertTrue(np.isnan(gap[450, 0]))


class ScreenedBasketTests(unittest.TestCase):

    def test_all_three_filters_agreeing_is_full_conviction(self):
        rising = [[100.0 * (1.01 ** i) for i in range(400)] for _ in range(2)]
        s = t.Stats(panel(rising))
        b = t.ScreenedTrendVoteBasket(s, sma_window=100, channel=20, fast=25,
                                      use_screen=False, rebalance=1)
        self.assertAlmostEqual(float(b._votes(350).max()), 1.0)

    def test_a_falling_market_gives_zero_conviction_and_all_cash(self):
        falling = [[100.0 * (0.99 ** i) for i in range(400)] for _ in range(2)]
        b = t.ScreenedTrendVoteBasket(t.Stats(panel(falling)), sma_window=100,
                                      channel=20, fast=25, use_screen=False,
                                      rebalance=1)
        np.testing.assert_allclose(b.weights(350), np.zeros(2))

    def test_gross_exposure_never_exceeds_the_cap(self):
        rng = np.random.default_rng(23)
        series = [list(np.cumprod(1 + rng.normal(0.004, 0.01, 500)) * 100)
                  for _ in range(6)]
        b = t.ScreenedTrendVoteBasket(t.Stats(panel(series)), sma_window=100,
                                      channel=20, fast=25, use_screen=False,
                                      rebalance=1, vol_target=5.0, gross_cap=1.0)
        for i in range(200, 500):
            self.assertLessEqual(float(np.abs(b.weights(i)).sum()), 1.0 + 1e-9)

    def test_the_calmer_asset_gets_the_larger_weight_at_equal_conviction(self):
        rng = np.random.default_rng(24)
        calm = list(np.cumprod(1 + rng.normal(0.004, 0.006, 500)) * 100)
        wild = list(np.cumprod(1 + rng.normal(0.004, 0.04, 500)) * 100)
        b = t.ScreenedTrendVoteBasket(t.Stats(panel([calm, wild])), sma_window=100,
                                      channel=20, fast=25, use_screen=False,
                                      rebalance=1)
        w = b.weights(450)
        if w[0] > 0 and w[1] > 0:
            self.assertGreater(w[0], w[1])

    def test_the_screen_can_only_remove_exposure_never_add_it(self):
        rng = np.random.default_rng(25)
        series = [list(np.cumprod(1 + rng.normal(0.003, 0.02, 1200)) * 100)
                  for _ in range(4)]
        s = t.Stats(panel(series))
        on = t.ScreenedTrendVoteBasket(s, sma_window=200, screen_window=400,
                                       use_screen=True, rebalance=1)
        off = t.ScreenedTrendVoteBasket(s, sma_window=200, screen_window=400,
                                        use_screen=False, rebalance=1)
        for i in range(700, 1200, 7):
            self.assertLessEqual(float(np.abs(on.weights(i)).sum()),
                                 float(np.abs(off.weights(i)).sum()) + 1e-9)

    def test_a_delisted_name_is_dropped_from_the_book(self):
        a = [100.0 + i for i in range(400)]
        bd = [100.0 + i for i in range(380)] + [np.nan] * 20
        b = t.ScreenedTrendVoteBasket(t.Stats(panel([a, bd])), sma_window=100,
                                      channel=20, fast=25, use_screen=False,
                                      rebalance=1)
        self.assertEqual(b.weights(390)[1], 0.0)


class RiskMetricTests(unittest.TestCase):

    def test_a_flat_curve_has_no_drawdown_and_no_growth(self):
        m = t.risk_metrics(np.full(365, 100.0), 100.0)
        self.assertAlmostEqual(m["cagr"], 0.0, places=6)
        self.assertAlmostEqual(m["worst_dd"], 0.0, places=12)

    def test_drawdown_and_mar_on_a_known_curve(self):
        curve = np.array([100.0, 200.0, 100.0, 400.0])
        m = t.risk_metrics(curve, 100.0)
        self.assertAlmostEqual(m["worst_dd"], 0.5)
        self.assertAlmostEqual(m["total_return"], 3.0)
        self.assertAlmostEqual(m["mar"], m["cagr"] / 0.5)

    def test_time_under_water_counts_the_longest_stretch(self):
        curve = np.array([100.0, 90.0, 80.0, 95.0, 120.0, 110.0])
        m = t.risk_metrics(curve, 100.0)
        self.assertEqual(m["max_time_under_water"], 3)

    def test_exposure_share_counts_only_days_with_a_position(self):
        self.assertAlmostEqual(t.exposure_days([0.0, 0.0, 2.0, 2.0]), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
