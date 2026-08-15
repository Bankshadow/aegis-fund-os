"""E54 candidates — ten specialist proposals, re-implemented in one harness.

Each function returns a full desired-weight matrix. Row t may only use data
through row t; the simulator earns row t's weights over t -> t+1.

Where a spec could not be reproduced exactly from daily bars, the departure is
marked SIMPLIFIED in the docstring and reported with the results. None of the
specialists' own performance claims are used anywhere.
"""

from __future__ import annotations

import numpy as np

from .bakeoff import (GROSS, cross_z, normalise_rows, rolling_mean, rolling_std,
                      top_bottom)


# ------------------------------------------------------------------ 1 -------

def xsec_ltrev(data, p):
    """XSEC-LTREV: De Bondt-Thaler long-horizon reversal, skipping the last month."""
    C, live = data["C"], data["live"]
    L, skip, n = p["L"], 30, 8
    n_t, n_s = C.shape
    S = np.full((n_t, n_s), np.nan)
    lo = L + skip
    if n_t > lo:
        with np.errstate(invalid="ignore", divide="ignore"):
            S[lo:] = np.log(C[skip:n_t - L]) - np.log(C[:n_t - lo])
    ok = live & np.isfinite(S)
    # long the most beaten down, short the most extended
    W = -top_bottom(S, ok, n)
    return normalise_rows(W)


# ------------------------------------------------------------------ 2 -------

def ivol_xs(data, p):
    """IVOL-XS: residual vol against an equal-weight universe index, top vs bottom third."""
    R, live = data["R"], data["live"]
    L = p["L"]
    n_t, n_s = R.shape
    mkt = np.nanmean(np.where(live, R, np.nan), axis=1)
    S = np.full((n_t, n_s), np.nan)
    for t in range(L, n_t):
        y = R[t - L + 1:t + 1]
        x = mkt[t - L + 1:t + 1]
        okx = np.isfinite(x)
        if okx.sum() < L * 0.8:
            continue
        xv = x[okx] - x[okx].mean()
        den = float(xv @ xv)
        if den <= 0:
            continue
        Y = y[okx]
        good = np.isfinite(Y).all(axis=0)
        if not good.any():
            continue
        Yg = Y[:, good]
        beta = (xv @ (Yg - Yg.mean(axis=0))) / den
        resid = Yg - Yg.mean(axis=0) - np.outer(xv, beta)
        S[t, good] = resid.std(axis=0, ddof=1)
    ok = live & np.isfinite(S)
    third = max(1, int(round(n_s / 3)))
    W = top_bottom(S, ok, third)          # long HIGH ivol, short low (crypto sign)
    return normalise_rows(W)


# ------------------------------------------------------------------ 3 -------

def femd(data, p):
    """FEMD: fade funding crowding only where price momentum is decelerating."""
    C, F, live = data["C"], data["F"], data["live"]
    win = p["win"]
    n_t, n_s = C.shape
    mu = rolling_mean(F, win)
    sd = rolling_std(F, win)
    with np.errstate(invalid="ignore", divide="ignore"):
        fz = np.where(sd > 0, (F - mu) / sd, 0.0)
    mom = np.full((n_t, n_s), np.nan)
    prv = np.full((n_t, n_s), np.nan)
    mom[10:] = C[10:] / C[:-10] - 1.0
    prv[20:] = C[10:-10] / C[:-20] - 1.0
    decel = mom - prv
    # one full day of lag on every input
    fz = np.vstack([np.zeros((1, n_s)), fz[:-1]])
    decel = np.vstack([np.full((1, n_s), np.nan), decel[:-1]])
    gate = 0.5 * (1.0 - np.tanh(np.nan_to_num(decel * np.sign(fz), nan=0.0) / 0.05))
    W = np.where(live, -fz * gate, 0.0)
    return normalise_rows(W)


# ------------------------------------------------------------------ 4 -------

def liq_improve(data, p):
    """LIQ-IMPROVE-XS: Amihud improvement, restricted to the tradeable end.

    SIMPLIFIED: the spec's 20/25/15 hysteresis band is implemented as a plain
    top-20 dollar-volume gate on a 60-day median. Hysteresis would only reduce
    turnover; it cannot create an edge that is not there, and leaving it out
    keeps the eligibility rule auditable.
    """
    C, V, live = data["C"], data["V"], data["live"]
    W_ = p["W"]
    n_t, n_s = C.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        illiq = np.abs(data["R"]) / np.where(V > 0, V, np.nan)
    recent = rolling_mean(illiq, W_)
    prior = np.vstack([np.full((W_, n_s), np.nan), recent[:-W_]])
    with np.errstate(invalid="ignore", divide="ignore"):
        lir = np.log(prior / recent)
    dv60 = rolling_mean(V, 60)
    elig = np.zeros_like(live)
    for t in range(n_t):
        idx = np.flatnonzero(live[t] & np.isfinite(dv60[t]))
        if len(idx) == 0:
            continue
        keep = idx[np.argsort(-dv60[t, idx])][:20]
        elig[t, keep] = True
    ok = elig & np.isfinite(lir)
    z = np.clip(cross_z(lir, ok), -3, 3)
    z = np.where(np.abs(z) < 0.25, 0.0, z)
    Wm = normalise_rows(z)
    return normalise_rows(np.clip(Wm, -0.15, 0.15))


# ------------------------------------------------------------------ 5 -------

def xabs(data, p):
    """XABS: trend vs its own 200-day SMA, gated on cross-sectional breadth."""
    C, live = data["C"], data["live"]
    hi, lo = p["hi"], p["lo"]
    n_t, n_s = C.shape
    sma = rolling_mean(C, 200)
    up = live & np.isfinite(sma) & (C > sma)
    dn = live & np.isfinite(sma) & (C < sma)
    valid = live & np.isfinite(sma)
    cnt = valid.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        breadth = np.where(cnt > 0, up.sum(axis=1) / np.where(cnt > 0, cnt, 1), np.nan)
    vol = rolling_std(data["R"], 60)
    with np.errstate(invalid="ignore", divide="ignore"):
        iv = np.where(np.isfinite(vol) & (vol > 0), 1.0 / vol, 0.0)
    longs = up & (breadth >= hi)[:, None]
    shorts = dn & (breadth <= lo)[:, None]
    Wl = normalise_rows(np.where(longs, iv, 0.0), gross=0.5)
    Ws = normalise_rows(np.where(shorts, iv, 0.0), gross=0.5)
    return Wl - Ws


# ------------------------------------------------------------------ 6 -------

def wknd_funding(data, p):
    """WKND_FUNDING_MEANREV: fade the weekend funding dislocation on Monday only.

    SIMPLIFIED: the harness holds a weight until the next rebalance rather than
    flattening intraweek, so this runs at rebal=7 and the Monday-only holding
    period becomes a full week. Reported as a departure - it makes the strategy
    hold longer than specified, which the spec's own mechanism does not claim.
    """
    import datetime as dt
    C, F, live = data["C"], data["F"], data["live"]
    q = p["q"]
    n_t, n_s = C.shape
    dow = np.array([dt.date.fromisoformat(d).weekday() for d in data["dates"]])
    S = np.full((n_t, n_s), np.nan)
    for t in range(2, n_t):
        if dow[t] != 0:                      # decide on Monday, using Sat+Sun
            continue
        sat = t - 2 if dow[t - 2] == 5 else None
        if sat is None:
            continue
        S[t] = F[t - 2] + F[t - 1]
    ok = live & np.isfinite(S) & (S != 0)
    W = np.zeros((n_t, n_s))
    for t in range(n_t):
        idx = np.flatnonzero(ok[t])
        k = int(len(idx) * q)
        if k < 1 or len(idx) < 2 * k:
            continue
        order = idx[np.argsort(S[t, idx])]
        W[t, order[:k]] = +1.0               # most negative funding -> long
        W[t, order[-k:]] = -1.0
    # carry the Monday book forward to the harness's rebalance rows
    for t in range(1, n_t):
        if not np.abs(W[t]).any():
            W[t] = W[t - 1]
    return normalise_rows(W)


# ------------------------------------------------------------------ 7 -------

def bcr(data, p):
    """BCR: betting against beta within alts, gross scaled by average correlation."""
    R, live = data["R"], data["live"]
    win = p["win"]
    n_t, n_s = R.shape
    btc = data["syms"].index("BTC") if "BTC" in data["syms"] else -1
    alt = np.ones(n_s, bool)
    if btc >= 0:
        alt[btc] = False
    idxr = np.nanmean(np.where(live & alt, R, np.nan), axis=1)
    beta = np.full((n_t, n_s), np.nan)
    rho = np.full(n_t, np.nan)
    for t in range(win, n_t):
        x = idxr[t - win + 1:t + 1]
        Y = R[t - win + 1:t + 1]
        if not np.isfinite(x).all():
            continue
        xv = x - x.mean()
        den = float(xv @ xv)
        if den <= 0:
            continue
        good = np.isfinite(Y).all(axis=0) & alt
        if good.sum() < 5:
            continue
        Yg = Y[:, good]
        beta[t, good] = (xv @ (Yg - Yg.mean(axis=0))) / den
        Z = (Yg - Yg.mean(axis=0)) / np.where(Yg.std(axis=0) > 0, Yg.std(axis=0), np.inf)
        Cm = (Z.T @ Z) / len(Z)
        m = Cm.shape[0]
        rho[t] = (Cm.sum() - np.trace(Cm)) / max(m * (m - 1), 1)
    # lag one day: decide on yesterday's estimates
    beta = np.vstack([np.full((1, n_s), np.nan), beta[:-1]])
    rho = np.concatenate([[np.nan], rho[:-1]])
    ok = live & np.isfinite(beta)
    third = max(1, int(round(alt.sum() / 3)))
    W = -top_bottom(beta, ok, third)          # long low beta, short high beta
    # correlation gate, percentiles from a trailing 2y window only
    g = np.ones(n_t)
    for t in range(n_t):
        hist = rho[max(0, t - 730):t]
        hist = hist[np.isfinite(hist)]
        if len(hist) < 120 or not np.isfinite(rho[t]):
            continue
        lo_, hi_ = np.percentile(hist, 25), np.percentile(hist, 85)
        if hi_ > lo_:
            g[t] = float(np.clip(1.0 - (rho[t] - lo_) / (hi_ - lo_), 0.2, 1.0))
    return normalise_rows(W, scale=g)


# ------------------------------------------------------------------ 8 -------

SECTORS = (("ETH", "SOL", "AVAX", "NEAR", "APT", "SUI", "TIA"),
           ("ARB", "OP"),
           ("DOT", "ATOM", "NEAR"),
           ("SAND", "MANA", "GALA"),
           ("UNI", "SUSHI", "CRV", "AAVE", "INJ"),
           ("BTC", "LTC", "ETC"))


def _adf_t(e):
    """Dickey-Fuller t-stat on the residual series (no augmentation)."""
    de, lag = np.diff(e), e[:-1]
    x = lag - lag.mean()
    den = float(x @ x)
    if den <= 0 or len(de) < 20:
        return 0.0
    b = float(x @ (de - de.mean())) / den
    resid = (de - de.mean()) - b * x
    s2 = float(resid @ resid) / max(len(de) - 2, 1)
    se = np.sqrt(s2 / den) if den > 0 and s2 > 0 else np.inf
    return b / se if np.isfinite(se) and se > 0 else 0.0


def daily_coint(data, p):
    """DAILY-COINT-SECTOR: Engle-Granger pairs inside hand-fixed sector buckets."""
    C, live, syms = data["C"], data["live"], data["syms"]
    z_in, z_out, z_stop = p["z"], 0.5, 4.0
    n_t, n_s = C.shape
    pairs = sorted({(min(a, b), max(a, b)) for grp in SECTORS
                    for i, a in enumerate(grp) for b in grp[i + 1:]
                    if a in syms and b in syms})
    ji = {s: syms.index(s) for s in syms}
    W = np.zeros((n_t, n_s))
    state, sel = {}, []
    with np.errstate(invalid="ignore", divide="ignore"):
        LP = np.log(C)

    for t in range(1, n_t):
        if t % 30 == 0 and t > 150:
            sel, state = [], {}
            for a, b in pairs:
                ia, ib = ji[a], ji[b]
                ya, yb = LP[t - 90:t, ia], LP[t - 90:t, ib]
                if not (np.isfinite(ya).all() and np.isfinite(yb).all()):
                    continue
                xv = yb - yb.mean()
                den = float(xv @ xv)
                if den <= 0:
                    continue
                beta = float(xv @ (ya - ya.mean())) / den
                e = ya - beta * yb
                if _adf_t(e) < -2.9:                 # ~10% Engle-Granger critical
                    sel.append((ia, ib, beta))
            sel = sel[:6]
        if not sel:
            continue
        raw = np.zeros(n_s)
        for ia, ib, beta in sel:
            if t < 60 or not (np.isfinite(LP[t - 60:t + 1, ia]).all()
                              and np.isfinite(LP[t - 60:t + 1, ib]).all()):
                continue
            s = LP[t - 60:t + 1, ia] - beta * LP[t - 60:t + 1, ib]
            sd = s.std(ddof=1)
            if sd <= 0:
                continue
            z = (s[-1] - s.mean()) / sd
            key = (ia, ib)
            pos = state.get(key, 0)
            if pos == 0 and abs(z) > z_in:
                pos = -int(np.sign(z))
            elif pos != 0 and (abs(z) < z_out or abs(z) > z_stop):
                pos = 0
            state[key] = pos
            if pos:
                raw[ia] += pos * 0.5
                raw[ib] -= pos * 0.5
        W[t] = raw
    return normalise_rows(W)


# ------------------------------------------------------------------ 9 -------

def gk_vol_carry(data, p):
    """garman-klass-vol-carry: short-vs-long Garman-Klass range ratio, ranked."""
    O, H, L, C, live = data["O"], data["H"], data["L"], data["C"], data["live"]
    short = p["short"]
    with np.errstate(invalid="ignore", divide="ignore"):
        gk = 0.5 * np.log(H / L) ** 2 - (2 * np.log(2) - 1) * np.log(C / O) ** 2
    num = rolling_mean(gk, short)
    den = rolling_mean(gk, 30)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(den > 0, num / den, np.nan)
    S = -(ratio - 1.0)
    ok = live & np.isfinite(S)
    n_t, n_s = C.shape
    W = np.zeros((n_t, n_s))
    for t in range(n_t):
        idx = np.flatnonzero(ok[t])
        if len(idx) < 10:
            continue
        r = np.argsort(np.argsort(S[t, idx])).astype(float)
        W[t, idx] = r - r.mean()
    return normalise_rows(np.clip(normalise_rows(W), -0.15, 0.15))


# ----------------------------------------------------------------- 10 -------

def er_switch(data, p):
    """ER-Switch: Kaufman efficiency ratio picks trend or mean-reversion per coin.

    SIMPLIFIED: the spec's chop leg is a multi-level grid marked against the
    day's H/L. A grid has no representation in a daily weight vector, so the
    continuous limit of one is used - short when price sits above its 20-day
    mean, long when below, scaled by the distance. This keeps the SIGN of the
    grid leg, which is the property the mechanism rests on.
    """
    C, R, live = data["C"], data["R"], data["live"]
    theta, n = p["theta"], 20
    n_t, n_s = C.shape
    disp = np.full((n_t, n_s), np.nan)
    disp[n:] = np.abs(C[n:] - C[:-n])
    path = rolling_mean(np.abs(np.nan_to_num(np.diff(C, axis=0, prepend=np.nan))), n) * n
    with np.errstate(invalid="ignore", divide="ignore"):
        er = np.where(path > 0, disp / path, np.nan)
    sma = rolling_mean(C, n)
    vol = rolling_std(R, n)
    with np.errstate(invalid="ignore", divide="ignore"):
        iv = np.where(np.isfinite(vol) & (vol > 0), 1.0 / vol, 0.0)
        stretch = np.where(sma > 0, (C - sma) / sma, 0.0)
    trend_sign = np.sign(np.nan_to_num(disp * 0 + (C - np.vstack(
        [np.full((n, n_s), np.nan), C[:-n]])), nan=0.0))
    is_trend = np.isfinite(er) & (er >= theta)
    pos = np.where(is_trend, trend_sign, -np.sign(stretch) * np.minimum(
        np.abs(stretch) / 0.10, 1.0))
    # one-day lag on the classification
    pos = np.vstack([np.zeros((1, n_s)), pos[:-1]])
    ivl = np.vstack([np.zeros((1, n_s)), iv[:-1]])
    W = np.where(live, pos * ivl, 0.0)
    return normalise_rows(np.clip(normalise_rows(W), -0.15, 0.15))


# ---------------------------------------------------------------------------

CANDIDATES = {
    "XSEC-LTREV":  {"fn": xsec_ltrev, "rebal": 21, "key": "L",
                    "centre": 270, "neigh": (180, 360), "src": "long-term reversal"},
    "IVOL-XS":     {"fn": ivol_xs, "rebal": 7, "key": "L",
                    "centre": 30, "neigh": (15, 60), "src": "idiosyncratic vol"},
    "FEMD":        {"fn": femd, "rebal": 1, "key": "win",
                    "centre": 90, "neigh": (60, 120), "src": "funding exhaustion"},
    "LIQ-IMPROVE": {"fn": liq_improve, "rebal": 1, "key": "W",
                    "centre": 20, "neigh": (10, 40), "src": "liquidity trend"},
    "XABS":        {"fn": xabs, "rebal": 7, "key": "hi",
                    "centre": 0.55, "neigh": (0.53, 0.60), "src": "breadth trend",
                    "extra": lambda v: {"hi": v, "lo": 1.0 - v}},
    "WKND-FUND":   {"fn": wknd_funding, "rebal": 7, "key": "q",
                    "centre": 0.20, "neigh": (0.10, 0.33), "src": "weekend funding"},
    "BCR":         {"fn": bcr, "rebal": 1, "key": "win",
                    "centre": 60, "neigh": (40, 90), "src": "betting against beta"},
    "COINT":       {"fn": daily_coint, "rebal": 1, "key": "z",
                    "centre": 2.0, "neigh": (1.5, 2.5), "src": "sector pairs"},
    "GK-VOL":      {"fn": gk_vol_carry, "rebal": 1, "key": "short",
                    "centre": 5, "neigh": (3, 10), "src": "Garman-Klass ratio"},
    "ER-SWITCH":   {"fn": er_switch, "rebal": 1, "key": "theta",
                    "centre": 0.30, "neigh": (0.25, 0.35), "src": "efficiency regime"},
}


def params_for(name, value):
    spec = CANDIDATES[name]
    if "extra" in spec:
        return spec["extra"](value)
    return {spec["key"]: value}
