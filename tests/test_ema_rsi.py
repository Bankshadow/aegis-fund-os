"""Invariants for the E36 EMA/RSI signal layer.

Run before any result is read. The signal layer must be causal and must never
touch equity — position accounting stays in the E31 leveraged engine.
"""

import unittest

import numpy as np

from dynamic_grid import ema_rsi as er


def panel(series):
    return np.array(series, dtype=float).reshape(-1, 1)


class IndicatorTests(unittest.TestCase):

    def test_ema_is_nan_until_seeded(self):
        out = er.ema(np.arange(10, dtype=float), 5)
        self.assertTrue(np.isnan(out[:4]).all())
        self.assertAlmostEqual(out[4], np.arange(5).mean())

    def test_ema_is_causal(self):
        rng = np.random.default_rng(0)
        values = np.abs(100 + np.cumsum(rng.normal(0, 1, 300)))
        base = er.ema(values, 21)
        tampered = values.copy()
        tampered[200:] *= 5.0
        np.testing.assert_allclose(base[:200], er.ema(tampered, 21)[:200])

    def test_rsi_is_100_when_nothing_ever_falls(self):
        self.assertAlmostEqual(er.rsi(np.arange(1, 60, dtype=float), 14)[-1], 100.0)

    def test_rsi_stays_within_bounds(self):
        rng = np.random.default_rng(1)
        values = np.abs(100 + np.cumsum(rng.normal(0, 2, 500)))
        out = er.rsi(values, 14)
        live = out[~np.isnan(out)]
        self.assertGreaterEqual(live.min(), 0.0)
        self.assertLessEqual(live.max(), 100.0)

    def test_rsi_is_causal(self):
        rng = np.random.default_rng(2)
        values = np.abs(100 + np.cumsum(rng.normal(0, 2, 400)))
        base = er.rsi(values, 14)
        tampered = values.copy()
        tampered[300:] *= 3.0
        np.testing.assert_allclose(base[:300], er.rsi(tampered, 14)[:300], equal_nan=True)


class ArmTests(unittest.TestCase):

    def test_the_control_arm_permits_everything(self):
        for value in (0.0, 50.0, 100.0, np.nan):
            self.assertTrue(er.RSI_ARMS["R0_none"](value, True))
            self.assertTrue(er.RSI_ARMS["R0_none"](value, False))

    def test_r1_uses_the_fifty_line_symmetrically(self):
        self.assertTrue(er.RSI_ARMS["R1_above50"](60.0, True))
        self.assertFalse(er.RSI_ARMS["R1_above50"](40.0, True))
        self.assertTrue(er.RSI_ARMS["R1_above50"](40.0, False))
        self.assertFalse(er.RSI_ARMS["R1_above50"](60.0, False))

    def test_r2_blocks_chasing_and_r3_blocks_trading_against(self):
        self.assertFalse(er.RSI_ARMS["R2_no_chase"](80.0, True))
        self.assertTrue(er.RSI_ARMS["R3_not_against"](80.0, True))
        self.assertFalse(er.RSI_ARMS["R3_not_against"](20.0, True))
        self.assertTrue(er.RSI_ARMS["R2_no_chase"](20.0, True))

    def test_every_declared_arm_exists(self):
        self.assertEqual(set(er.RSI_ARMS), {"R0_none", "R1_above50", "R2_no_chase", "R3_not_against"})


class StrategyTests(unittest.TestCase):

    def rising(self, n=200):
        return panel([100.0 * (1.01 ** i) for i in range(n)])

    def test_a_rising_market_goes_long_at_the_declared_leverage(self):
        closes = self.rising()
        strategy = er.EmaRsi(closes, leverage=5.0, arm="R0_none")
        self.assertAlmostEqual(strategy.weights(150)[0], 5.0)

    def test_weights_are_flat_while_the_emas_are_unseeded(self):
        closes = self.rising()
        strategy = er.EmaRsi(closes, arm="R0_none")
        self.assertEqual(strategy.weights(5)[0], 0.0)

    def test_long_only_never_returns_a_negative_weight(self):
        rng = np.random.default_rng(3)
        closes = panel(np.abs(100 + np.cumsum(rng.normal(0, 2, 600))) + 10)
        strategy = er.EmaRsi(closes, arm="R0_none", long_only=True)
        weights = [strategy.weights(i)[0] for i in range(len(closes))]
        self.assertGreaterEqual(min(weights), 0.0)

    def test_long_short_does_take_the_short_side(self):
        rng = np.random.default_rng(3)
        closes = panel(np.abs(100 + np.cumsum(rng.normal(0, 2, 600))) + 10)
        strategy = er.EmaRsi(closes, arm="R0_none", long_only=False)
        weights = [strategy.weights(i)[0] for i in range(len(closes))]
        self.assertLess(min(weights), 0.0)

    def test_the_signal_never_reads_a_future_bar(self):
        rng = np.random.default_rng(4)
        values = np.abs(100 + np.cumsum(rng.normal(0, 2, 500))) + 10
        base = er.EmaRsi(panel(values), arm="R1_above50")
        tampered = values.copy()
        tampered[400:] *= 4.0
        after = er.EmaRsi(panel(tampered), arm="R1_above50")
        for i in range(400):
            self.assertEqual(base.weights(i)[0], after.weights(i)[0], f"bar {i}")

    def test_a_stricter_arm_can_only_trade_less_often(self):
        # R1 is a subset of R0 by construction; if it ever traded more, the
        # gate would be inverted somewhere.
        rng = np.random.default_rng(5)
        closes = panel(np.abs(100 + np.cumsum(rng.normal(0, 2, 800))) + 10)
        none = er.EmaRsi(closes, arm="R0_none")
        gated = er.EmaRsi(closes, arm="R1_above50")
        live_none = sum(1 for i in range(len(closes)) if none.weights(i)[0] != 0)
        live_gated = sum(1 for i in range(len(closes)) if gated.weights(i)[0] != 0)
        self.assertLessEqual(live_gated, live_none)


class TradeCountTests(unittest.TestCase):

    def test_a_flat_path_has_no_trades(self):
        self.assertEqual(er.count_trades(np.zeros(50))["count"], 0)

    def test_open_and_close_counts_as_one_trade(self):
        path = np.array([0, 5, 5, 5, 0, 0], dtype=float)
        self.assertEqual(er.count_trades(path)["count"], 1)

    def test_a_flip_closes_one_trade_and_opens_the_next(self):
        path = np.array([0, 5, 5, -5, -5, 0], dtype=float)
        self.assertEqual(er.count_trades(path)["count"], 2)

    def test_a_position_still_open_at_the_end_is_not_counted(self):
        # Counting it would credit an unrealised mark as a completed trade.
        path = np.array([0, 5, 5, 5], dtype=float)
        self.assertEqual(er.count_trades(path)["count"], 0)


if __name__ == "__main__":
    unittest.main()
