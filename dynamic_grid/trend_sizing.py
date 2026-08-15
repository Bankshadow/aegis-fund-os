"""E42 — graded exposure from trend strength, for the cadence engine.

Criteria in `docs/E42_CRITERIA.md`, declared before this file existed.

Signals only: every arm returns a target-weight series in [0, 1] and the
`cadence` engine owns drift, turnover, cost and equity. Nothing here computes
a return, so a sizing bug cannot silently become a P&L bug.

All indicators are causal — the value at bar `i` uses bars `0..i` only.
"""

from __future__ import annotations

import numpy as np

from dynamic_grid.cadence import sma

RANK_WINDOW = 252
SMA_PERIOD = 200
VOL_LOOKBACK = 20
TARGET_VOL = 0.40
TRADING_DAYS = 365


def raw_strength(close: np.ndarray, period: int = SMA_PERIOD) -> np.ndarray:
    """`close / SMA(period) - 1`. NaN until the average is seeded."""
    ma = sma(close, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isnan(ma), np.nan, close / ma - 1.0)


def percentile_rank(values: np.ndarray, window: int = RANK_WINDOW) -> np.ndarray:
    """Rank of each value inside its own trailing `window`, in [0, 1].

    Raw distance-above-average is not comparable across eras — the same +5%
    means something different in a calm year and a violent one. Ranking against
    the asset's own recent history is the detector E14 already validated, so
    this is not a new parameter.
    """
    out = np.full(len(values), np.nan)
    for i in range(len(values)):
        if np.isnan(values[i]):
            continue
        lo = max(0, i - window + 1)
        history = values[lo:i + 1]
        history = history[~np.isnan(history)]
        if len(history) < 20:          # too short to rank against
            continue
        out[i] = float(np.mean(history <= values[i]))
    return out


def realized_vol(close: np.ndarray, lookback: int = VOL_LOOKBACK) -> np.ndarray:
    """Annualised standard deviation of log returns over `lookback` bars."""
    out = np.full(len(close), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        returns = np.concatenate([[np.nan], np.diff(np.log(close))])
    for i in range(lookback, len(close)):
        window = returns[i - lookback + 1:i + 1]
        if np.isnan(window).any():
            continue
        out[i] = float(np.std(window, ddof=1) * np.sqrt(TRADING_DAYS))
    return out


# --------------------------------------------------------------------------
# the five declared arms (E42 section 4) — no parameter is tuned here
# --------------------------------------------------------------------------

def a0_buy_hold(close: np.ndarray) -> np.ndarray:
    return np.ones(len(close))


def a1_binary(close: np.ndarray) -> np.ndarray:
    """1.0 above the 200-day average, 0.0 below. Reproduces E34's C2."""
    ma = sma(close, SMA_PERIOD)
    state = np.where(close > ma, 1.0, 0.0)
    return np.where(np.isnan(ma), np.nan, state)


def a2_graded(close: np.ndarray) -> np.ndarray:
    """Weight = percentile rank of trend strength. The claim under test."""
    return percentile_rank(raw_strength(close))


def a3_inverse_vol(close: np.ndarray) -> np.ndarray:
    """Size by risk, not by trend. Control for R5."""
    vol = realized_vol(close)
    with np.errstate(invalid="ignore", divide="ignore"):
        weight = np.where(vol > 0, TARGET_VOL / vol, np.nan)
    return np.clip(weight, 0.0, 1.0)


def a4_constant(close: np.ndarray, fraction: float) -> np.ndarray:
    """No signal at all, held at `fraction`. Control for R4 (E34's K6)."""
    return np.full(len(close), float(np.clip(fraction, 0.0, 1.0)))


def rescale_from_warmup(weights: np.ndarray, target_mean: float,
                        warmup: int) -> np.ndarray:
    """Scale `weights` so its warm-up mean equals `target_mean`.

    The factor is computed from the warm-up window only, so the live path never
    sees a statistic drawn from its own future.
    """
    head = weights[:warmup]
    head = head[~np.isnan(head)]
    if len(head) == 0 or head.mean() <= 0:
        return weights
    return np.clip(weights * (target_mean / head.mean()), 0.0, 1.0)


def decile_forward_returns(close: np.ndarray, strength: np.ndarray,
                           horizon: int = 21, warmup: int = 252) -> dict:
    """P1 — mean forward return per strength decile, measured before any backtest.

    If the strength carries no graded information, the deciles are flat and the
    whole premise of E42 is wrong.
    """
    n = len(close)
    forward = np.full(n, np.nan)
    forward[:n - horizon] = close[horizon:] / close[:n - horizon] - 1.0
    usable = (~np.isnan(strength)) & (~np.isnan(forward))
    usable[:warmup] = False

    values, returns = strength[usable], forward[usable]
    edges = np.quantile(values, np.linspace(0, 1, 11))
    means, counts = [], []
    for k in range(10):
        lo, hi = edges[k], edges[k + 1]
        sel = (values >= lo) & (values <= hi) if k == 9 else (values >= lo) & (values < hi)
        means.append(float(returns[sel].mean()) if sel.any() else np.nan)
        counts.append(int(sel.sum()))

    order = np.arange(1, 11, dtype=float)
    valid = ~np.isnan(means)
    spearman = float(np.corrcoef(order[valid], np.argsort(np.argsort(np.array(means)[valid])) + 1.0)[0, 1])

    rng = np.random.default_rng(0)
    shuffled = []
    for _ in range(1000):
        permuted = rng.permutation(returns)
        m = []
        for k in range(10):
            lo, hi = edges[k], edges[k + 1]
            sel = (values >= lo) & (values <= hi) if k == 9 else (values >= lo) & (values < hi)
            m.append(permuted[sel].mean() if sel.any() else np.nan)
        m = np.array(m)
        ok = ~np.isnan(m)
        shuffled.append(np.corrcoef(order[ok], np.argsort(np.argsort(m[ok])) + 1.0)[0, 1])
    percentile = float(np.mean(np.array(shuffled) < spearman))

    return {"decile_means": means, "decile_counts": counts,
            "spearman": spearman, "permutation_percentile": percentile,
            "n": int(usable.sum())}
