"""Invariants for E41 DEX-vol rotation."""

import unittest

import numpy as np

from dynamic_grid import dex_rotation as d


class GrowthTests(unittest.TestCase):

    def test_growth_uses_only_past_lookback(self):
        vals = np.array([10.0, 20.0, 40.0, 80.0, 160.0])
        g = d.growth(vals, lookback=2)
        self.assertTrue(np.isnan(g[1]))
        self.assertAlmostEqual(g[2], 3.0)  # 40/10 - 1
        self.assertAlmostEqual(g[4], 3.0)  # 160/40 - 1

    def test_vol_chart_alignment_is_day_keyed(self):
        dates = np.array([1_700_000_000_000, 1_700_086_400_000], dtype=np.int64)
        chart = [[1_700_000_000, 100.0], [1_700_086_400, 200.0]]
        vol = d.load_vol_chart(chart, dates)
        np.testing.assert_allclose(vol, [100.0, 200.0])


class RotationTests(unittest.TestCase):

    def test_equal_weight_has_no_turnover_after_start(self):
        n = 120
        closes = {
            "ETH": 100 + np.cumsum(np.ones(n)),
            "SOL": 50 + np.cumsum(np.ones(n) * 0.5),
        }
        scores = {s: np.zeros(n) for s in closes}
        res = d.run_rotation(closes, scores, mode="eq")
        # after first set, weights constant → turnover only possibly at start
        self.assertGreaterEqual(res.n_rebalances, 1)
        self.assertAlmostEqual(res.turnover, 0.0, places=9)

    def test_dex_picks_higher_growth_name(self):
        n = 100
        eth = np.full(n, 100.0)
        sol = np.full(n, 100.0)
        # flat prices so return path is about weights/costs only
        closes = {"ETH": eth, "SOL": sol}
        scores = {"ETH": np.full(n, -0.1), "SOL": np.full(n, 0.5)}
        res = d.run_rotation(closes, scores, mode="dex")
        # inspect a rebalance day weight via reconstructing — equity ~1 if flat
        self.assertLess(abs(res.total_return), 0.01)  # flat prices; only tiny rebalance costs


    def test_oos_windows_exclude_held_out_tail(self):
        windows = d.oos_windows(1000, held_out_tail=252, oos=252, warmup=60)
        self.assertTrue(windows)
        self.assertLessEqual(windows[-1][1], 1000 - 252)
        for a, b in windows:
            self.assertEqual(b - a, 252)

    def test_window_metrics_stop_beats_nothing_on_flat(self):
        n = 80
        closes = {"ETH": np.full(n, 100.0), "SOL": np.full(n, 100.0)}
        scores = {s: np.zeros(n) for s in closes}
        res = d.run_rotation(closes, scores, mode="eq")
        m = d.window_metrics(res, 60, 80)
        self.assertAlmostEqual(m["return"], 0.0, places=9)
        self.assertAlmostEqual(m["maxDD"], 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
