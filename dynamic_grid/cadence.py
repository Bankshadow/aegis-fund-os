"""E34 — long-only fractional-exposure backtester with an explicit decision cadence.

Criteria in `docs/E34_CRITERIA.md`, declared before this file existed.

The one variable E30/E31/E32 never moved is here: **how often the signal is
read**. Every prior BTC candidate decided daily. A weight is chosen only on a
decision day and held flat until the next one, so `cadence=1` reproduces the
daily behaviour and `cadence=21` is the same signal sampled monthly.

Rules fixed by §4 of the criteria and not tunable here:

* long-only spot, no leverage, no short: weight is clamped to [0, 1]
* cost `COST_PER_SIDE` is charged on the **change** in weight, not the whole
  book, so a fractional strategy pays for what it actually trades
* the weight for bar `i` is decided from bars 0..i and earns bar `i+1`'s return
  — the decision never sees the return it is paid for
"""

from __future__ import annotations

import numpy as np

COST_PER_SIDE = 0.0015  # 0.10% taker + 0.05% slippage, same as E30
TRADING_DAYS = 365      # crypto trades every day (E31 correction)


def sma(values: np.ndarray, period: int) -> np.ndarray:
    """Causal simple moving average; NaN until the window is full."""
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return out
    csum = np.cumsum(np.insert(values, 0, 0.0))
    out[period - 1:] = (csum[period:] - csum[:-period]) / period
    return out


def sma_state(close: np.ndarray, period: int = 200) -> np.ndarray:
    """1.0 where close is above its own SMA, 0.0 below, NaN while warming up."""
    ma = sma(close, period)
    state = np.where(close > ma, 1.0, 0.0)
    return np.where(np.isnan(ma), np.nan, state)


def simulate(close: np.ndarray, target: np.ndarray, cadence: int,
             floor: float = 0.0, initial: float = 10_000.0) -> dict:
    """Simulate a two-leg book (risky + cash) with an explicit decision cadence.

    This exists because a weight path alone cannot price a fractional book. The
    realised weight moves every day as the asset moves, but **drift is not a
    trade** — nobody bought or sold. Charging turnover on the day-to-day change
    in realised weight billed the monthly constant-mix control for ~364 trades
    a year that never happened, and counted them against its decision budget.

    Cost is charged only on the value actually traded, only on a decision day.
    Weight `w[i]` is in force for the move from `close[i]` to `close[i+1]`.
    """
    n = len(close)
    invested, cash = 0.0, float(initial)
    equity = np.empty(n)
    weights = np.empty(n)
    trades = 0
    traded_value = 0.0

    for i in range(n):
        if i % cadence == 0:
            book = invested + cash
            value = target[i]
            wanted = 0.0 if np.isnan(value) else max(float(value), floor)
            wanted = min(max(wanted, 0.0), 1.0)
            delta = abs(book * wanted - invested)
            if delta > book * 1e-12:
                # Cost comes out of the book before allocating, never booked as
                # negative cash: doing that pushed weight above 1.0 on a fully
                # invested book and made buy-and-hold "trade" every single day.
                book -= delta * COST_PER_SIDE
                invested = book * wanted
                cash = book - invested
                trades += 1
                traded_value += delta
        book = invested + cash
        equity[i] = book
        weights[i] = invested / book if book > 0 else 0.0
        if i + 1 < n:
            invested *= close[i + 1] / close[i]

    return {"equity": equity, "weights": weights,
            "trades": trades, "traded_value": traded_value}


def sampled(target: np.ndarray, cadence: int, close: np.ndarray,
            floor: float = 0.0) -> np.ndarray:
    """Realised weight path: set the target on a decision day, then let it drift.

    Between decision days nobody trades, so a partly-invested book does **not**
    hold its weight — the risky leg compounds while cash does not, and the
    weight rises as the asset rises. Holding the target flat instead would
    invent a free daily rebalance, which is both a missing cost and a missing
    buy-low-sell-high benefit. It matters only for fractional books (C4, C5):
    at weight 0 or 1 there is nothing to drift.

    `cadence=1` reproduces daily behaviour exactly. Warm-up NaN means no
    signal, so the position is flat — never a guess, and the floor does not
    apply before the signal exists.
    """
    weights = np.zeros(len(target))
    invested = 0.0        # value of the risky leg, in units of book value 1.0
    cash = 1.0
    for i, value in enumerate(target):
        if i % cadence == 0:
            book = invested + cash
            wanted = 0.0 if np.isnan(value) else max(float(value), floor)
            wanted = min(max(wanted, 0.0), 1.0)
            invested, cash = book * wanted, book * (1.0 - wanted)
        book = invested + cash
        weights[i] = invested / book if book > 0 else 0.0
        if i + 1 < len(close):
            invested *= close[i + 1] / close[i]
    return np.clip(weights, 0.0, 1.0)


def equity_curve(close: np.ndarray, weights: np.ndarray,
                 initial: float = 10_000.0) -> np.ndarray:
    """Equity from a weight path, charging cost on every change in weight.

    Weight `w[i]` is in force for the move from `close[i]` to `close[i+1]`, so
    the curve has `len(close)` points and the last weight earns nothing.
    """
    equity = np.empty(len(close))
    equity[0] = initial
    cash = initial
    previous = 0.0
    for i in range(len(close) - 1):
        turnover = abs(weights[i] - previous)
        cash *= (1.0 - turnover * COST_PER_SIDE)
        previous = weights[i]
        step = close[i + 1] / close[i] - 1.0
        cash *= (1.0 + weights[i] * step)
        equity[i + 1] = cash
    return equity


def metrics(run: dict) -> dict:
    """Return, max drawdown, robust score, exposure and real trade counts.

    `trades` comes from the simulation, never inferred from the weight path:
    a fractional book's weight moves daily without anyone trading.
    """
    equity, weights = run["equity"], run["weights"]
    initial = float(equity[0])
    total = float(equity[-1]) / initial - 1.0
    peak = np.maximum.accumulate(equity)
    max_dd = float(np.max((peak - equity) / peak))
    years = max(len(equity) / TRADING_DAYS, 1e-9)
    cagr = (float(equity[-1]) / initial) ** (1.0 / years) - 1.0
    return {
        "total_return": total,
        "cagr": cagr,
        "max_dd": max_dd,
        "robust": total - 2.0 * max_dd,     # project definition, unchanged
        "exposure": float(np.mean(weights)),
        "trades": int(run["trades"]),
        "trades_per_year": run["trades"] / years,
        "final_equity": float(equity[-1]),
    }


# --------------------------------------------------------------------------
# candidates — parameters fixed a priori by §4/§5, no tuning pass
# --------------------------------------------------------------------------

def targets(close: np.ndarray, mix_fraction: float) -> dict:
    """The six declared candidates as `(target, cadence, floor)` specs.

    Signals are computed on the **full** history so a walk-forward window can
    be simulated in isolation without re-warming SMA-200 inside the window —
    which would blind the first 200 bars of every fold.
    `mix_fraction` is C2's realised exposure; C4 is matched to it by §5.
    """
    state = sma_state(close, 200)
    flat = np.full(len(close), float(np.clip(mix_fraction, 0.0, 1.0)))
    return {
        "C0_buy_hold": (np.ones(len(close)), 1, 0.0),
        "C1_sma200_daily": (state, 1, 0.0),
        "C2_sma200_monthly": (state, 21, 0.0),
        "C3_sma200_quarterly": (state, 63, 0.0),
        # No signal at all: rebalance back to `mix_fraction` monthly. The
        # control separating "the trend filter works" from "you held less".
        "C4_constant_mix_monthly": (flat, 21, 0.0),
        "C5_sma200_monthly_floor50": (state, 21, 0.5),
    }


def run_segment(close: np.ndarray, spec: tuple, lo: int = 0, hi: int = None,
                initial: float = 10_000.0) -> dict:
    """Simulate one candidate over `close[lo:hi]` using its full-history target."""
    target, cadence, floor = spec
    hi = len(close) if hi is None else hi
    return simulate(close[lo:hi], target[lo:hi], cadence, floor, initial)
