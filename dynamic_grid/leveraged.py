"""Leveraged / multi-asset / long-short portfolio simulator for E31.

Pure backtest. No exchange call, no order transport, no network.

The three things this module exists to get right, because they are what make a
leveraged backtest lie (`docs/CRYPTO_E31_CRITERIA.md` §3):

1. **Liquidation is checked inside the bar**, against `low` for longs and
   `high` for shorts. Multiplying a daily close-to-close return by L silently
   assumes you survived the intrabar excursion — which is exactly the assumption
   that blows real accounts up.
2. **Funding is real, per symbol, per day**, taken from Binance's own
   `fundingRate` history. Longs pay it when positive; shorts receive it.
3. **Delisting is an exit, not a disappearance.** When a symbol's history ends
   the position is closed at its last close and the symbol leaves the universe.

The portfolio is expressed as a weight vector `w` (negative = short). Gross
leverage is `sum(|w|)`. Weights are set from data up to and including bar `i`
and take effect at `close[i]`.
"""

from dataclasses import dataclass, field

import numpy as np

SPOT_COST = 0.0015        # taker 0.10% + slippage 0.05%
PERP_COST = 0.0010        # taker 0.05% + slippage 0.05%
MAINTENANCE = 0.005       # 0.5% maintenance margin
RUIN_LEVEL = 0.10         # equity below 10% of window start counts as ruin


@dataclass
class PortfolioResult:
    name: str
    equity: np.ndarray
    initial_equity: float = 10_000.0
    liquidations: int = 0
    turnover: float = 0.0
    funding_paid: float = 0.0
    days: int = 0
    gross_leverage: list = field(default_factory=list)
    #: Executed weight per bar. Recording only — nothing reads it inside the
    #: simulation, so it cannot change a result. Needed by E36 to count trades
    #: from what the engine actually held, including bars where a liquidation
    #: flattened the book, rather than from the raw signal.
    weights_log: list = field(default_factory=list)

    @property
    def _curve(self):
        return np.concatenate(([self.initial_equity], self.equity))

    @property
    def total_return(self) -> float:
        return float(self.equity[-1] / self.initial_equity - 1.0)

    @property
    def annualised(self) -> float:
        """CAGR over the window. Reported in the unit the target is stated in."""
        yrs = self.days / 365.25
        if yrs <= 0:
            return 0.0
        ratio = max(self.equity[-1] / self.initial_equity, 1e-12)
        return float(ratio ** (1.0 / yrs) - 1.0)

    @property
    def max_drawdown(self) -> float:
        curve = self._curve
        peak = np.maximum.accumulate(curve)
        return float(((peak - curve) / peak).max())

    @property
    def robust(self) -> float:
        return self.total_return - 2.0 * self.max_drawdown

    @property
    def ruined(self) -> bool:
        return bool(self.equity.min() < self.initial_equity * RUIN_LEVEL)

    @property
    def final_equity(self) -> float:
        return float(self.equity[-1])

    @property
    def mean_gross_leverage(self) -> float:
        return float(np.mean(self.gross_leverage)) if self.gross_leverage else 0.0


def simulate(dates, closes, highs, lows, funding, strategy, start,
             initial_equity=10_000.0, cost=PERP_COST, use_funding=True,
             intrabar_liquidation=True):
    """Run `strategy` over the aligned panel.

    closes/highs/lows: (n_days, n_assets) with NaN where the asset is not trading.
    funding:           (n_days, n_assets) daily funding rate, longs pay when > 0.
    strategy.weights(i) -> np.ndarray of target weights, using bars <= i only.
    """
    n_days, n_assets = closes.shape
    w = np.zeros(n_assets)
    equity = np.empty(n_days - start)
    eq = initial_equity
    liq = 0
    turn = 0.0
    fund_total = 0.0
    gross = []
    executed = []

    for i in range(start, n_days):
        if i > start and eq > 0:
            prev, cur = closes[i - 1], closes[i]
            live = w != 0.0

            if live.any():
                # --- intrabar liquidation check
                # Adversarial by construction: every held name is assumed to
                # print its extreme at the same instant. That is exact for a
                # one-asset book and pessimistic for a basket, so a diagnostic
                # run with `intrabar_liquidation=False` brackets the effect.
                adverse = np.zeros(n_assets)
                for j in np.flatnonzero(live):
                    if np.isnan(prev[j]):
                        continue
                    if not intrabar_liquidation:
                        # diagnostic mode: only the close-to-close move can
                        # blow the account up — wicks are forgiven
                        px = cur[j]
                    elif w[j] > 0:
                        px = lows[i, j]
                    else:
                        px = highs[i, j]
                    adverse[j] = (px / prev[j] - 1.0) if not np.isnan(px) else 0.0
                worst = float(np.dot(w, adverse))
                if 1.0 + worst <= MAINTENANCE:
                    eq *= MAINTENANCE     # margin call: the account is wiped
                    w = np.zeros(n_assets)
                    liq += 1
                    equity[i - start] = eq
                    executed.append(w.copy())   # keep the log aligned to equity
                    continue

                # --- close-to-close move on the surviving book
                ret = 0.0
                for j in np.flatnonzero(live):
                    if np.isnan(prev[j]):
                        continue
                    if np.isnan(cur[j]):
                        # delisted: the position was closed at the last print
                        w[j] = 0.0
                        continue
                    ret += w[j] * (cur[j] / prev[j] - 1.0)
                eq *= (1.0 + ret)

                # --- funding on the notional actually carried
                if use_funding:
                    f = 0.0
                    for j in np.flatnonzero(w != 0.0):
                        rate = funding[i, j]
                        if not np.isnan(rate):
                            f += w[j] * rate
                    eq -= eq * f if eq > 0 else 0.0
                    fund_total += f

        if eq <= 0:
            eq = 0.0
            equity[i - start] = 0.0
            w = np.zeros(n_assets)
            executed.append(w.copy())
            continue

        target = strategy.weights(i)
        traded = float(np.abs(target - w).sum())
        eq -= eq * traded * cost
        turn += traded
        w = target
        gross.append(float(np.abs(w).sum()))
        executed.append(w.copy())
        equity[i - start] = eq

    return PortfolioResult(name=strategy.name, equity=equity,
                           initial_equity=initial_equity, liquidations=liq,
                           turnover=turn, funding_paid=fund_total,
                           days=n_days - start, gross_leverage=gross,
                           weights_log=executed)


# --------------------------------------------------------------------------
# strategies — every parameter is fixed by the criteria doc, none tuned here
# --------------------------------------------------------------------------

class _Panel:
    """Shared, pre-computed, causal views over the panel."""

    def __init__(self, closes, highs, lows, symbols):
        self.closes, self.highs, self.lows = closes, highs, lows
        self.symbols = symbols
        self.n = closes.shape[1]

    def tradable(self, i):
        return ~np.isnan(self.closes[i])

    def momentum(self, i, lookback):
        past = i - lookback
        if past < 0:
            return np.full(self.n, np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            return self.closes[i] / self.closes[past] - 1.0

    def donchian_break(self, i, channel, asset):
        if i < channel:
            return False
        window = self.highs[i - channel:i, asset]
        return bool(self.closes[i, asset] > np.nanmax(window))

    def donchian_break_down(self, i, channel, asset):
        if i < channel:
            return False
        window = self.lows[i - channel:i, asset]
        return bool(self.closes[i, asset] < np.nanmin(window))

    def realised_vol(self, i, asset, lookback=20):
        if i < lookback + 1:
            return np.nan
        seg = self.closes[i - lookback:i + 1, asset]
        if np.isnan(seg).any():
            return np.nan
        r = np.diff(seg) / seg[:-1]
        return float(r.std(ddof=1) * np.sqrt(365.25))


class BuyHold:
    name = "K0_btc_buy_hold"
    leverage = 1.0

    def __init__(self, panel, asset=0):
        self.p, self.a = panel, asset

    def weights(self, i):
        w = np.zeros(self.p.n)
        if self.p.tradable(i)[self.a]:
            w[self.a] = 1.0
        return w


class LeveredTrend:
    """K1 / K2 — Donchian-55 breakout, optionally two-sided, constant leverage."""

    def __init__(self, panel, asset=0, channel=55, leverage=3.0,
                 two_sided=False, name=None):
        self.p, self.a = panel, asset
        self.channel, self.lev, self.two_sided = channel, leverage, two_sided
        self.state = 0
        self.name = name or (
            f"K2_btc_trend_ls_{leverage:g}x" if two_sided
            else f"K1_btc_trend_long_{leverage:g}x")

    def weights(self, i):
        if self.p.donchian_break(i, self.channel, self.a):
            self.state = 1
        elif self.p.donchian_break_down(i, self.channel, self.a):
            self.state = -1 if self.two_sided else 0
        w = np.zeros(self.p.n)
        if self.p.tradable(i)[self.a]:
            w[self.a] = self.state * self.lev
        return w


class CrossSectionalMomentum:
    """K3 / K4 — hold the top `k` of the universe by `lookback` return."""

    def __init__(self, panel, k=5, lookback=90, leverage=1.0, rebalance=5,
                 name=None):
        self.p, self.k, self.lb = panel, k, lookback
        self.lev, self.rebalance = leverage, rebalance
        self._w = np.zeros(panel.n)
        self.name = name or f"K3_xsec_mom_top{k}_{leverage:g}x"

    def weights(self, i):
        if i % self.rebalance == 0:
            mom = self.momentum_scores(i)
            valid = np.flatnonzero(~np.isnan(mom))
            self._w = np.zeros(self.p.n)
            if len(valid):
                top = valid[np.argsort(mom[valid])[::-1][:self.k]]
                if len(top):
                    self._w[top] = self.lev / len(top)
        # a symbol that stopped printing is dropped, not carried
        self._w = np.where(self.p.tradable(i), self._w, 0.0)
        return self._w.copy()

    def momentum_scores(self, i):
        mom = self.p.momentum(i, self.lb)
        return np.where(self.p.tradable(i), mom, np.nan)


class LongShortMomentum(CrossSectionalMomentum):
    """K5 — long the top k, short the bottom k, gross leverage `leverage`."""

    def __init__(self, panel, k=5, lookback=90, leverage=2.0, rebalance=5):
        super().__init__(panel, k, lookback, leverage, rebalance,
                         name=f"K5_xsec_ls_top{k}_{leverage:g}x")

    def weights(self, i):
        if i % self.rebalance == 0:
            mom = self.momentum_scores(i)
            valid = np.flatnonzero(~np.isnan(mom))
            self._w = np.zeros(self.p.n)
            if len(valid) >= 2 * self.k:
                order = valid[np.argsort(mom[valid])]
                bottom, top = order[:self.k], order[::-1][:self.k]
                side = self.lev / 2.0
                self._w[top] = side / len(top)
                self._w[bottom] = -side / len(bottom)
        self._w = np.where(self.p.tradable(i), self._w, 0.0)
        return self._w.copy()


class VolTargetTrend:
    """K6 — same trend signal, leverage set so realised vol meets a target."""

    name = "K6_btc_trend_voltarget"

    def __init__(self, panel, asset=0, channel=55, target_vol=0.60, cap=5.0):
        self.p, self.a = panel, asset
        self.channel, self.target, self.cap = channel, target_vol, cap
        self.state = 0

    def weights(self, i):
        if self.p.donchian_break(i, self.channel, self.a):
            self.state = 1
        elif self.p.donchian_break_down(i, self.channel, self.a):
            self.state = 0
        w = np.zeros(self.p.n)
        vol = self.p.realised_vol(i, self.a)
        if self.state and self.p.tradable(i)[self.a] and vol and not np.isnan(vol) \
                and vol > 0:
            w[self.a] = min(self.target / vol, self.cap)
        return w


class LeveredBuyHold:
    """K7 — constant-leverage BTC, rebalanced daily. The 'leverage alone' bar."""

    def __init__(self, panel, asset=0, leverage=3.0):
        self.p, self.a, self.lev = panel, asset, leverage
        self.name = f"K7_btc_buy_hold_{leverage:g}x"

    def weights(self, i):
        w = np.zeros(self.p.n)
        if self.p.tradable(i)[self.a]:
            w[self.a] = self.lev
        return w
