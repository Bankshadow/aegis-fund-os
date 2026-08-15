"""Invariants for the E34 cadence engine.

These run before any result is read. If one breaks, the E34 numbers are not
"slightly off" — they are measuring something else.
"""

import unittest

import numpy as np

from dynamic_grid import cadence as c


def ramp(n, start=100.0, step=1.0):
    return np.array([start + step * i for i in range(n)], dtype=float)


class SignalTests(unittest.TestCase):

    def test_sma_is_nan_until_the_window_is_full(self):
        out = c.sma(ramp(10), 5)
        self.assertTrue(np.isnan(out[:4]).all())
        self.assertFalse(np.isnan(out[4]))

    def test_sma_state_is_nan_during_warmup_then_binary(self):
        state = c.sma_state(ramp(300), 200)
        self.assertTrue(np.isnan(state[:199]).all())
        self.assertTrue(set(np.unique(state[199:])) <= {0.0, 1.0})

    def test_the_signal_is_causal_rewriting_the_future_cannot_move_the_past(self):
        rng = np.random.default_rng(0)
        close = 100 + np.cumsum(rng.normal(0, 1, 600))
        close = np.abs(close) + 10
        base = c.sma_state(close, 200)
        tampered = close.copy()
        tampered[400:] *= 3.0
        after = c.sma_state(tampered, 200)
        np.testing.assert_allclose(base[:400], after[:400])


class CadenceTests(unittest.TestCase):

    def sim(self, close, target, cadence, floor=0.0, initial=10_000.0):
        return c.simulate(close, target, cadence, floor, initial)

    def test_cadence_one_reproduces_the_daily_signal(self):
        close = ramp(400)
        state = c.sma_state(close, 200)
        w = self.sim(close, state, 1)["weights"]
        np.testing.assert_allclose(w[200:], state[200:])

    def test_a_binary_position_does_not_drift_between_decisions(self):
        # Fully in or fully out: nothing to drift, so monthly equals daily here.
        close = ramp(400)
        state = c.sma_state(close, 200)
        self.assertTrue(np.allclose(self.sim(close, state, 21)["weights"][250:], 1.0))

    def test_a_fractional_book_drifts_up_as_the_asset_rises(self):
        # The error this replaced: holding the weight flat would have invented
        # a free daily rebalance for C4 and C5.
        close = np.array([100.0, 110.0, 121.0, 133.1, 146.41])
        w = self.sim(close, np.full(5, 0.5), cadence=100)["weights"]
        self.assertAlmostEqual(w[0], 0.5, places=3)
        self.assertGreater(w[1], 0.5)
        self.assertGreater(w[2], w[1])

    def test_rebalancing_snaps_the_weight_back_to_target(self):
        close = np.array([100.0, 200.0, 400.0, 800.0])
        drift = self.sim(close, np.full(4, 0.5), cadence=100)["weights"]
        snap = self.sim(close, np.full(4, 0.5), cadence=1)["weights"]
        self.assertGreater(drift[3], 0.8)
        np.testing.assert_allclose(snap, 0.5, atol=1e-3)

    def test_drift_is_not_a_trade(self):
        # The defect that crippled the C4 control: counting the daily change in
        # realised weight as turnover billed it ~364 trades a year.
        close = np.array([100.0 * (1.02 ** i) for i in range(400)])
        run = self.sim(close, np.full(400, 0.5), cadence=21)
        self.assertLessEqual(run["trades"], 400 // 21 + 1)
        self.assertGreater(run["weights"][20], run["weights"][0])

    def test_warmup_means_flat_even_when_a_floor_is_set(self):
        # No signal is not a reason to hold half a position.
        close = ramp(400)
        state = c.sma_state(close, 200)
        self.assertEqual(self.sim(close, state, 21, floor=0.5)["weights"][0], 0.0)

    def test_the_floor_is_a_target_at_rebalance_not_a_continuous_guarantee(self):
        # A half-invested book in a falling market drifts BELOW the floor
        # between decision days — nobody is trading, so nothing restores it.
        close = np.concatenate([ramp(250), ramp(150, start=350, step=-2.0)])
        state = c.sma_state(close, 200)
        w = self.sim(close, state, 21, floor=0.5)["weights"]
        decisions = [i for i in range(210, len(close)) if i % 21 == 0]
        for i in decisions:
            self.assertGreaterEqual(w[i], 0.5 - 1e-6, f"decision day {i}")
        self.assertTrue([i for i in decisions[:-1] if w[i + 10] < 0.5],
                        "a falling market must pull the weight below the floor")
        self.assertLessEqual(w.max(), 1.0 + 1e-9)

    def test_weights_never_leave_long_only_bounds(self):
        rng = np.random.default_rng(1)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 900))) + 10
        state = c.sma_state(close, 200)
        for cad in (1, 21, 63):
            w = self.sim(close, state, cad)["weights"]
            self.assertGreaterEqual(w.min(), 0.0)
            self.assertLessEqual(w.max(), 1.0 + 1e-9)


class EquityTests(unittest.TestCase):

    def test_a_flat_book_neither_earns_nor_pays(self):
        close = ramp(50)
        run = c.simulate(close, np.zeros(50), 1, initial=10_000.0)
        np.testing.assert_allclose(run["equity"], 10_000.0)
        self.assertEqual(run["trades"], 0)

    def test_buy_and_hold_matches_the_price_ratio_minus_one_entry_cost(self):
        close = np.array([100.0, 150.0, 200.0])
        run = c.simulate(close, np.ones(3), 1, initial=1000.0)
        self.assertAlmostEqual(run["equity"][-1], 1000.0 * (1 - c.COST_PER_SIDE) * 2.0)

    def test_cost_is_charged_on_the_value_traded_not_the_whole_book(self):
        # Trimming 1.0 -> 0.9 must cost far less than liquidating outright.
        close = np.array([100.0, 100.0, 100.0])
        trim = c.simulate(close, np.array([1.0, 0.9, 0.9]), 1, initial=1000.0)
        exit_all = c.simulate(close, np.array([1.0, 0.0, 0.0]), 1, initial=1000.0)
        self.assertLess(1000.0 - trim["equity"][-1], 1000.0 - exit_all["equity"][-1])
        self.assertEqual(trim["trades"], 2)

    def test_cost_never_produces_negative_cash_or_weight_above_one(self):
        # The bug this pins: booking cost as negative cash pushed a fully
        # invested weight above 1.0, which then re-traded every single day.
        close = ramp(300)
        run = c.simulate(close, np.ones(300), 1, initial=1000.0)
        self.assertLessEqual(run["weights"].max(), 1.0 + 1e-12)
        self.assertEqual(run["trades"], 1)

    def test_the_weight_earns_the_next_bar_not_its_own(self):
        # A position opened on the day of a jump must not collect that jump.
        close = np.array([100.0, 200.0, 200.0])
        run = c.simulate(close, np.array([0.0, 1.0, 1.0]), 1, initial=1000.0)
        # Bar 1 pays the entry cost and nothing else: the 100 -> 200 doubling
        # that happened on the way into bar 1 must not be collected.
        self.assertAlmostEqual(run["equity"][1], 1000.0 * (1 - c.COST_PER_SIDE))
        self.assertAlmostEqual(run["equity"][2], 1000.0 * (1 - c.COST_PER_SIDE))

    def test_drawdown_and_robust_use_the_project_definition(self):
        run = {"equity": np.array([100.0, 200.0, 100.0]),
               "weights": np.ones(3), "trades": 1, "traded_value": 0.0}
        m = c.metrics(run)
        self.assertAlmostEqual(m["max_dd"], 0.5)
        self.assertAlmostEqual(m["total_return"], 0.0)
        self.assertAlmostEqual(m["robust"], 0.0 - 2.0 * 0.5)

    def test_trade_counts_come_from_the_simulation_not_the_weight_path(self):
        close = np.array([100.0 * (1.01 ** i) for i in range(365)])
        run = c.simulate(close, np.full(365, 0.5), 365, initial=1000.0)
        m = c.metrics(run)
        self.assertEqual(m["trades"], 1)
        self.assertAlmostEqual(m["trades_per_year"], 1.0, places=1)
        self.assertGreater(run["weights"][-1], 0.5, "weight drifted without trading")


if __name__ == "__main__":
    unittest.main()
