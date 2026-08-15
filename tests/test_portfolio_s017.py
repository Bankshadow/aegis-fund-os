"""Invariants for the E55 portfolio driver and the S017 cooldown.

The one that matters most is `NoCooldownTests`: with the cooldown off, the
portfolio driver has to reproduce `run_symbol` trade for trade, or every number
E44-E51 published stops being comparable to anything E55 says. The rest pin the
semantics `docs/E55_CRITERIA.md` section 1 declared in advance, because each one
is a place the locked spec is silent and a different reading would change the
result.
"""

import datetime as dt
import json
import os
import unittest

import numpy as np

from dynamic_grid import strat_trap as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S003_DATA = os.path.join(ROOT, "data", "s003")


def days(n, start="2020-01-01"):
    d0 = dt.date.fromisoformat(start)
    return [(d0 + dt.timedelta(days=i)).isoformat() for i in range(n)]


def feed(rows):
    """rows = [(open, high, low, close), ...] -> (dates, o, h, l, c)"""
    a = np.array(rows, dtype=float)
    return days(len(rows)), a[:, 0], a[:, 1], a[:, 2], a[:, 3]


BASE_BAR = (100.0, 101.0, 99.0, 100.0)

# One losing short, then quiet bars, so the cycle repeats cleanly and every
# repetition books exactly -1R.
#   SIGNAL  2U (h>101, l>=99) and red      -> SHORT at 100.5
#   STOPOUT high runs through the stop     -> SL
#   then base bars: the first is a 2D doji, the rest are inside bars
#
# The quiet tail is long on purpose. The two eventful bars each add ~6 of true
# range against the base's 2, and a short tail lets ATR ratchet up cycle after
# cycle until the stop sits above the stop-out bar's high and the fixture
# quietly stops losing. Thirty flat bars decay the excess away, so cycle 7
# behaves exactly like cycle 1.
LOSS_CYCLE = ([(101.0, 105.0, 99.0, 100.5),
               (101.0, 106.0, 100.0, 105.5)] + [BASE_BAR] * 30)


def losing_feed(cycles, warmup_bars):
    return feed([BASE_BAR] * warmup_bars + LOSS_CYCLE * cycles)


class NoCooldownTests(unittest.TestCase):
    """H1/H2: cooldown off must be `run_symbol`, exactly."""

    def assert_same(self, feeds, **kw):
        port = st.run_portfolio(feeds, **kw)
        for sym, (dates, o, h, l, c) in feeds.items():
            solo = st.run_symbol(sym, dates, o, h, l, c, **kw)
            got, want = port.per_symbol[sym].closed, solo.closed
            self.assertEqual(len(got), len(want), f"{sym}: trade count")
            for a, b in zip(got, want):
                self.assertEqual((a.entry_date, a.exit_date, a.side, a.reason),
                                 (b.entry_date, b.exit_date, b.side, b.reason))
                self.assertAlmostEqual(a.pnl_r_net, b.pnl_r_net, places=12)

    def random_feed(self, seed, n=700):
        rng = np.random.default_rng(seed)
        close = np.abs(100 + np.cumsum(rng.normal(0, 2, n))) + 50
        o = close * (1 + rng.normal(0, 0.01, n))
        h = np.maximum(o, close) * (1 + np.abs(rng.normal(0, 0.02, n)))
        l = np.minimum(o, close) * (1 - np.abs(rng.normal(0, 0.02, n)))
        return days(n), o, h, l, close

    def test_two_assets_match_the_solo_engine(self):
        feeds = {"A": self.random_feed(11), "B": self.random_feed(12)}
        self.assertTrue(st.run_portfolio(feeds).closed, "fixture must trade")
        self.assert_same(feeds)

    def test_assets_with_different_start_dates_still_match(self):
        # LINK starts 2017, SOL 2020: the union axis has to tolerate a symbol
        # that simply has no bar on a given day.
        dates, o, h, l, c = self.random_feed(13)
        feeds = {"A": (dates, o, h, l, c),
                 "B": (dates[200:], o[200:], h[200:], l[200:], c[200:])}
        self.assert_same(feeds)

    def test_the_pessimistic_intrabar_model_matches_too(self):
        feeds = {"A": self.random_feed(14), "B": self.random_feed(15)}
        self.assert_same(feeds, intrabar="sl_first")

    @unittest.skipUnless(os.path.isdir(S003_DATA), "s003 data not present")
    def test_real_sol_and_link_match_trade_for_trade(self):
        feeds = {}
        for sym in ("SOL-USD", "LINK-USD"):
            path = os.path.join(S003_DATA, f"{sym}_full.json")
            if not os.path.exists(path):
                self.skipTest(f"{sym} full history not present")
            with open(path, encoding="utf-8") as fh:
                rows = json.load(fh)["rows"]
            while rows:                       # same trailing-bar rule as E45
                _, o, h, l, c = rows[-1]
                if l <= o <= h and l <= c <= h:
                    break
                rows.pop()
            a = np.array([[r[1], r[2], r[3], r[4]] for r in rows], dtype=float)
            feeds[sym] = ([r[0] for r in rows], a[:, 0], a[:, 1], a[:, 2], a[:, 3])
        self.assert_same(feeds)


class CooldownTests(unittest.TestCase):

    def setUp(self):
        self.warmup = st.WARMUP + 1

    def run_cycles(self, cycles, cooldown=None, symbols=("A",)):
        feeds = {s: losing_feed(cycles, self.warmup) for s in symbols}
        return st.run_portfolio(feeds, cooldown=cooldown)

    def test_the_fixture_loses_once_per_cycle(self):
        res = self.run_cycles(6)
        self.assertEqual(len(res.closed), 6)
        for t in res.closed:
            self.assertEqual(t.reason, "SL")
            self.assertLess(t.pnl_r_net, 0)

    def test_four_losses_skip_exactly_the_next_two_signals(self):
        res = self.run_cycles(7, cooldown=st.S017)
        self.assertEqual(len(res.skipped), 2)
        self.assertEqual(len(res.closed), 5, "4 before the pause, 1 after")

    def test_the_budget_is_signals_not_bars(self):
        # Only two signals are skipped no matter how many bars pass between
        # them - the spec counts signals, and a quiet month costs nothing.
        res = self.run_cycles(7, cooldown=st.Cooldown(streak=4, skip=2))
        self.assertEqual([s for _, s in res.skipped], ["A", "A"])

    def test_a_win_resets_the_streak(self):
        # Three losses, a win, then three more losses: never four in a row, so
        # the cooldown must never arm.
        win = [(101.0, 105.0, 99.0, 100.5)]          # 2U red -> SHORT at 100.5
        rows = [BASE_BAR] * self.warmup + LOSS_CYCLE * 3
        entry, r = 100.5, None
        res_probe = st.run_portfolio({"A": feed(rows + win + [BASE_BAR])})
        r = res_probe.per_symbol["A"].trades[-1].r
        tp3 = entry - 3 * r
        rows = rows + win + [(entry, entry + 0.1, tp3 - 1.0, tp3)]
        rows += LOSS_CYCLE * 3
        res = st.run_portfolio({"A": feed(rows)}, cooldown=st.S017)
        self.assertEqual([t.reason for t in res.closed][3], "TP3")
        self.assertEqual(res.skipped, [], "the win breaks the streak")

    def test_the_streak_is_shared_across_assets(self):
        # Two assets losing in lockstep reach four combined losses in half the
        # cycles a single asset would need.
        res = self.run_cycles(3, cooldown=st.S017, symbols=("A", "B"))
        self.assertEqual(len(res.skipped), 2)
        self.assertEqual(len(res.closed), 4)

    def test_per_symbol_streaks_pause_later_than_the_shared_one(self):
        shared = self.run_cycles(3, cooldown=st.S017, symbols=("A", "B"))
        split = self.run_cycles(3, cooldown=st.Cooldown(per_symbol=True),
                                symbols=("A", "B"))
        self.assertEqual(len(split.skipped), 0)
        self.assertGreater(len(shared.skipped), len(split.skipped))

    def test_ties_are_broken_alphabetically(self):
        # Both assets signal on the same bar with one skip left: the criteria
        # fixed A-before-Z, so A is the one that loses its turn.
        res = self.run_cycles(3, cooldown=st.Cooldown(streak=4, skip=1),
                              symbols=("A", "B"))
        self.assertEqual([s for _, s in res.skipped], ["A"])

    def test_duty_counts_only_signals_that_reached_the_gate(self):
        res = self.run_cycles(7, cooldown=st.S017)
        self.assertEqual(res.signals, 7)
        self.assertAlmostEqual(res.duty, 2 / 7)

    def test_a_skip_decider_can_stand_in_for_the_cooldown(self):
        seen = []
        res = st.run_portfolio({"A": losing_feed(4, self.warmup)},
                               skip_decider=lambda s, d: bool(seen.append((s, d))) or True)
        self.assertEqual(res.closed, [])
        self.assertEqual(len(res.skipped), 4)

    def test_a_cooldown_and_a_decider_cannot_both_be_given(self):
        with self.assertRaises(ValueError):
            st.run_portfolio({"A": losing_feed(1, self.warmup)},
                             cooldown=st.S017, skip_decider=lambda s, d: False)


class ArmingBarRuleTests(unittest.TestCase):
    """D1: the one rule the locked spec does not state."""

    SIGNAL = ("2024-09-01", 99.0, 100.5, 98.0, 100.0)

    def bars_for(self, following):
        rows = [(f"2020-{1 + i // 28:02d}-{1 + i % 28:02d}",) + BASE_BAR
                for i in range(st.WARMUP + 1)]
        rows = [(d, o, h, l, c) for d, o, h, l, c in rows]
        rows.append(self.SIGNAL)
        rows.extend(following)
        dates = [r[0] for r in rows]
        a = np.array([[r[1], r[2], r[3], r[4]] for r in rows], dtype=float)
        return dates, a[:, 0], a[:, 1], a[:, 2], a[:, 3]

    def planned(self):
        d, o, h, l, c = self.bars_for([("2024-09-02", 100, 100.2, 99.8, 100)])
        return st.run_symbol("X", d, o, h, l, c).trades[0]

    def arming_bar_run(self, be_on_arming_bar):
        base = self.planned()
        d, o, h, l, c = self.bars_for(
            [("2024-09-02", 100, base.tp2 + 0.01, base.entry - 1, 100.0)])
        return st.run_symbol("X", d, o, h, l, c,
                             be_on_arming_bar=be_on_arming_bar).trades[0]

    def test_the_default_survives_the_arming_bar(self):
        self.assertEqual(self.arming_bar_run(False).reason, "EOD")

    def test_the_literal_reading_stops_out_on_the_arming_bar(self):
        t = self.arming_bar_run(True)
        self.assertEqual(t.reason, "BE_SL")
        self.assertAlmostEqual(t.pnl_r_gross, 0.0, places=9)

    def test_the_flag_changes_nothing_under_the_pessimistic_model(self):
        # sl_first already re-checks the moved stop, so the two readings only
        # ever disagree under tp_first.
        base = self.planned()
        d, o, h, l, c = self.bars_for(
            [("2024-09-02", 100, base.tp2 + 0.01, base.entry - 1, 100.0)])
        a = st.run_symbol("X", d, o, h, l, c, intrabar="sl_first").trades[0]
        b = st.run_symbol("X", d, o, h, l, c, intrabar="sl_first",
                          be_on_arming_bar=True).trades[0]
        self.assertEqual(a.reason, b.reason)


if __name__ == "__main__":
    unittest.main()
