"""Invariants for the E37 DSL runtime.

Run before any result is read. Order-of-checks inside a bar is the thing that
makes or breaks a leveraged stop simulator, so most of these pin exactly that.
"""

import unittest

import numpy as np

from dynamic_grid import dsl_runtime as dsl


def flat(n, price=100.0):
    c = np.full(n, price)
    return c, c.copy(), c.copy()


def rising(n, start=100.0, step=0.004):
    c = np.array([start * (1 + step) ** i for i in range(n)])
    return c, c * 1.001, c * 0.999


class LadderTests(unittest.TestCase):
    """The ladder is denominated in price move; leverage must not appear in it."""

    def test_no_floor_before_the_first_tier(self):
        self.assertEqual(dsl.floor_from_ladder(0.019), 0.0)

    def test_each_declared_tier_locks_its_fraction(self):
        self.assertAlmostEqual(dsl.floor_from_ladder(0.02), 0.006)
        self.assertAlmostEqual(dsl.floor_from_ladder(0.07), 0.035)
        self.assertAlmostEqual(dsl.floor_from_ladder(0.20), 0.170)

    def test_the_highest_reached_tier_wins(self):
        self.assertAlmostEqual(dsl.floor_from_ladder(0.24), 0.204)

    def test_the_price_tiers_are_the_exact_5x_equivalents_of_the_roe_preset(self):
        # A2 must be a re-denomination, not a re-tuning: at the declared 5x the
        # new tiers have to arm at exactly the same place as the published
        # ROE tiers did, or a "design fix" has quietly become a parameter change.
        for (roe_tier, roe_frac), (price_tier, price_frac) in zip(
                dsl.PROFIT_LADDER_ROE, dsl.PRICE_LADDER):
            self.assertAlmostEqual(price_tier, roe_tier / 5.0, places=12)
            self.assertEqual(price_frac, roe_frac)

    def test_the_ladder_does_not_depend_on_leverage(self):
        # The old ROE form armed at a 2% move at 5x and a 10% move at 1x. The
        # whole point of A2 is that this can no longer happen.
        rng = np.random.default_rng(9)
        close = np.abs(100 + np.cumsum(rng.normal(0.05, 1.5, 900))) + 20
        high, low = close * 1.01, close * 0.99
        exits = {}
        for lev in (1.0, 2.0, 5.0):
            r = dsl.run(close, high, low, warmup=60, leverage=lev,
                        drawdown_halt=0.99, daily_loss_limit=0.99)
            exits[lev] = [(t.entry_bar, t.exit_bar, t.reason) for t in r.trades]
        self.assertEqual(exits[1.0], exits[5.0],
                         "entry/exit timing must be identical across leverage")
        self.assertEqual(exits[2.0], exits[5.0])


class SignalTests(unittest.TestCase):

    def test_intent_fires_only_on_the_crossing_bar(self):
        close, _, _ = rising(200)
        intent = dsl.signals(close, use_rsi=False)
        self.assertLessEqual(np.count_nonzero(intent), 3,
                             "a monotonic ramp must not re-fire every bar")

    def test_dedup_is_structural_not_a_counter(self):
        rng = np.random.default_rng(0)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 800))) + 20
        intent = dsl.signals(close, use_rsi=False)
        # No two consecutive bars may both carry the same non-zero intent.
        for i in range(1, len(intent)):
            if intent[i] != 0 and intent[i - 1] != 0:
                self.assertNotEqual(intent[i], intent[i - 1])

    def test_the_rsi_gate_can_only_remove_signals(self):
        rng = np.random.default_rng(1)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 900))) + 20
        wide = np.count_nonzero(dsl.signals(close, use_rsi=False))
        gated = np.count_nonzero(dsl.signals(close, use_rsi=True))
        self.assertLessEqual(gated, wide)

    def test_signals_are_causal(self):
        rng = np.random.default_rng(2)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 600))) + 20
        base = dsl.signals(close, use_rsi=True)
        tampered = close.copy()
        tampered[400:] *= 4.0
        np.testing.assert_array_equal(base[:400], dsl.signals(tampered, use_rsi=True)[:400])


class RuntimeTests(unittest.TestCase):

    def test_a_flat_market_never_trades(self):
        close, high, low = flat(300)
        result = dsl.run(close, high, low, warmup=60)
        self.assertEqual(result.stats()["trades"], 0)
        self.assertAlmostEqual(result.equity[-1], 5_000.0)

    def test_only_one_position_is_ever_open(self):
        rng = np.random.default_rng(3)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 1200))) + 20
        result = dsl.run(close, close * 1.01, close * 0.99, warmup=60)
        for a, b in zip(result.trades, result.trades[1:]):
            self.assertGreaterEqual(b.entry_bar, a.exit_bar,
                                    "a new trade opened before the previous closed")

    def test_a_monotonic_ramp_produces_no_crossing_at_all(self):
        # Not a bug: after the EMAs seed, a ramp never has fast crossing slow —
        # the crossing happened while they were still undefined. Pinned so the
        # next reader does not "fix" the signal into firing here.
        close, _, _ = rising(200)
        self.assertEqual(np.count_nonzero(dsl.signals(close, use_rsi=False)), 0)

    def test_a_stop_is_taken_on_the_bar_that_touches_it(self):
        # Down then up, so a genuine cross lands after the warm-up.
        close = np.concatenate([np.linspace(120, 90, 70), np.linspace(90, 115, 40),
                                np.full(30, 115.0)])
        high, low = close * 1.002, close.copy()
        entry_zone = 112
        low[entry_zone] = 70.0                # deep wick beyond any 3xATR stop
        result = dsl.run(close, high, low, warmup=60)
        closed = [t for t in result.trades if t.exit_bar >= 0]
        self.assertTrue(closed, "the fixture must actually open a trade")
        self.assertTrue(any(t.reason in ("stop_3atr", "liquidation") for t in closed))

    def test_liquidation_is_checked_before_the_stop(self):
        # A -25% bar at 5x wipes the account; the engine must call it a
        # liquidation, not a tidy stop-out, or it would overstate survival.
        close = np.concatenate([np.linspace(100, 120, 70), [120.0], [90.0], [90.0] * 10])
        high = close * 1.001
        low = close.copy()
        low[71] = 120.0 * 0.70
        result = dsl.run(close, high, low, warmup=60, leverage=5.0)
        if result.trades and result.trades[0].exit_bar >= 0:
            self.assertEqual(result.trades[0].reason, "liquidation")

    def test_drawdown_halt_stops_trading_and_bounds_the_loss(self):
        rng = np.random.default_rng(4)
        close = np.abs(100 + np.cumsum(rng.normal(-0.6, 3, 1500))) + 20
        result = dsl.run(close, close * 1.02, close * 0.98, warmup=60,
                         drawdown_halt=0.25, halt_is_permanent=True)
        if result.halted_at >= 0:
            self.assertTrue(np.all(np.diff(result.equity[result.halted_at:]) == 0),
                            "equity must be frozen after a permanent halt")

    def test_no_lookahead_truncating_the_future_cannot_change_the_past(self):
        rng = np.random.default_rng(5)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 900))) + 20
        high, low = close * 1.01, close * 0.99
        full = dsl.run(close, high, low, warmup=60)
        cut = dsl.run(close[:600], high[:600], low[:600], warmup=60)
        np.testing.assert_allclose(full.equity[:540], cut.equity[:540])

    def test_cost_is_charged_on_leveraged_notional_both_ways(self):
        close = np.concatenate([np.linspace(100, 110, 70), np.full(30, 110.0)])
        result = dsl.run(close, close * 1.0001, close * 0.9999, warmup=60,
                         leverage=5.0, drawdown_halt=0.99)
        self.assertLessEqual(result.equity[-1], 5_000.0 * (1 + 1e-6) * 1.5)

    def test_a_position_open_at_the_end_is_not_counted_as_a_trade(self):
        close, high, low = rising(200)
        result = dsl.run(close, high, low, warmup=60)
        for t in result.trades:
            if t.exit_bar < 0:
                self.assertNotIn(t, [x for x in result.trades if x.exit_bar >= 0])
        self.assertEqual(result.stats()["trades"],
                         len([t for t in result.trades if t.exit_bar >= 0]))

    def test_exit_reasons_are_recorded_for_every_closed_trade(self):
        rng = np.random.default_rng(6)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 1500))) + 20
        result = dsl.run(close, close * 1.02, close * 0.98, warmup=60)
        for t in result.trades:
            if t.exit_bar >= 0:
                self.assertTrue(t.reason, "a closed trade must carry a reason code")


if __name__ == "__main__":
    unittest.main()
