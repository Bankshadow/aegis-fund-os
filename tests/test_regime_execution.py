import unittest

import numpy as np

from dynamic_grid.backtest import run_backtest
from dynamic_grid.grid_engine import DynamicGridConfig, DynamicGridEngine
from dynamic_grid.regime import PersistentRegimeDetector


class RegimeExecutionTests(unittest.TestCase):
    def test_direction_and_volatility_can_coexist(self):
        detector = PersistentRegimeDetector(
            m_threshold=0.3, vol_hi=1.2, confirm_bars=2,
            min_dwell_bars=0, hysteresis=0.7)
        price = 100.0
        # Warm the slow ATR in a calm market.
        for _ in range(55):
            detector.update(price + 0.3, price - 0.3, price)
        # A persistent selloff with expanding ranges must not be labelled as
        # merely high volatility; both risk dimensions are observable.
        for width in (2, 3, 4, 5, 6, 7, 8, 9):
            price -= 2.0
            detector.update(price + width, price - width, price)
        self.assertEqual(detector.direction, "trend_down")
        self.assertEqual(detector.volatility, "high_vol")

    def test_conservative_intrabar_resolves_ambiguous_bar_against_strategy(self):
        bars = np.array([
            [100.0, 101.0, 99.0, 100.0],  # build: level 98, stop 96, TP 100
            [100.0, 99.0, 98.0, 98.5],    # fill the level only
            [98.0, 101.0, 95.0, 97.0],    # TP and stop both touched
        ])
        common = dict(levels=1, atr_period=1, atr_mult=1.0,
                      risk_per_zone=0.01, stop_mult=1.0, tp_mult=1.0,
                      use_regime=False, fee_rate=0.0)
        optimistic = run_backtest(
            bars, DynamicGridConfig(**common, conservative_intrabar=False))
        conservative = run_backtest(
            bars, DynamicGridConfig(**common, conservative_intrabar=True))
        self.assertGreater(optimistic.total_return, conservative.total_return)
        self.assertLess(conservative.total_return, 0.0)

    def test_liquidation_books_exit_cost_for_open_position(self):
        bars = np.array([
            [100.0, 101.0, 99.0, 100.0],
            [100.0, 100.0, 98.0, 99.0],
        ])
        cfg = DynamicGridConfig(
            levels=1, atr_period=1, atr_mult=1.0, risk_per_zone=0.01,
            stop_mult=2.0, tp_mult=3.0, use_regime=False,
            fee_rate=0.001, book_entry_fees_immediately=True,
            stop_slippage_bps=10.0)
        marked = run_backtest(bars, cfg, liquidate_at_end=False)
        liquidated = run_backtest(bars, cfg, liquidate_at_end=True)
        self.assertLess(liquidated.final_equity, marked.final_equity)


if __name__ == "__main__":
    unittest.main()
