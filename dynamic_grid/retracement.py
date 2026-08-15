"""E35 — retracement-zone measurement (fractal swings, equal-width zones).

Criteria in `docs/E35_CRITERIA.md`, declared before this file existed.

Pure measurement: no orders, no sizing, no strategy. It answers one question —
does price reaching a given retracement band behave differently afterwards than
price reaching any other band, or a random one.

The correctness detail everything rests on: a fractal pivot at bar `i` is only
**knowable** at bar `i + lookback`, because it takes that many later bars to
confirm nothing exceeded it. A zone drawn from it may therefore not be used
before `i + lookback`. Getting this wrong would let the study see the future
and quietly manufacture an edge.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Zone half-width as a fraction of the swing range. The golden pocket spans
#: 0.618 -> 0.66, i.e. 0.042; every comparison zone gets the same width so the
#: test is not "a band versus a line".
ZONE_WIDTH = 0.042
ZONE_HALF = ZONE_WIDTH / 2.0

LEVELS = {"Z1_0382": 0.382, "Z2_0500": 0.500, "Z3_golden": 0.639, "Z4_0786": 0.786}
RANDOM_ZONE = "Z5_random"
RANDOM_RANGE = (0.30, 0.90)


@dataclass(frozen=True)
class Swing:
    """A completed leg between two confirmed pivots."""

    start: int          # bar index of the first pivot
    end: int            # bar index of the second pivot
    start_price: float
    end_price: float
    up: bool            # True when the leg ran low -> high
    usable_from: int    # first bar at which the end pivot is confirmed

    @property
    def span(self) -> float:
        return abs(self.end_price - self.start_price)

    def zone_price(self, level: float) -> tuple:
        """Price band for `level`, retracing from `end_price` back toward start."""
        lo_level, hi_level = level - ZONE_HALF, level + ZONE_HALF
        if self.up:                      # retrace of an up leg -> price falls
            a = self.end_price - self.span * hi_level
            b = self.end_price - self.span * lo_level
        else:                            # retrace of a down leg -> price rises
            a = self.end_price + self.span * lo_level
            b = self.end_price + self.span * hi_level
        return (min(a, b), max(a, b))


def fractal_pivots(high: np.ndarray, low: np.ndarray, lookback: int) -> list:
    """Confirmed fractal pivots as `(index, is_high)`, chronological.

    A pivot needs `lookback` bars strictly on each side, so the earliest
    possible pivot is at index `lookback` and the latest at `n - lookback - 1`.
    """
    pivots = []
    n = len(high)
    for i in range(lookback, n - lookback):
        window_hi = high[i - lookback:i + lookback + 1]
        window_lo = low[i - lookback:i + lookback + 1]
        if high[i] == window_hi.max() and np.count_nonzero(window_hi == high[i]) == 1:
            pivots.append((i, True))
        elif low[i] == window_lo.min() and np.count_nonzero(window_lo == low[i]) == 1:
            pivots.append((i, False))
    return pivots


def swings(high: np.ndarray, low: np.ndarray, close: np.ndarray,
           lookback: int) -> list:
    """Alternating pivot pairs. Consecutive same-type pivots keep the extreme."""
    pivots = fractal_pivots(high, low, lookback)
    cleaned = []
    for index, is_high in pivots:
        if cleaned and cleaned[-1][1] == is_high:
            prev_index = cleaned[-1][0]
            better = (high[index] > high[prev_index]) if is_high else (low[index] < low[prev_index])
            if better:
                cleaned[-1] = (index, is_high)
            continue
        cleaned.append((index, is_high))

    out = []
    for (i0, hi0), (i1, hi1) in zip(cleaned, cleaned[1:]):
        p0 = high[i0] if hi0 else low[i0]
        p1 = high[i1] if hi1 else low[i1]
        if p0 == p1:
            continue
        out.append(Swing(start=i0, end=i1, start_price=float(p0), end_price=float(p1),
                         up=bool(hi1), usable_from=i1 + lookback))
    return out


def first_touch(low: np.ndarray, high: np.ndarray, band: tuple,
                start: int, stop: int) -> int:
    """First bar in [start, stop) whose range intersects `band`, else -1."""
    lo, hi = band
    for i in range(max(start, 0), min(stop, len(low))):
        if low[i] <= hi and high[i] >= lo:
            return i
    return -1


def observations(high, low, close, lookback, horizons, rng, max_wait=None) -> dict:
    """One observation per swing per zone: the first touch after confirmation.

    `max_wait` bounds how long a zone stays live. Defaults to the swing's own
    duration, so a zone from a three-day leg is not still being watched a year
    later — the bound comes from the swing, not from a tuned constant.
    """
    result = {name: [] for name in list(LEVELS) + [RANDOM_ZONE]}
    horizon_max = max(horizons)
    for swing in swings(high, low, close, lookback):
        levels = dict(LEVELS)
        levels[RANDOM_ZONE] = float(rng.uniform(*RANDOM_RANGE))
        window = max_wait if max_wait is not None else max(swing.end - swing.start, 1)
        stop = min(swing.usable_from + window, len(close) - horizon_max)
        for name, level in levels.items():
            touch = first_touch(low, high, swing.zone_price(level),
                                swing.usable_from, stop)
            if touch < 0:
                continue
            entry = float(close[touch])
            row = {"swing_start": swing.start, "swing_end": swing.end,
                   "touch": int(touch), "up": swing.up, "level": level}
            for h in horizons:
                move = float(close[touch + h]) / entry - 1.0
                # Measured in the direction the retracement implies resuming.
                row[f"fwd_{h}"] = move if swing.up else -move
            result[name].append(row)
    return result


def baseline(close: np.ndarray, horizons, start: int) -> dict:
    """Unconditional forward returns from every bar, both directions pooled.

    Retracement observations are half up-legs and half down-legs, so the
    baseline must be direction-symmetric or the comparison would inherit BTC's
    secular uptrend as a free edge.
    """
    out = {}
    for h in horizons:
        moves = close[start + h:] / close[start:-h] - 1.0
        out[h] = np.concatenate([moves, -moves])
    return out
