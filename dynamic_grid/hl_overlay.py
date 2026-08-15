"""E43 — Hyperliquid fee activity as BTC risk-on overlay (Osmo S3).

Criteria in `docs/E43_CRITERIA.md`, declared before this file existed.

Signals only: returns are owned by `dynamic_grid.cadence.simulate`.
"""

from __future__ import annotations

import numpy as np

from dynamic_grid.cadence import sma, sma_state
from dynamic_grid.trend_sizing import realized_vol

RANK_WINDOW = 90
GATE = 0.50
SMA_PERIOD = 200
TARGET_VOL = 0.40
CADENCE = 21
WARMUP = 90
OOS = 90
HELD_OUT = 90
FWD = 21


def align_fees_to_dates(fee_chart: list, dates_ms: np.ndarray) -> np.ndarray:
    """Map DefiLlama [sec, fee] onto Binance day-open ms timestamps."""
    by_day = {int(row[0]) * 1000: float(row[1]) for row in fee_chart}
    return np.array([by_day.get(int(t), np.nan) for t in dates_ms], dtype=float)


def fee_percentile(fees: np.ndarray, window: int = RANK_WINDOW) -> np.ndarray:
    """Trailing percentile of fees[i] in fees[i-window+1:i+1]. Causal."""
    out = np.full(len(fees), np.nan)
    for i in range(len(fees)):
        if not np.isfinite(fees[i]):
            continue
        lo = max(0, i - window + 1)
        hist = fees[lo:i + 1]
        hist = hist[np.isfinite(hist)]
        if len(hist) < 20:
            continue
        out[i] = float(np.mean(hist <= fees[i]))
    return out


def arms(close: np.ndarray, fees: np.ndarray) -> dict[str, np.ndarray]:
    """Declared weight series. NaN where undefined."""
    trend = sma_state(close, SMA_PERIOD)
    p = fee_percentile(fees, RANK_WINDOW)
    vol = realized_vol(close, 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        inv = np.where(vol > 0, TARGET_VOL / vol, np.nan)
    inv = np.clip(inv, 0.0, 1.0)

    h_gate = np.where(np.isnan(trend) | np.isnan(p), np.nan,
                      np.where((trend > 0) & (p >= GATE), 1.0, 0.0))
    h_size = np.where(np.isnan(trend) | np.isnan(p), np.nan, trend * p)
    h_only = p.copy()
    c_vol = np.where(np.isnan(trend) | np.isnan(inv), np.nan, trend * inv)

    return {
        "B0_buy_hold": np.ones(len(close)),
        "T1_trend": trend,
        "H_gate": h_gate,
        "H_size": h_size,
        "H_only": h_only,
        "C_vol": c_vol,
    }


def spearman_p_vs_forward(close: np.ndarray, p: np.ndarray,
                          horizon: int = FWD, warmup: int = WARMUP) -> dict:
    """P1: association between HL percentile and forward BTC return."""
    n = len(close)
    fwd = np.full(n, np.nan)
    fwd[: n - horizon] = close[horizon:] / close[: n - horizon] - 1.0
    usable = np.isfinite(p) & np.isfinite(fwd)
    usable[:warmup] = False
    if usable.sum() < 30:
        return {"spearman": None, "permutation_percentile": None, "n": int(usable.sum())}

    x = p[usable]
    y = fwd[usable]
    # rank correlation
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    spearman = float(np.corrcoef(rx, ry)[0, 1])

    rng = np.random.default_rng(0)
    null = np.empty(1000)
    for i in range(1000):
        yy = rng.permutation(y)
        ryy = np.argsort(np.argsort(yy)).astype(float)
        null[i] = np.corrcoef(rx, ryy)[0, 1]
    return {
        "spearman": spearman,
        "permutation_percentile": float(np.mean(null < spearman)),
        "n": int(usable.sum()),
    }


def oos_windows(n: int, warmup: int = WARMUP, oos: int = OOS,
                held_out: int = HELD_OUT) -> list[tuple[int, int]]:
    end = n - held_out
    out = []
    t = warmup
    while t + oos <= end:
        out.append((t, t + oos))
        t += oos
    return out
