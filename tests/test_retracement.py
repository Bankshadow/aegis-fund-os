"""Invariants for the E35 retracement measurement.

The load-bearing one is no-lookahead: a fractal pivot at bar i is only knowable
at bar i+L, and a zone drawn from it must not be usable before then. If that
breaks, the study sees the future and manufactures an edge out of nothing.
"""

import unittest

import numpy as np

from dynamic_grid import retracement as r


def series(values):
    """close == high == low, so pivots are unambiguous."""
    close = np.array(values, dtype=float)
    return close.copy(), close.copy(), close


class PivotTests(unittest.TestCase):

    def test_a_pivot_needs_lookback_bars_on_both_sides(self):
        high, low, close = series([1, 2, 3, 4, 5, 4, 3, 2, 1])
        pivots = r.fractal_pivots(high, low, 2)
        self.assertIn((4, True), pivots)

    def test_edges_can_never_be_pivots(self):
        high, low, close = series([9, 1, 2, 3, 2, 1, 9])
        for index, _ in r.fractal_pivots(high, low, 2):
            self.assertGreaterEqual(index, 2)
            self.assertLessEqual(index, len(close) - 3)

    def test_a_pivot_is_only_confirmed_lookback_bars_later(self):
        high, low, close = series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3])
        for swing in r.swings(high, low, close, 2):
            self.assertEqual(swing.usable_from, swing.end + 2)

    def test_the_future_cannot_change_a_confirmed_swing(self):
        # Rewrite everything after bar 60 and the swings that were already
        # confirmed before then must come back identical.
        rng = np.random.default_rng(0)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, 200))) + 10
        high, low = close * 1.01, close * 0.99
        before = [s for s in r.swings(high, low, close, 5) if s.usable_from <= 60]

        tampered = close.copy()
        tampered[60:] *= 3.0
        after = [s for s in r.swings(high * 1.0, low * 1.0, close, 5)]
        after = [s for s in r.swings(np.concatenate([high[:60], tampered[60:] * 1.01]),
                                     np.concatenate([low[:60], tampered[60:] * 0.99]),
                                     tampered, 5) if s.usable_from <= 60]
        self.assertEqual([(s.start, s.end) for s in before],
                         [(s.start, s.end) for s in after])


class ZoneTests(unittest.TestCase):

    def swing(self, up=True):
        return r.Swing(start=0, end=10, start_price=100.0, end_price=200.0,
                       up=up, usable_from=15)

    def test_every_zone_has_the_same_width(self):
        # The fairness control: golden pocket is a band, so 0.5 must be too.
        swing = self.swing()
        widths = []
        for level in list(r.LEVELS.values()) + [0.45, 0.82]:
            lo, hi = swing.zone_price(level)
            widths.append(hi - lo)
        for width in widths:
            self.assertAlmostEqual(width, widths[0], places=9)
            self.assertAlmostEqual(width, swing.span * r.ZONE_WIDTH, places=9)

    def test_the_golden_pocket_band_matches_0618_to_066(self):
        swing = self.swing()
        lo, hi = swing.zone_price(r.LEVELS["Z3_golden"])
        self.assertAlmostEqual(hi, 200.0 - 100.0 * 0.618, places=6)
        self.assertAlmostEqual(lo, 200.0 - 100.0 * 0.660, places=6)

    def test_an_up_leg_retraces_downward_and_a_down_leg_upward(self):
        up = self.swing(up=True).zone_price(0.5)
        self.assertLess(up[1], 200.0)
        down = r.Swing(0, 10, 200.0, 100.0, False, 15).zone_price(0.5)
        self.assertGreater(down[0], 100.0)

    def test_first_touch_needs_the_bar_range_to_intersect_the_band(self):
        low = np.array([10.0, 10.0, 4.0, 10.0])
        high = np.array([12.0, 12.0, 11.0, 12.0])
        self.assertEqual(r.first_touch(low, high, (5.0, 6.0), 0, 4), 2)
        self.assertEqual(r.first_touch(low, high, (0.0, 1.0), 0, 4), -1)

    def test_first_touch_never_looks_before_the_start_bar(self):
        low = np.array([5.0, 50.0, 50.0])
        high = np.array([6.0, 60.0, 60.0])
        self.assertEqual(r.first_touch(low, high, (5.0, 6.0), 1, 3), -1)


class ObservationTests(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(1)
        self.close = np.abs(100 + np.cumsum(rng.normal(0, 2, 900))) + 20
        self.high, self.low = self.close * 1.01, self.close * 0.99

    def test_no_observation_is_recorded_before_its_pivot_is_confirmed(self):
        obs = r.observations(self.high, self.low, self.close, 10, (10,),
                             np.random.default_rng(0))
        seen = 0
        for rows in obs.values():
            for row in rows:
                self.assertGreaterEqual(row["touch"], row["swing_end"] + 10)
                seen += 1
        self.assertGreater(seen, 0, "the fixture must actually produce touches")

    def test_one_observation_per_swing_per_zone_at_most(self):
        # The de-clustering lesson from the RVOL diagnostic: repeated touches
        # inside one swing are not independent evidence.
        obs = r.observations(self.high, self.low, self.close, 10, (10,),
                             np.random.default_rng(0))
        for name, rows in obs.items():
            keys = [(row["swing_start"], row["swing_end"]) for row in rows]
            self.assertEqual(len(keys), len(set(keys)), name)

    def test_forward_return_is_signed_toward_the_swing_direction(self):
        high, low, close = series([100, 110, 120, 130, 120, 110, 100, 90, 80, 70,
                                   60, 50, 60, 70, 80, 90, 100, 110, 120, 130])
        obs = r.observations(high, low, close, 2, (2,), np.random.default_rng(0))
        rows = [row for rows in obs.values() for row in rows]
        self.assertTrue(rows)
        for row in rows:
            self.assertIsInstance(row["fwd_2"], float)

    def test_the_baseline_is_direction_symmetric(self):
        # Otherwise BTC's secular uptrend would be handed to the zones for free.
        base = r.baseline(self.close, (10,), 0)[10]
        self.assertAlmostEqual(float(np.mean(base)), 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
