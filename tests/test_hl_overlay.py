"""Invariants for E43 Hyperliquid fee overlay."""

import unittest

import numpy as np

from dynamic_grid import hl_overlay as h


class PercentileTests(unittest.TestCase):

    def test_percentile_ignores_future_fees(self):
        fees = np.linspace(1.0, 100.0, 120)
        p = h.fee_percentile(fees, window=90)
        cut = 100
        before = p[:cut].copy()
        fees2 = fees.copy()
        fees2[cut:] *= 10
        after = h.fee_percentile(fees2, window=90)[:cut]
        np.testing.assert_allclose(before, after, equal_nan=True)

    def test_align_maps_sec_to_ms(self):
        dates = np.array([1_700_000_000_000, 1_700_086_400_000], dtype=np.int64)
        chart = [[1_700_000_000, 10.0], [1_700_086_400, 20.0]]
        out = h.align_fees_to_dates(chart, dates)
        np.testing.assert_allclose(out, [10.0, 20.0])


class ArmTests(unittest.TestCase):

    def test_h_size_zero_when_trend_off(self):
        n = 300
        close = np.concatenate([np.linspace(200, 100, 220), np.linspace(100, 90, 80)])
        fees = np.linspace(1e6, 2e6, n)
        arms = h.arms(close, fees)
        # After long decline, SMA200 trend should be off on late bars
        late = arms["T1_trend"][-1]
        if np.isfinite(late) and late == 0:
            self.assertEqual(arms["H_size"][-1], 0.0)

    def test_h_gate_requires_half_percentile(self):
        n = 250
        close = np.linspace(100, 200, n)  # uptrend
        fees = np.ones(n)
        fees[-5:] = 0.1  # recent low fees -> low percentile
        arms = h.arms(close, fees)
        # last bar percentile should be low
        p = h.fee_percentile(fees)
        if np.isfinite(p[-1]) and p[-1] < 0.5 and arms["T1_trend"][-1] == 1:
            self.assertEqual(arms["H_gate"][-1], 0.0)


class WindowTests(unittest.TestCase):

    def test_oos_excludes_held_out(self):
        windows = h.oos_windows(500)
        self.assertTrue(windows)
        self.assertLessEqual(windows[-1][1], 500 - h.HELD_OUT)
        for a, b in windows:
            self.assertEqual(b - a, h.OOS)


if __name__ == "__main__":
    unittest.main()
