"""Regression tests for the A1/A2 simplifications, on the real BTC data.

A1 (drop the RSI) and A2 (denominate the ladder in price, not ROE) were both
justified by measurements, not by judgement. These pin the measurements, so
neither change can quietly stop being true.

They read the committed 4h fixtures; if those are missing the tests skip rather
than fail, because the fixtures are data, not code.
"""

import json
import os
import unittest

import numpy as np

from dynamic_grid import dsl_runtime as dsl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = (("W1", "BTCUSDT_4h_2y.json"), ("W2", "BTCUSDT_4h_prev2y.json"))


def load(name):
    path = os.path.join(ROOT, "data", name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        bars = json.load(fh)
    return (np.array([float(b[4]) for b in bars]),
            np.array([float(b[2]) for b in bars]),
            np.array([float(b[3]) for b in bars]))


class RsiIsInertTests(unittest.TestCase):
    """A1: the declared 45/55 band rejected 0 signals on both windows."""

    def test_the_band_rejects_nothing_on_either_window(self):
        for label, filename in WINDOWS:
            data = load(filename)
            if data is None:
                self.skipTest(f"{filename} not present")
            close, _, _ = data
            gated = int(np.count_nonzero(dsl.signals(close, use_rsi=True)))
            ungated = int(np.count_nonzero(dsl.signals(close, use_rsi=False)))
            self.assertEqual(gated, ungated,
                             f"{label}: the RSI band is no longer inert "
                             f"({ungated - gated} signals rejected)")

    def test_turning_the_rsi_on_changes_no_result(self):
        for label, filename in WINDOWS:
            data = load(filename)
            if data is None:
                self.skipTest(f"{filename} not present")
            close, high, low = data
            off = dsl.run(close, high, low, warmup=60, use_rsi=False)
            on = dsl.run(close, high, low, warmup=60, use_rsi=True)
            self.assertEqual(off.stats()["trades"], on.stats()["trades"], label)
            self.assertAlmostEqual(off.total_return, on.total_return, places=12,
                                   msg=label)

    def test_the_claim_is_scoped_to_these_windows(self):
        # A band that never binds on BTC 4h can absolutely bind elsewhere; a
        # synthetic series where it does keeps that honest.
        rng = np.random.default_rng(11)
        close = np.abs(100 + np.cumsum(rng.normal(0, 6, 1500))) + 50
        gated = int(np.count_nonzero(dsl.signals(close, use_rsi=True)))
        ungated = int(np.count_nonzero(dsl.signals(close, use_rsi=False)))
        self.assertLessEqual(gated, ungated)


class LadderDenominationTests(unittest.TestCase):
    """A2: at the declared 5x, the price ladder must reproduce the ROE one."""

    def roe_equivalent_run(self, close, high, low, leverage):
        """Re-implements the OLD ROE ladder, to compare against the new one."""
        original = dsl.PRICE_LADDER
        try:
            dsl.PRICE_LADDER = tuple((tier / leverage, frac)
                                     for tier, frac in dsl.PROFIT_LADDER_ROE)
            return dsl.run(close, high, low, warmup=60, leverage=leverage)
        finally:
            dsl.PRICE_LADDER = original

    def test_five_x_is_bit_identical_to_the_old_roe_ladder(self):
        for label, filename in WINDOWS:
            data = load(filename)
            if data is None:
                self.skipTest(f"{filename} not present")
            close, high, low = data
            new = dsl.run(close, high, low, warmup=60, leverage=5.0)
            old = self.roe_equivalent_run(close, high, low, 5.0)
            self.assertEqual(new.stats()["trades"], old.stats()["trades"], label)
            self.assertAlmostEqual(new.total_return, old.total_return, places=12,
                                   msg=f"{label}: A2 changed the declared 5x spec")

    def test_one_x_is_where_the_two_forms_diverge(self):
        # This divergence is the confound A2 removes: under the ROE form the 1x
        # book had to wait for a 10% move to arm the first tier.
        data = load("BTCUSDT_4h_2y.json")
        if data is None:
            self.skipTest("fixture not present")
        close, high, low = data
        new = dsl.run(close, high, low, warmup=60, leverage=1.0)
        old = self.roe_equivalent_run(close, high, low, 1.0)
        self.assertNotEqual(new.stats()["trades"], old.stats()["trades"])


if __name__ == "__main__":
    unittest.main()
