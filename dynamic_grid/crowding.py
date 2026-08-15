"""E39 — crowded-long liquidation-fade panel and signals.

Definitions are fixed by `docs/E39_CRITERIA.md` §3 and are NOT tunable here:

* **Crowded**  L/S >= 1.50  AND  funding(ffill) >= 0.0001  AND  OI[i] > OI[i-24]
* **Impulse_up**  close[i] > close[i-1]  AND  (close[i]-close[i-1]) >= 0.5 * ATR14[i]
* **ATR14[i]** = mean true range over the **14 bars before i**, i not included
* **fade_h**  = -(close[i+h]/close[i] - 1)   (positive = fading paid)

Classification at bar `i` reads only bars <= i; the forward window starts at
`close[i]`. Nothing here places an order or computes leverage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LS_THRESHOLD = 1.50
FUNDING_THRESHOLD = 0.0001      # 0.01% per settlement
OI_LOOKBACK = 24                # bars
IMPULSE_ATR_MULT = 0.5
ATR_PERIOD = 14


@dataclass
class Panel:
    """Aligned 1h panel. Every array is the same length and shares an index."""

    times: np.ndarray
    close: np.ndarray
    high: np.ndarray
    low: np.ndarray
    long_short: np.ndarray
    oi_value: np.ndarray
    funding: np.ndarray

    def __len__(self):
        return len(self.times)


def forward_fill(times: np.ndarray, stamps: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Carry each settlement forward onto later bars. NaN before the first one.

    Causal by construction: a bar only ever sees a settlement at or before its
    own timestamp, so an 8h funding print never leaks backwards into the bars
    that preceded it.
    """
    out = np.full(len(times), np.nan)
    if len(stamps) == 0:
        return out
    order = np.argsort(stamps)
    stamps, values = stamps[order], values[order]
    idx = np.searchsorted(stamps, times, side="right") - 1
    known = idx >= 0
    out[known] = values[idx[known]]
    return out


def atr_prior(high, low, close, period: int = ATR_PERIOD) -> np.ndarray:
    """Mean true range over the `period` bars BEFORE i. NaN until available.

    The criteria say "14 bars before i, i not included" — using the current bar
    would let the impulse test measure itself, so a big bar would raise its own
    threshold and the signal would be self-referential.
    """
    n = len(close)
    tr = np.full(n, np.nan)
    tr[1:] = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ])
    out = np.full(n, np.nan)
    for i in range(period + 1, n):
        window = tr[i - period:i]          # excludes i
        if not np.isnan(window).any():
            out[i] = float(window.mean())
    return out


def impulse_up(panel: Panel) -> np.ndarray:
    band = atr_prior(panel.high, panel.low, panel.close)
    move = np.full(len(panel), np.nan)
    move[1:] = panel.close[1:] - panel.close[:-1]
    with np.errstate(invalid="ignore"):
        return (move > 0) & (move >= IMPULSE_ATR_MULT * band) & ~np.isnan(band)


def oi_expanding(panel: Panel) -> np.ndarray:
    out = np.zeros(len(panel), dtype=bool)
    oi = panel.oi_value
    for i in range(OI_LOOKBACK, len(panel)):
        if not (np.isnan(oi[i]) or np.isnan(oi[i - OI_LOOKBACK])):
            out[i] = oi[i] > oi[i - OI_LOOKBACK]
    return out


def signals(panel: Panel) -> dict:
    """The six declared signal sets (§3). Booleans over the panel index."""
    imp = impulse_up(panel)
    with np.errstate(invalid="ignore"):
        ls_hot = panel.long_short >= LS_THRESHOLD
        fund_hot = panel.funding >= FUNDING_THRESHOLD
    ls_hot = np.where(np.isnan(panel.long_short), False, ls_hot)
    fund_hot = np.where(np.isnan(panel.funding), False, fund_hot)
    oi_hot = oi_expanding(panel)

    crowded = ls_hot & fund_hot & oi_hot
    return {
        "S_full": crowded & imp,
        "S_fund": fund_hot & imp,
        "S_ls": ls_hot & imp,
        "S_oi": oi_hot & imp,
        "S_imp": imp,
        "_crowded": crowded,
    }


def fade(close: np.ndarray, horizon: int) -> np.ndarray:
    """`-(close[i+h]/close[i] - 1)`. NaN where the window runs off the end."""
    out = np.full(len(close), np.nan)
    if horizon < len(close):
        out[:-horizon] = -(close[horizon:] / close[:-horizon] - 1.0)
    return out


def random_like(mask: np.ndarray, eligible: np.ndarray, seed: int = 0) -> np.ndarray:
    """A same-size random draw from the eligible bars. Seed fixed by §3."""
    rng = np.random.default_rng(seed)
    pool = np.flatnonzero(eligible)
    k = int(mask.sum())
    out = np.zeros(len(mask), dtype=bool)
    if k and len(pool) >= k:
        out[rng.choice(pool, size=k, replace=False)] = True
    return out


def label_permutation_percentile(a: np.ndarray, b: np.ndarray, draws: int = 10_000,
                                 seed: int = 0) -> float:
    """Share of label-shuffles where the A-minus-B gap is below the observed one.

    Shuffling labels over the pooled sample is the test the criteria name: it
    asks whether splitting these same observations this particular way is
    special, rather than whether either group differs from the whole market.
    """
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    observed = float(a.mean() - b.mean())
    pool = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    n_a = len(a)
    gaps = np.empty(draws)
    for d in range(draws):
        shuffled = rng.permutation(pool)
        gaps[d] = shuffled[:n_a].mean() - shuffled[n_a:].mean()
    return float(np.mean(gaps < observed))
