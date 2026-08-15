"""E54 — one harness every candidate is measured in.

Criteria: `docs/E54_CRITERIA.md`, declared before any candidate existed.

Ten specialists proposed strategies. None of their numbers are used: a candidate
is a *weight function* here, and every one of them goes through the same gates
with the same costs on the same data. A bake-off whose candidates each brought
their own backtest would be comparing harnesses, not strategies.

The gate that matters most is G6. With N candidates the best of N looks good even
when none has an edge, so the placebo ceiling is the maximum over *every*
candidate's placebos, not each candidate's own. Adding candidates raises the bar
on all of them.

A candidate returns a full desired-weight matrix in one vectorised pass; the
simulator applies it only on that candidate's rebalance days. That shape exists
because G2 re-runs every candidate twenty times on perturbed prices.
"""

from __future__ import annotations

import datetime as dt
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSE = os.path.join(ROOT, "data", "universe", "spot_1d.json")
FUNDING = os.path.join(ROOT, "data", "universe", "funding_daily.json")

FEE_SIDE = 0.0015
GROSS = 1.0
NOISE_SEEDS = 20
PLACEBO_SEEDS = 20
TRAIN, TEST = 730, 182
NEIGHBOUR_FLOOR = 0.60
NOISE_SIGN_MIN = 18
NOISE_RATIO_MIN = 0.70


# ---------------------------------------------------------------- data ------

def _day(ms):
    return dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def load_panel():
    with open(UNIVERSE, encoding="utf-8") as fh:
        raw = json.load(fh)
    syms = sorted(raw)
    dates = sorted({_day(r[0]) for s in syms for r in raw[s]})
    idx = {d: i for i, d in enumerate(dates)}
    shape = (len(dates), len(syms))
    O, H, L, C, V = (np.full(shape, np.nan) for _ in range(5))
    for j, s in enumerate(syms):
        for r in raw[s]:
            i = idx[_day(r[0])]
            O[i, j], H[i, j], L[i, j], C[i, j] = (float(r[1]), float(r[2]),
                                                  float(r[3]), float(r[4]))
            V[i, j] = float(r[7])            # quote volume = USDT traded
    return dates, syms, O, H, L, C, V


def load_funding(dates, syms):
    with open(FUNDING, encoding="utf-8") as fh:
        fd = json.load(fh)
    F = np.zeros((len(dates), len(syms)))
    for j, s in enumerate(syms):
        tab = fd.get(s, {})
        for i, d in enumerate(dates):
            F[i, j] = tab.get(d, 0.0)
    return F


def log_returns(C):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.vstack([np.full((1, C.shape[1]), np.nan),
                          np.diff(np.log(C), axis=0)])


def build_data(O, H, L, C, V, F, dates, syms):
    return {"O": O, "H": H, "L": L, "C": C, "V": V, "F": F,
            "R": log_returns(C), "dates": dates, "syms": syms,
            "live": np.isfinite(C)}


def vendor_noise_pool():
    """Measured Yahoo-vs-Binance log close differences (E51). The real thing."""
    from e45_s003_full import load as load_yahoo
    with open(UNIVERSE, encoding="utf-8") as fh:
        raw = json.load(fh)
    pool = []
    for ysym, bsym in (("LINK-USD", "LINK"), ("SOL-USD", "SOL")):
        yd, _, _, _, yc, _ = load_yahoo(ysym)
        ym = dict(zip(yd, yc))
        for r in raw[bsym]:
            d, p = _day(r[0]), float(r[4])
            if d in ym and p > 0 and ym[d] > 0:
                pool.append(np.log(ym[d] / p))
    return np.array(pool)


def perturb(data, rng, pool):
    """Apply vendor-scale noise to O/H/L/C and rebuild the derived fields."""
    eps = np.exp(rng.choice(pool, size=data["C"].shape))
    out = dict(data)
    for k in ("O", "H", "L", "C"):
        out[k] = data[k] * eps
    out["R"] = log_returns(out["C"])
    out["live"] = np.isfinite(out["C"])
    return out


# --------------------------------------------------------- weight helpers ---

def normalise_rows(W, gross=GROSS, scale=None):
    W = np.nan_to_num(W, nan=0.0, posinf=0.0, neginf=0.0)
    g = np.abs(W).sum(axis=1, keepdims=True)
    out = np.divide(W, np.where(g > 0, g, 1.0)) * gross
    out[np.repeat(g <= 0, W.shape[1], axis=1)] = 0.0
    if scale is not None:
        out *= scale[:, None]
    return out


def rolling_mean(X, win):
    """NaN-aware trailing mean of length `win`, aligned so row t uses t-win+1..t."""
    Z = np.nan_to_num(X, nan=0.0)
    M = np.isfinite(X).astype(float)
    cz = np.cumsum(np.vstack([np.zeros((1, X.shape[1])), Z]), axis=0)
    cm = np.cumsum(np.vstack([np.zeros((1, X.shape[1])), M]), axis=0)
    s = cz[win:] - cz[:-win]
    n = cm[win:] - cm[:-win]
    out = np.full_like(X, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[win - 1:] = np.where(n > 0, s / np.where(n > 0, n, 1.0), np.nan)
    return out


def rolling_std(X, win):
    m = rolling_mean(X, win)
    m2 = rolling_mean(X ** 2, win)
    with np.errstate(invalid="ignore"):
        return np.sqrt(np.maximum(m2 - m ** 2, 0.0))


def cross_z(X, mask):
    """Cross-sectional z-score within `mask` on each row."""
    A = np.where(mask, X, np.nan)
    mu = np.nanmean(A, axis=1, keepdims=True)
    sd = np.nanstd(A, axis=1, keepdims=True)
    with np.errstate(invalid="ignore"):
        return np.where(mask & np.isfinite(A) & (sd > 0), (A - mu) / sd, 0.0)


def top_bottom(X, mask, n):
    """+1 on the n highest, -1 on the n lowest of each row, within `mask`."""
    W = np.zeros_like(X)
    for t in range(X.shape[0]):
        idx = np.flatnonzero(mask[t] & np.isfinite(X[t]))
        if len(idx) < 2 * n:
            continue
        order = idx[np.argsort(X[t, idx])]
        W[t, order[:n]] = -1.0
        W[t, order[-n:]] = +1.0
    return W


# ------------------------------------------------------------ simulation ----

def simulate(W, data, rebal, *, fee=FEE_SIDE, funding=True):
    """Daily net returns. Row t of W is the weight held from t to t+1."""
    C, F, R = data["C"], data["F"], data["R"]
    n_t, n_s = C.shape
    w = np.zeros(n_s)
    out = np.zeros(n_t)
    for t in range(1, n_t):
        r = float(w @ np.nan_to_num(np.exp(R[t]) - 1.0, nan=0.0))
        if funding:
            r -= float(w @ F[t])
        cost = 0.0
        if t % rebal == 0:
            cost = float(np.abs(W[t] - w).sum()) * fee
            w = W[t]
        out[t] = (1.0 + r) * (1.0 - cost) - 1.0
    return out


def mean_turnover(W, rebal):
    rows = np.arange(rebal, W.shape[0], rebal)
    if len(rows) < 2:
        return 0.0
    return float(np.abs(np.diff(W[rows], axis=0)).sum(axis=1).mean())


def placebo_weights(data, rebal, target_turnover, rng):
    """Random signs on live names, churned to match a candidate's turnover."""
    live = data["live"]
    n_t, n_s = live.shape
    W = np.zeros((n_t, n_s))
    prev = np.zeros(n_s)
    # each rebalance replaces a fraction of names; solve the fraction so the
    # resulting turnover lands on the candidate's, rather than assuming it
    frac = float(np.clip(target_turnover / 2.0, 0.0, 1.0))
    for t in range(rebal, n_t, rebal):
        ok = live[t]
        if ok.sum() < 5:
            W[t] = prev
            continue
        fresh = np.where(rng.random(n_s) < 0.5, 1.0, -1.0) * ok
        keep = rng.random(n_s) >= frac
        raw = np.where(keep, prev, fresh)
        raw = np.where(ok, raw, 0.0)
        if np.abs(raw).sum() == 0:
            raw = fresh
        prev = raw / max(np.abs(raw).sum(), 1e-12) * GROSS
        W[t] = prev
    for t in range(1, n_t):
        if W[t].sum() == 0 and np.abs(W[t]).sum() == 0:
            W[t] = W[t - 1]
    return W


# --------------------------------------------------------------- metrics ----

def curve_stats(daily, days=None):
    curve = np.cumprod(1.0 + daily)
    final = float(curve[-1])
    peak = np.maximum.accumulate(curve)
    dd = float(((peak - curve) / peak).max()) if len(curve) else 0.0
    days = days if days is not None else len(daily)
    years = days / 365.25
    return {"final": final, "total": final - 1.0, "maxDD": dd,
            "cagr": final ** (1 / years) - 1 if final > 0 and years > 0 else -1.0,
            "ret_dd": (final - 1.0) / dd if dd > 1e-9 else 0.0}
