"""Invariants for E39 crowding-fade measurement."""

import unittest

import numpy as np

from dynamic_grid import crowding_fade as c


def synthetic_raw(n=80, seed=0):
    rng = np.random.default_rng(seed)
    t0 = 1_700_000_000_000
    step = 3_600_000
    close = 60_000 + np.cumsum(rng.normal(0, 50, n))
    close = np.abs(close) + 1000
    high = close + rng.uniform(10, 80, n)
    low = close - rng.uniform(10, 80, n)
    open_ = close + rng.normal(0, 20, n)
    ls = 1.2 + rng.normal(0, 0.1, n)
    ls[40:50] = 1.7
    oi = 1e9 + np.cumsum(rng.normal(0, 1e6, n))
    oi[40:50] = oi[40:50] + 5e7
    funding = np.full(n, 0.00005)
    funding[40:50] = 0.00015
    klines = []
    ls_rows = []
    oi_rows = []
    fund_rows = []
    for i in range(n):
        ts = t0 + i * step
        klines.append([ts, open_[i], high[i], low[i], close[i], "0", ts + step - 1,
                       "0", 0, "0", "0", "0"])
        ls_rows.append({
            "symbol": "BTCUSDT",
            "longShortRatio": str(ls[i]),
            "longAccount": "0.6",
            "shortAccount": "0.4",
            "timestamp": ts,
        })
        oi_rows.append({
            "symbol": "BTCUSDT",
            "sumOpenInterest": "1",
            "sumOpenInterestValue": str(oi[i]),
            "timestamp": ts,
        })
        if i % 8 == 0:
            fund_rows.append({
                "symbol": "BTCUSDT",
                "fundingTime": ts,
                "fundingRate": str(funding[i]),
            })
    return {
        "symbol": "BTCUSDT",
        "long_short": ls_rows,
        "open_interest": oi_rows,
        "funding": fund_rows,
        "klines_1h": klines,
    }


class AlignTests(unittest.TestCase):

    def test_panel_length_matches_overlap(self):
        panel = c.align_panel(synthetic_raw(60))
        self.assertEqual(len(panel.close), 60)
        self.assertEqual(len(panel.funding), 60)

    def test_future_oi_cannot_change_past_masks(self):
        raw = synthetic_raw(100, seed=2)
        panel = c.align_panel(raw)
        before = c.masks(panel)
        cut = 50
        # Tamper future OI / L/S / close
        raw2 = synthetic_raw(100, seed=2)
        for i in range(cut, 100):
            raw2["open_interest"][i]["sumOpenInterestValue"] = str(
                float(raw2["open_interest"][i]["sumOpenInterestValue"]) * 3
            )
            raw2["long_short"][i]["longShortRatio"] = "3.0"
            raw2["klines_1h"][i][4] = float(raw2["klines_1h"][i][4]) * 1.2
        after = c.masks(c.align_panel(raw2))
        for name in ("S_full", "S_fund", "impulse", "crowded"):
            np.testing.assert_array_equal(before[name][:cut], after[name][:cut])


class ScoreTests(unittest.TestCase):

    def test_fade_score_sign(self):
        close = np.array([100.0, 110.0, 105.0, 100.0])
        mask = np.array([True, False, False, False])
        # from 100 to 105 over h=2 → fwd=+5% → fade=-5%
        scores = c.fade_scores(close, mask, 2)
        self.assertEqual(len(scores), 1)
        self.assertAlmostEqual(scores[0], -0.05)

    def test_atr_ignores_current_and_future(self):
        high = np.linspace(110, 150, 40)
        low = np.linspace(90, 130, 40)
        close = np.linspace(100, 140, 40)
        atr = c.atr_sma_prior(high, low, close, 14)
        self.assertTrue(np.isnan(atr[13]))
        self.assertFalse(np.isnan(atr[14]))
        atr_before = atr[:21].copy()
        high2 = high.copy()
        high2[21:] *= 5
        atr2 = c.atr_sma_prior(high2, low, close, 14)
        np.testing.assert_allclose(atr_before, atr2[:21], equal_nan=True)


class BootstrapTests(unittest.TestCase):

    def test_identical_groups_zero_diff(self):
        a = np.full(30, 0.01)
        b = np.full(30, 0.01)
        out = c.bootstrap_diff_percentile(a, b, 1000, np.random.default_rng(0))
        self.assertAlmostEqual(out["diff"], 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
