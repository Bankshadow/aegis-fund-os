"""E36 — volume-regime measurement (Koroush three patterns).

Criteria in `docs/E36_CRITERIA.md`, declared before this file existed.

Pure measurement: no orders, no sizing, no strategy. It answers whether the
volume regime at bar i predicts which signed forward return (continuation vs
fade) is active — nothing more.

Classification at bar i uses only data through i. Getting that wrong would let
the study see the future and quietly manufacture an edge.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

REGIMES = ("SPIKE", "INCREASING", "DECREASING", "FLAT")
SPIKE_VOL_MULT = 3.0
HORIZONS = (5, 10, 20)
WINDOWS = (5, 10, 20)


@dataclass(frozen=True)
class BarLabel:
    """One classified bar with signed scores at each horizon."""

    index: int
    regime: str
    direction: int          # sign(close[i] - close[i-1]), never 0 in stored rows
    continuation: dict      # horizon -> float
    fade: dict              # horizon -> float


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """TR[i] uses close[i-1]; TR[0] is high-low."""
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    return np.maximum(high - low,
                      np.maximum(np.abs(high - prev_close),
                                 np.abs(low - prev_close)))


def atr_sma(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 14) -> np.ndarray:
    """SMA of TR over the prior `period` bars. atr[i] uses TR[i-period:i] only.

    atr[i] is NaN when fewer than `period` prior bars exist.
    """
    tr = true_range(high, low, close)
    atr = np.full(len(close), np.nan)
    for i in range(period, len(close)):
        atr[i] = tr[i - period:i].mean()
    return atr


def classify_bar(quote_vol: np.ndarray, close: np.ndarray, atr: np.ndarray,
                 i: int, window: int) -> str | None:
    """Regime at bar i using only data <= i. None when not classifiable."""
    if i < max(window, 14) or i >= len(close):
        return None
    if not np.isfinite(atr[i]) or atr[i] <= 0 or close[i - 1] <= 0:
        return None
    if close[i] == close[i - 1]:
        return None

    prior = quote_vol[i - window + 1:i]   # excludes i; length window-1 when...
    # Need window bars ending at i for diffs, and median of the bars before i
    # inside the window. Criteria: median(quote_volume[i-W+1 : i]) — length W-1.
    if len(prior) < window - 1 or window < 2:
        return None
    median_prior = float(np.median(prior))
    if median_prior <= 0:
        return None

    vol_spike = quote_vol[i] >= SPIKE_VOL_MULT * median_prior
    ret = abs(np.log(close[i] / close[i - 1]))
    price_spike = ret >= (atr[i] / close[i - 1])
    if vol_spike and price_spike:
        return "SPIKE"

    window_vols = quote_vol[i - window + 1:i + 1]
    diffs = np.diff(window_vols)
    if np.all(diffs > 0):
        return "INCREASING"
    if np.all(diffs < 0):
        return "DECREASING"
    return "FLAT"


def classify_series(quote_vol: np.ndarray, close: np.ndarray,
                    high: np.ndarray, low: np.ndarray,
                    window: int) -> list[str | None]:
    atr = atr_sma(high, low, close, 14)
    return [classify_bar(quote_vol, close, atr, i, window)
            for i in range(len(close))]


def observations(quote_vol: np.ndarray, close: np.ndarray,
                 high: np.ndarray, low: np.ndarray,
                 window: int, horizons: tuple = HORIZONS) -> dict[str, list[BarLabel]]:
    """Partition bars into regimes; one observation per bar with nonzero move."""
    atr = atr_sma(high, low, close, 14)
    n = len(close)
    max_h = max(horizons)
    out = {name: [] for name in REGIMES}
    for i in range(n - max_h):
        regime = classify_bar(quote_vol, close, atr, i, window)
        if regime is None:
            continue
        delta = close[i] - close[i - 1]
        direction = 1 if delta > 0 else -1
        cont = {}
        fade = {}
        for h in horizons:
            fwd = close[i + h] / close[i] - 1.0
            cont[h] = direction * fwd
            fade[h] = -direction * fwd
        out[regime].append(BarLabel(index=i, regime=regime, direction=direction,
                                    continuation=cont, fade=fade))
    return out


def price_only_spike_mask(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                          window: int) -> np.ndarray:
    """Control B: price spike without volume requirement."""
    atr = atr_sma(high, low, close, 14)
    mask = np.zeros(len(close), dtype=bool)
    for i in range(max(window, 14), len(close)):
        if not np.isfinite(atr[i]) or close[i - 1] <= 0 or close[i] == close[i - 1]:
            continue
        ret = abs(np.log(close[i] / close[i - 1]))
        mask[i] = ret >= (atr[i] / close[i - 1])
    return mask


def volume_only_spike_mask(quote_vol: np.ndarray, close: np.ndarray,
                           window: int) -> np.ndarray:
    """Control C: volume spike without price requirement."""
    mask = np.zeros(len(quote_vol), dtype=bool)
    for i in range(max(window, 14), len(quote_vol)):
        if close[i] == close[i - 1]:
            continue
        prior = quote_vol[i - window + 1:i]
        if len(prior) < window - 1:
            continue
        median_prior = float(np.median(prior))
        if median_prior <= 0:
            continue
        mask[i] = quote_vol[i] >= SPIKE_VOL_MULT * median_prior
    return mask


def mean_score(rows: list[BarLabel], horizon: int, kind: str) -> float | None:
    if not rows:
        return None
    if kind == "continuation":
        return float(np.mean([r.continuation[horizon] for r in rows]))
    if kind == "fade":
        return float(np.mean([r.fade[horizon] for r in rows]))
    raise ValueError(kind)


def bootstrap_diff_percentile(group_a: list[BarLabel], group_b: list[BarLabel],
                              horizon: int, kind: str,
                              samples: int, rng: np.random.Generator) -> dict | None:
    """Percentile of (mean_a - mean_b) under label-shuffle of the pooled set."""
    if len(group_a) < 2 or len(group_b) < 2:
        return None
    key = (lambda r: r.continuation[horizon] if kind == "continuation"
           else r.fade[horizon])
    a_vals = np.array([key(r) for r in group_a], dtype=float)
    b_vals = np.array([key(r) for r in group_b], dtype=float)
    real_diff = float(a_vals.mean() - b_vals.mean())
    pooled = np.concatenate([a_vals, b_vals])
    n_a = len(a_vals)
    diffs = np.empty(samples)
    for s in range(samples):
        rng.shuffle(pooled)
        diffs[s] = pooled[:n_a].mean() - pooled[n_a:].mean()
    return {
        "a_mean": float(a_vals.mean()),
        "b_mean": float(b_vals.mean()),
        "diff": real_diff,
        "n_a": int(n_a),
        "n_b": int(len(b_vals)),
        "percentile": float(np.mean(diffs < real_diff)),
    }


def scores_on_mask(close: np.ndarray, mask: np.ndarray, horizons: tuple,
                   kind: str) -> dict:
    """Continuation or fade scores on bars where mask is True."""
    out = {h: [] for h in horizons}
    max_h = max(horizons)
    for i in range(1, len(close) - max_h):
        if not mask[i]:
            continue
        if close[i] == close[i - 1]:
            continue
        direction = 1 if close[i] > close[i - 1] else -1
        for h in horizons:
            fwd = close[i + h] / close[i] - 1.0
            score = direction * fwd if kind == "continuation" else -direction * fwd
            out[h].append(score)
    return {h: {"n": len(v),
                "mean": float(np.mean(v)) if v else None}
            for h, v in out.items()}
