"""E32 — trend-filter overlays that carry the leverage, instead of buy-and-hold.

Pure backtest. No exchange call, no order transport, no network. Everything here
produces a weight vector for `dynamic_grid.leveraged.simulate`, which owns the
parts that make a leveraged backtest lie (intrabar liquidation, real funding,
delisting as an exit). That engine is not modified by this module.

Every parameter is fixed by `docs/E32_CRITERIA.md` §3 before the first run:
SMA 200, MA cross 50/200, momentum lookback 200, vol lookback 20, vol target
0.40. Nothing in this file is tuned.

Causality: a weight for bar `i` may only read bars `<= i`, and is executed at
`close[i]`. The rolling statistics below include bar `i`'s own close, which is
known at the moment of the decision, and never a later bar. `tests/
test_trend_overlay.py` pins this.
"""

from __future__ import annotations

import numpy as np

TRADING_DAYS = 365.25       # crypto trades every day


class Stats:
    """Causal rolling statistics over a (n_days, n_assets) close panel.

    Cached per window length so a candidate sweep does not recompute them.
    """

    def __init__(self, closes: np.ndarray):
        self.closes = closes
        self._sma: dict[int, np.ndarray] = {}
        self._vol: dict[int, np.ndarray] = {}

    def sma(self, window: int) -> np.ndarray:
        """Rolling mean of the close, NaN until `window` clean observations."""
        if window not in self._sma:
            c = self.closes
            valid = ~np.isnan(c)
            filled = np.where(valid, c, 0.0)
            csum = np.cumsum(filled, axis=0)
            ccnt = np.cumsum(valid.astype(np.int64), axis=0)
            out = np.full(c.shape, np.nan)
            total = csum[window - 1:] - np.vstack(
                [np.zeros((1, c.shape[1])), csum[:-window]])
            count = ccnt[window - 1:] - np.vstack(
                [np.zeros((1, c.shape[1]), dtype=np.int64), ccnt[:-window]])
            with np.errstate(invalid="ignore", divide="ignore"):
                mean = np.where(count == window, total / window, np.nan)
            out[window - 1:] = mean
            self._sma[window] = out
        return self._sma[window]

    def conditional_gap(self, window: int, sma_window: int = 200) -> np.ndarray:
        """Trailing edge of the state itself, per asset, using closed bars only.

        For each day `i`, the mean next-day return over the last `window` days
        while the close was above its SMA, minus the same while it was below.
        Positive means the state carried information on that asset recently.

        Only bars whose next-day return is already known at `i` are used, so the
        value at `i` is decidable at `i`. `tests/test_trend_overlay.py` pins it.
        """
        key = ("gap", window, sma_window)
        if key not in self._vol:            # cache shares the dict, keyed by tuple
            c = self.closes
            ma = self.sma(sma_window)
            fwd = np.full(c.shape, np.nan)
            fwd[:-1] = c[1:] / c[:-1] - 1.0
            usable = (~np.isnan(fwd)) & (~np.isnan(ma)) & (~np.isnan(c))
            above = usable & (c > ma)
            below = usable & ~(c > ma)
            out = np.full(c.shape, np.nan)

            def rolling(mask):
                vals = np.where(mask, np.nan_to_num(fwd), 0.0)
                cnt = np.cumsum(mask.astype(np.float64), axis=0)
                tot = np.cumsum(vals, axis=0)
                return tot, cnt

            tot_a, cnt_a = rolling(above)
            tot_b, cnt_b = rolling(below)
            for i in range(window, c.shape[0]):
                # the window ends at i-1: the return of day i is not known at i
                lo = i - window
                na = cnt_a[i - 1] - cnt_a[lo]
                nb = cnt_b[i - 1] - cnt_b[lo]
                ok = (na >= 20) & (nb >= 20)
                if not ok.any():
                    continue
                ma_ret = np.where(ok, (tot_a[i - 1] - tot_a[lo]) / np.where(na > 0, na, 1), np.nan)
                mb_ret = np.where(ok, (tot_b[i - 1] - tot_b[lo]) / np.where(nb > 0, nb, 1), np.nan)
                out[i] = ma_ret - mb_ret
            self._vol[key] = out
        return self._vol[key]

    def vol(self, window: int = 20) -> np.ndarray:
        """Annualised realised volatility of daily returns, NaN when incomplete."""
        if window not in self._vol:
            c = self.closes
            with np.errstate(invalid="ignore", divide="ignore"):
                r = np.full(c.shape, np.nan)
                r[1:] = c[1:] / c[:-1] - 1.0
            out = np.full(c.shape, np.nan)
            for i in range(window, c.shape[0]):
                seg = r[i - window + 1:i + 1]
                ok = ~np.isnan(seg)
                good = ok.all(axis=0)
                if good.any():
                    out[i, good] = seg[:, good].std(axis=0, ddof=1) * np.sqrt(TRADING_DAYS)
            self._vol[window] = out
        return self._vol[window]


# --------------------------------------------------------------------------
# single-asset overlays
# --------------------------------------------------------------------------

class SmaRegime:
    """T1-T3 — hold `leverage` while the close is above its own SMA, else flat.

    This is E30's M3 mechanism, which had the best up/down capture ratio of the
    directional set, with the leverage moved onto it.
    """

    def __init__(self, stats: Stats, asset=0, window=200, leverage=1.0, name=None):
        self.s, self.a = stats, asset
        self.window, self.lev = window, leverage
        self.name = name or f"T_sma{window}_{leverage:g}x"

    def weights(self, i):
        w = np.zeros(self.s.closes.shape[1])
        px = self.s.closes[i, self.a]
        ma = self.s.sma(self.window)[i, self.a]
        if not np.isnan(px) and not np.isnan(ma) and px > ma:
            w[self.a] = self.lev
        return w


class MaCross:
    """T — long `leverage` while fast SMA is above slow SMA (E30's M5, levered)."""

    def __init__(self, stats: Stats, asset=0, fast=50, slow=200, leverage=1.0,
                 name=None):
        self.s, self.a = stats, asset
        self.fast, self.slow, self.lev = fast, slow, leverage
        self.name = name or f"T_cross{fast}_{slow}_{leverage:g}x"

    def weights(self, i):
        w = np.zeros(self.s.closes.shape[1])
        f = self.s.sma(self.fast)[i, self.a]
        sl = self.s.sma(self.slow)[i, self.a]
        if not np.isnan(f) and not np.isnan(sl) and f > sl:
            w[self.a] = self.lev
        return w


class VolTargetSma:
    """T — same SMA regime, but sized so realised vol meets a target.

    Leverage is an output here, not an input: the position shrinks when the
    market is violent, which is where constant leverage gets liquidated.
    """

    def __init__(self, stats: Stats, asset=0, window=200, target=0.40, cap=3.0,
                 vol_lookback=20, name=None):
        self.s, self.a = stats, asset
        self.window, self.target, self.cap = window, target, cap
        self.vlb = vol_lookback
        self.name = name or f"T_sma{window}_voltgt{target:g}_cap{cap:g}"

    def weights(self, i):
        w = np.zeros(self.s.closes.shape[1])
        px = self.s.closes[i, self.a]
        ma = self.s.sma(self.window)[i, self.a]
        v = self.s.vol(self.vlb)[i, self.a]
        if (not np.isnan(px) and not np.isnan(ma) and px > ma
                and not np.isnan(v) and v > 0):
            w[self.a] = min(self.target / v, self.cap)
        return w


# --------------------------------------------------------------------------
# universe overlays — time-series (absolute) momentum, not cross-sectional
# --------------------------------------------------------------------------

class TimeSeriesMomentumBasket:
    """T — every symbol carries its OWN trend filter; hold all that qualify.

    This is a different mechanism from E31's `CrossSectionalMomentum`, which
    always held the top 5 names whether or not any of them was trending. Here
    the basket can be empty, which is the point: in a universe-wide bear market
    the book goes to cash by construction rather than by ranking.

    `weighting='equal'` splits the gross leverage evenly; `'invvol'` splits it
    inversely to each name's realised volatility (risk parity, no optimiser).
    """

    def __init__(self, stats: Stats, window=200, leverage=1.0, weighting="equal",
                 vol_lookback=20, rebalance=5, name=None):
        self.s = stats
        self.window, self.lev = window, leverage
        self.weighting, self.vlb, self.rebalance = weighting, vol_lookback, rebalance
        self._w = np.zeros(stats.closes.shape[1])
        self.name = name or f"T_tsmom{window}_{weighting}_{leverage:g}x"

    def _targets(self, i):
        c = self.s.closes[i]
        ma = self.s.sma(self.window)[i]
        live = (~np.isnan(c)) & (~np.isnan(ma)) & (c > ma)
        idx = np.flatnonzero(live)
        w = np.zeros(len(c))
        if len(idx) == 0:
            return w
        if self.weighting == "invvol":
            v = self.s.vol(self.vlb)[i]
            inv = np.array([1.0 / v[j] if (not np.isnan(v[j]) and v[j] > 0) else np.nan
                            for j in idx])
            ok = ~np.isnan(inv)
            if not ok.any():
                return w
            idx, inv = idx[ok], inv[ok]
            w[idx] = self.lev * inv / inv.sum()
        else:
            w[idx] = self.lev / len(idx)
        return w

    def weights(self, i):
        if i % self.rebalance == 0:
            self._w = self._targets(i)
        # a symbol that stopped printing is dropped, never carried
        self._w = np.where(~np.isnan(self.s.closes[i]), self._w, 0.0)
        return self._w.copy()


class ScreenedTrendVoteBasket:
    """E33 — the setup `docs/E33_CRITERIA.md` §2 specifies, and nothing else.

    Per asset: how many of three slow filters say long (0..3), divided by 3.
    An asset only counts if its own trailing conditional gap is positive, which
    is the mechanism E32-depth §1 measured rather than a preference. Weights are
    inverse-volatility, the book is scaled to a volatility target, and gross
    exposure is capped at 1.0 because every leverage test in E31/E32 said so.

    Empty basket = 100% cash. That is a state, not a failure.
    """

    def __init__(self, stats: Stats, sma_window=200, channel=55, fast=50,
                 vol_target=0.40, gross_cap=1.0, vol_lookback=20,
                 screen_window=730, rebalance=5, use_screen=True,
                 assets=None, name="E33_STVB"):
        self.s = stats
        self.sma_w, self.ch, self.fast = sma_window, channel, fast
        self.target, self.cap, self.vlb = vol_target, gross_cap, vol_lookback
        self.screen_w, self.rebalance, self.use_screen = screen_window, rebalance, use_screen
        self.assets = assets
        self.name = name
        self._w = np.zeros(stats.closes.shape[1])
        self._state = np.zeros(stats.closes.shape[1])     # Donchian latch

    def _votes(self, i):
        c = self.s.closes
        px = c[i]
        slow = self.s.sma(self.sma_w)[i]
        fast = self.s.sma(self.fast)[i]
        live = ~np.isnan(px)

        # filter 2 keeps a latched state, exactly like E31's LeveredTrend
        if i >= self.ch:
            window_hi = np.nanmax(c[i - self.ch:i], axis=0)
            window_lo = np.nanmin(c[i - self.ch:i], axis=0)
            with np.errstate(invalid="ignore"):
                self._state = np.where(live & (px > window_hi), 1.0,
                                       np.where(live & (px < window_lo), 0.0,
                                                self._state))

        with np.errstate(invalid="ignore"):
            v1 = live & (~np.isnan(slow)) & (px > slow)
            v2 = live & (self._state > 0)
            v3 = live & (~np.isnan(fast)) & (~np.isnan(slow)) & (fast > slow)
        return (v1.astype(float) + v2.astype(float) + v3.astype(float)) / 3.0

    def _targets(self, i):
        n = self.s.closes.shape[1]
        conv = self._votes(i)
        if self.assets is not None:
            keep = np.zeros(n, dtype=bool)
            keep[list(self.assets)] = True
            conv = np.where(keep, conv, 0.0)
        if self.use_screen:
            gap = self.s.conditional_gap(self.screen_w, self.sma_w)[i]
            conv = np.where((~np.isnan(gap)) & (gap > 0), conv, 0.0)
        v = self.s.vol(self.vlb)[i]
        ok = (conv > 0) & (~np.isnan(v)) & (v > 0)
        w = np.zeros(n)
        if not ok.any():
            return w
        raw = np.zeros(n)
        raw[ok] = conv[ok] / v[ok]
        # scale so the correlation-1 volatility estimate meets the target,
        # which is deliberately the pessimistic estimate for a crypto basket
        est = float(np.dot(raw, np.where(ok, v, 0.0)))
        if est <= 0:
            return w
        w = raw * (self.target / est)
        gross = float(np.abs(w).sum())
        if gross > self.cap:
            w *= self.cap / gross
        return w

    def weights(self, i):
        if i % self.rebalance == 0:
            self._w = self._targets(i)
        self._w = np.where(~np.isnan(self.s.closes[i]), self._w, 0.0)
        return self._w.copy()


class Blend:
    """T — a static split across sub-strategies. Weights sum to `1.0` of capital."""

    def __init__(self, parts, name):
        self.parts = parts          # [(strategy, share), ...]
        self.name = name

    def weights(self, i):
        out = None
        for strat, share in self.parts:
            w = strat.weights(i) * share
            out = w if out is None else out + w
        return out


class CashSleeve:
    """T — hold `fraction` of capital in `inner`, the rest in cash."""

    def __init__(self, inner, fraction, name=None):
        self.inner, self.f = inner, fraction
        self.name = name or f"{inner.name}@{fraction:g}"

    def weights(self, i):
        return self.inner.weights(i) * self.f


# --------------------------------------------------------------------------
# risk metrics that window-level summaries cannot express
# --------------------------------------------------------------------------

def risk_metrics(equity: np.ndarray, initial: float) -> dict:
    """Daily-resolution risk statistics from an equity curve."""
    curve = np.concatenate(([initial], equity))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = curve[1:] / curve[:-1] - 1.0
    r = np.where(np.isfinite(r), r, 0.0)
    peak = np.maximum.accumulate(curve)
    dd = (peak - curve) / peak
    n = len(r)
    yrs = n / TRADING_DAYS
    ratio = max(curve[-1] / initial, 1e-12)
    cagr = ratio ** (1.0 / yrs) - 1.0 if yrs > 0 else 0.0
    sd = r.std(ddof=1) if n > 1 else 0.0
    downside = r[r < 0]
    dsd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    ann = np.sqrt(TRADING_DAYS)
    worst_dd = float(dd.max())
    # longest stretch below the previous equity peak, in days
    tuw, best_tuw = 0, 0
    for x in dd:
        tuw = tuw + 1 if x > 1e-12 else 0
        best_tuw = max(best_tuw, tuw)
    return {
        "cagr": float(cagr),
        "total_return": float(curve[-1] / initial - 1.0),
        "worst_dd": worst_dd,
        "mar": float(cagr / worst_dd) if worst_dd > 0 else float("nan"),
        "vol": float(sd * ann),
        "sharpe": float(r.mean() / sd * ann) if sd > 0 else float("nan"),
        "sortino": float(r.mean() / dsd * ann) if dsd > 0 else float("nan"),
        "ulcer": float(np.sqrt(np.mean(dd ** 2))),
        "worst_day": float(r.min()),
        "best_day": float(r.max()),
        "days": int(n),
        "max_time_under_water": int(best_tuw),
        "final_equity": float(curve[-1]),
    }


def exposure_days(gross_leverage) -> float:
    """Share of decision days with any position on."""
    if not len(gross_leverage):
        return 0.0
    g = np.asarray(gross_leverage)
    return float((g > 1e-9).mean())
