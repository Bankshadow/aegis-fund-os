"""E36 — EMA9/21 + RSI filter arms for the leveraged perp engine.

Criteria in `docs/E36_CRITERIA.md`, declared before this file existed.

Signals only. Position accounting, intrabar liquidation, funding and costs all
live in `dynamic_grid/leveraged.py` (the E31 engine) — this module never touches
equity, so a signal bug cannot quietly become a P&L bug.

Every indicator is causal: the value at bar `i` uses bars `0..i` only, and the
weight it produces takes effect at `close[i]`.
"""

from __future__ import annotations

import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    """Standard EMA seeded with the first `period` mean; NaN until seeded."""
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    out[period - 1] = values[:period].mean()
    for i in range(period, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI. NaN until the first smoothed average exists."""
    n = len(values)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    delta = np.diff(values)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for i in range(period, n):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


#: The four declared readings of "loose RSI" (§1 of the criteria). Each returns
#: True when the RSI permits the trade. R0 is the control that permits
#: everything — if the filtered arms do not beat it, the filter does nothing.
def _r0(_value, _long):
    return True


def _r1(value, long):
    if np.isnan(value):
        return False
    return value > 50.0 if long else value < 50.0


def _r2(value, long):
    if np.isnan(value):
        return False
    return value <= 70.0 if long else value >= 30.0


def _r3(value, long):
    if np.isnan(value):
        return False
    return value >= 30.0 if long else value <= 70.0


RSI_ARMS = {"R0_none": _r0, "R1_above50": _r1, "R2_no_chase": _r2, "R3_not_against": _r3}


class EmaRsi:
    """EMA fast/slow cross, gated by one RSI reading, at fixed gross leverage.

    `weights(i)` returns the target weight vector for a single-asset panel:
    `+leverage` long, `-leverage` short, `0` flat. Long/short by default; set
    `long_only=True` to drop the short leg (declared robustness arm).
    """

    def __init__(self, closes: np.ndarray, asset: int = 0, fast: int = 9, slow: int = 21,
                 rsi_period: int = 14, arm: str = "R1_above50", leverage: float = 5.0,
                 long_only: bool = False, name: str | None = None):
        series = closes[:, asset]
        self.n_assets = closes.shape[1]
        self.asset = asset
        self.fast = ema(series, fast)
        self.slow = ema(series, slow)
        self.rsi = rsi(series, rsi_period)
        self.gate = RSI_ARMS[arm]
        self.leverage = float(leverage)
        self.long_only = long_only
        self.name = name or f"EMA{fast}/{slow}+{arm}_{leverage:g}x{'_long' if long_only else ''}"

    def weights(self, i: int) -> np.ndarray:
        w = np.zeros(self.n_assets)
        fast, slow, strength = self.fast[i], self.slow[i], self.rsi[i]
        if np.isnan(fast) or np.isnan(slow):
            return w
        if fast > slow:
            if self.gate(strength, True):
                w[self.asset] = self.leverage
        elif fast < slow and not self.long_only:
            if self.gate(strength, False):
                w[self.asset] = -self.leverage
        return w


def count_trades(weights_log: np.ndarray) -> dict:
    """Round trips and per-trade returns from the realised weight path.

    A trade opens when the weight leaves zero and closes when it returns to
    zero or flips sign. Counted from the weight path the engine actually
    executed, never from the raw signal, so blocked or liquidated positions
    are reflected.
    """
    trades = []
    side = 0.0
    for i, w in enumerate(weights_log):
        if side == 0.0 and w != 0.0:
            side, entry = w, i
        elif side != 0.0 and (w == 0.0 or np.sign(w) != np.sign(side)):
            trades.append((entry, i, side))
            side, entry = (w, i) if w != 0.0 else (0.0, i)
    return {"count": len(trades), "spans": trades}
