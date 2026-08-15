"""E39 — crowded-long fade measurement (Osmo S1).

Criteria in `docs/E39_CRITERIA.md`, declared before this file existed.

Classification at bar i uses only data through i. Fade score is the signed
return of fading an up-impulse; positive means the fade would have paid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LS_THRESH = 1.50
FUNDING_THRESH = 0.0001
OI_LOOKBACK = 24
IMPULSE_ATR_MULT = 0.5
HORIZONS = (4, 12, 24)
PRIMARY_H = 12
BOOTSTRAP = 10_000


@dataclass(frozen=True)
class Panel:
    """Aligned 1h series (no lookahead fields)."""

    ts: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    ls_ratio: np.ndarray
    oi_value: np.ndarray
    funding: np.ndarray  # forward-filled to each hour


def atr_sma_prior(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                  period: int = 14) -> np.ndarray:
    """ATR[i] = mean(TR[i-period:i]); NaN until enough prior bars."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev = close[:-1]
    tr[1:] = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - prev),
        np.abs(low[1:] - prev),
    ])
    atr = np.full(n, np.nan)
    for i in range(period, n):
        atr[i] = tr[i - period:i].mean()
    return atr


def align_panel(raw: dict) -> Panel:
    """Join L/S, OI, funding, klines on 1h open timestamps."""
    ls_map = {int(r["timestamp"]): float(r["longShortRatio"]) for r in raw["long_short"]}
    oi_map = {
        int(r["timestamp"]): float(r["sumOpenInterestValue"])
        for r in raw["open_interest"]
    }
    fund_events = sorted(
        ((int(r["fundingTime"]), float(r["fundingRate"])) for r in raw["funding"]),
        key=lambda x: x[0],
    )

    rows = []
    for k in raw["klines_1h"]:
        ts = int(k[0])
        if ts not in ls_map or ts not in oi_map:
            continue
        rows.append((
            ts,
            float(k[1]), float(k[2]), float(k[3]), float(k[4]),
            ls_map[ts], oi_map[ts],
        ))
    if not rows:
        raise ValueError("no overlapping L/S + OI + kline bars")

    ts = np.array([r[0] for r in rows], dtype=np.int64)
    open_ = np.array([r[1] for r in rows])
    high = np.array([r[2] for r in rows])
    low = np.array([r[3] for r in rows])
    close = np.array([r[4] for r in rows])
    ls_ratio = np.array([r[5] for r in rows])
    oi_value = np.array([r[6] for r in rows])

    funding = np.full(len(ts), np.nan)
    fi = 0
    last = np.nan
    for i, t in enumerate(ts):
        while fi < len(fund_events) and fund_events[fi][0] <= t:
            last = fund_events[fi][1]
            fi += 1
        funding[i] = last

    return Panel(ts=ts, open=open_, high=high, low=low, close=close,
                 ls_ratio=ls_ratio, oi_value=oi_value, funding=funding)


def masks(panel: Panel) -> dict[str, np.ndarray]:
    """Boolean masks for each arm; True only where classifiable."""
    atr = atr_sma_prior(panel.high, panel.low, panel.close, 14)
    n = len(panel.close)
    crowded = np.zeros(n, dtype=bool)
    fund_hi = np.zeros(n, dtype=bool)
    ls_hi = np.zeros(n, dtype=bool)
    oi_up = np.zeros(n, dtype=bool)
    impulse = np.zeros(n, dtype=bool)

    for i in range(n):
        if i < max(14, OI_LOOKBACK) or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        if not np.isfinite(panel.funding[i]):
            continue
        fund_hi[i] = panel.funding[i] >= FUNDING_THRESH
        ls_hi[i] = panel.ls_ratio[i] >= LS_THRESH
        oi_up[i] = panel.oi_value[i] > panel.oi_value[i - OI_LOOKBACK]
        crowded[i] = fund_hi[i] and ls_hi[i] and oi_up[i]
        up = panel.close[i] > panel.close[i - 1]
        move = panel.close[i] - panel.close[i - 1]
        impulse[i] = up and move >= IMPULSE_ATR_MULT * atr[i]

    return {
        "S_full": crowded & impulse,
        "S_fund": fund_hi & impulse,
        "S_ls": ls_hi & impulse,
        "S_oi": oi_up & impulse,
        "S_imp": impulse,
        "crowded": crowded,
        "fund_hi": fund_hi,
        "ls_hi": ls_hi,
        "oi_up": oi_up,
        "impulse": impulse,
    }


def fade_scores(close: np.ndarray, mask: np.ndarray, horizon: int) -> np.ndarray:
    """Fade scores at bars where mask is True and i+horizon exists."""
    out = []
    n = len(close)
    for i in range(n - horizon):
        if not mask[i]:
            continue
        fwd = close[i + horizon] / close[i] - 1.0
        out.append(-fwd)
    return np.array(out, dtype=float)


def bootstrap_diff_percentile(a: np.ndarray, b: np.ndarray, samples: int,
                              rng: np.random.Generator) -> dict | None:
    if len(a) < 2 or len(b) < 2:
        return None
    real = float(a.mean() - b.mean())
    pooled = np.concatenate([a, b])
    n_a = len(a)
    diffs = np.empty(samples)
    for s in range(samples):
        rng.shuffle(pooled)
        diffs[s] = pooled[:n_a].mean() - pooled[n_a:].mean()
    return {
        "a_mean": float(a.mean()),
        "b_mean": float(b.mean()),
        "diff": real,
        "n_a": int(len(a)),
        "n_b": int(len(b)),
        "percentile": float(np.mean(diffs < real)),
    }


def arm_summary(close: np.ndarray, mask: np.ndarray,
                horizons: tuple = HORIZONS) -> dict:
    entry = {"n": int(mask[: max(0, len(close) - max(horizons))].sum())
             if len(close) > max(horizons) else int(mask.sum())}
    # recount properly per horizon
    entry = {"n_signal_bars": int(mask.sum())}
    for h in horizons:
        scores = fade_scores(close, mask, h)
        entry[h] = {
            "n": int(len(scores)),
            "mean": float(scores.mean()) if len(scores) else None,
            "win_rate": float(np.mean(scores > 0)) if len(scores) else None,
        }
    return entry


def random_mask_like(base_mask: np.ndarray, close_len: int, horizon: int,
                     rng: np.random.Generator) -> np.ndarray:
    """Pick the same count of eligible bars (those with room for forward return)."""
    eligible = np.arange(0, close_len - horizon)
    n = int(base_mask[: close_len - horizon].sum())
    out = np.zeros(close_len, dtype=bool)
    if n <= 0 or len(eligible) == 0:
        return out
    pick = rng.choice(eligible, size=min(n, len(eligible)), replace=False)
    out[pick] = True
    return out


def cash_overlay(panel: Panel, signal: np.ndarray, hold: int = 12,
                 cost_per_side: float = 0.0015,
                 initial: float = 10_000.0) -> dict:
    """Secondary: long unless freshly signaled, then cash for `hold` bars."""
    close = panel.close
    n = len(close)
    equity = initial
    position = 1  # 1 long, 0 cash
    peak = equity
    max_dd = 0.0
    cash_until = -1
    trades = 0
    # enter long at first bar
    equity *= (1.0 - cost_per_side)
    trades += 1
    for i in range(1, n):
        # mark-to-market if long
        if position == 1:
            equity *= close[i] / close[i - 1]
        if signal[i] and position == 1:
            equity *= (1.0 - cost_per_side)
            position = 0
            cash_until = i + hold
            trades += 1
        elif position == 0 and i >= cash_until:
            equity *= (1.0 - cost_per_side)
            position = 1
            trades += 1
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)
    # close to cash at end for clean mark
    if position == 1:
        equity *= (1.0 - cost_per_side)
        trades += 1
    ret = equity / initial - 1.0
    return {
        "return": float(ret),
        "maxDD": float(max_dd),
        "robust": float(ret - 2.0 * max_dd),
        "final_equity": float(equity),
        "n_turnover_legs": int(trades),
    }


def buy_hold(panel: Panel, cost_per_side: float = 0.0015,
             initial: float = 10_000.0) -> dict:
    equity = initial * (1.0 - cost_per_side)
    equity *= panel.close[-1] / panel.close[0]
    equity *= (1.0 - cost_per_side)
    ret = equity / initial - 1.0
    # path DD
    path = panel.close / panel.close[0]
    peak = np.maximum.accumulate(path)
    dd = float(np.max((peak - path) / peak))
    return {
        "return": float(ret),
        "maxDD": dd,
        "robust": float(ret - 2.0 * dd),
        "final_equity": float(equity),
        "n_turnover_legs": 2,
    }
