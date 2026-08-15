"""Directional (non-grid) long-only spot backtester for E30.

Pure functions only: no exchange call, no order transport, no network.
Everything here is a backtest over an (n, 4) [open, high, low, close] array.

Design rules fixed by `docs/BTC_E30_CRITERIA.md` §2 and NOT tunable here:

* long-only spot, one position at a time, all-in compounding from `initial_equity`
* cost `COST_PER_SIDE` charged on entry *and* exit
* a signal computed from bars up to and including bar `i` executes at `close[i]`
* stop/target are checked on *later* bars against that bar's high/low; a gap
  through the level fills at the open, never at the (better) level price
* when a bar touches stop and target together the **stop** wins — the engine
  never credits itself the favourable ordering
"""

from dataclasses import dataclass, field

import numpy as np

COST_PER_SIDE = 0.0015  # 0.10% taker + 0.05% slippage


# --------------------------------------------------------------------------
# indicators (all causal: index i uses bars 0..i only)
# --------------------------------------------------------------------------

def sma(values: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return out
    csum = np.cumsum(np.insert(values, 0, 0.0))
    out[period - 1:] = (csum[period:] - csum[:-period]) / period
    return out


def atr_series(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               period: int = 14) -> np.ndarray:
    """Wilder's ATR. Same recurrence as `indicators.ATR`, vectorised."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev_close = close[:-1]
    tr[1:] = np.maximum.reduce([high[1:] - low[1:],
                                np.abs(high[1:] - prev_close),
                                np.abs(low[1:] - prev_close)])
    out = np.full(n, np.nan)
    if n < period:
        return out
    out[period - 1] = tr[:period].mean()
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def rsi_series(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI."""
    n = len(close)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_g = gain[:period].mean()
    avg_l = loss[:period].mean()
    for i in range(period, n):
        if i > period:
            avg_g = (avg_g * (period - 1) + gain[i - 1]) / period
            avg_l = (avg_l * (period - 1) + loss[i - 1]) / period
        out[i] = 100.0 if avg_l <= 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out


def rolling_max_prev(values: np.ndarray, period: int) -> np.ndarray:
    """max over the `period` bars BEFORE i (bar i excluded) — no lookahead."""
    n = len(values)
    out = np.full(n, np.nan)
    for i in range(period, n):
        out[i] = values[i - period:i].max()
    return out


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------

@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    entry_price: float
    exit_price: float
    reason: str

    @property
    def gross_return(self) -> float:
        return self.exit_price / self.entry_price - 1.0

    @property
    def net_return(self) -> float:
        """Return after both legs' costs, as a fraction of committed equity."""
        return (self.exit_price * (1 - COST_PER_SIDE)) / (
            self.entry_price * (1 + COST_PER_SIDE)) - 1.0


@dataclass
class StrategyResult:
    name: str
    equity: np.ndarray
    initial_equity: float = 10_000.0
    trades: list = field(default_factory=list)

    # ---- portfolio level ----
    @property
    def _curve(self) -> np.ndarray:
        """Equity including the pre-trade starting point.

        `equity[0]` is already marked *after* the first entry, so measuring
        against it would silently forgive the entry cost and hide a day-one
        drawdown. Every portfolio number is taken from this curve instead.
        """
        return np.concatenate(([self.initial_equity], self.equity))

    @property
    def total_return(self) -> float:
        return float(self.equity[-1] / self.initial_equity - 1.0)

    @property
    def max_drawdown(self) -> float:
        curve = self._curve
        peak = np.maximum.accumulate(curve)
        return float(((peak - curve) / peak).max())

    @property
    def robust(self) -> float:
        """Project-wide score. Never redefine — `return - 2*maxDD`."""
        return self.total_return - 2.0 * self.max_drawdown

    @property
    def final_equity(self) -> float:
        return float(self.equity[-1])

    # ---- trade level ----
    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> list:
        return [t.net_return for t in self.trades if t.net_return > 0]

    @property
    def losses(self) -> list:
        return [-t.net_return for t in self.trades if t.net_return <= 0]

    @property
    def win_rate(self):
        return len(self.wins) / len(self.trades) if self.trades else None

    @property
    def avg_win(self):
        return float(np.mean(self.wins)) if self.wins else None

    @property
    def avg_loss(self):
        return float(np.mean(self.losses)) if self.losses else None

    @property
    def rr(self):
        """Realised reward:risk = average win / average loss."""
        if not self.wins or not self.losses or self.avg_loss <= 0:
            return None
        return self.avg_win / self.avg_loss

    @property
    def expectancy(self):
        """Net expected return per trade, in fraction of committed equity."""
        if not self.trades:
            return None
        return float(np.mean([t.net_return for t in self.trades]))

    @property
    def profit_factor(self):
        gp, gl = sum(self.wins), sum(self.losses)
        if gl <= 0:
            return float("inf") if gp > 0 else 0.0
        return gp / gl


# --------------------------------------------------------------------------
# execution core
# --------------------------------------------------------------------------

def _simulate(bars: np.ndarray, start: int, signals, initial_equity: float,
              name: str) -> StrategyResult:
    """Walk bars[start:] driving a signal object.

    The signal object must expose:
        entry(i)                 -> bool, may I open at close[i]?
        on_entry(i, price)       -> set self.stop / self.target (None = off)
        exit_signal(i)           -> bool, close at close[i]?
        update(i)                -> called after exits, may move self.stop
    """
    n = len(bars)
    o, h, l, c = bars[:, 0], bars[:, 1], bars[:, 2], bars[:, 3]
    equity = np.empty(n - start)
    cash = initial_equity
    units = 0.0
    entry_idx = -1
    entry_price = 0.0
    trades = []

    for i in range(start, n):
        if units > 0.0:
            exited, price, reason = False, 0.0, ""
            stop, target = signals.stop, signals.target
            # stop first: a bar that touches both is booked as a stop
            if stop is not None and l[i] <= stop:
                price, reason, exited = min(o[i], stop), "stop", True
            elif target is not None and h[i] >= target:
                price, reason, exited = max(o[i], target), "target", True
            elif signals.exit_signal(i):
                price, reason, exited = c[i], "signal", True

            if exited:
                cash = units * price * (1 - COST_PER_SIDE)
                trades.append(Trade(entry_idx, i, entry_price, price, reason))
                units, entry_idx, entry_price = 0.0, -1, 0.0
                signals.stop = signals.target = None

        if units == 0.0 and i < n - 1 and signals.entry(i):
            entry_price = c[i]
            units = cash / (entry_price * (1 + COST_PER_SIDE))
            cash, entry_idx = 0.0, i
            signals.on_entry(i, entry_price)

        if units > 0.0:
            signals.update(i)

        equity[i - start] = cash + units * c[i]

    # liquidate whatever is open at the window's last close
    if units > 0.0:
        price = c[n - 1]
        cash = units * price * (1 - COST_PER_SIDE)
        trades.append(Trade(entry_idx, n - 1, entry_price, price, "eow"))
        equity[-1] = cash

    return StrategyResult(name=name, equity=equity,
                          initial_equity=initial_equity, trades=trades)


# --------------------------------------------------------------------------
# candidates — parameters fixed a priori by the criteria doc, never tuned here
# --------------------------------------------------------------------------

class _Base:
    stop = None
    target = None

    def on_entry(self, i, price):
        pass

    def exit_signal(self, i):
        return False

    def update(self, i):
        pass


class BuyHold(_Base):
    def __init__(self, bars):
        self._done = False

    def entry(self, i):
        if self._done:
            return False
        self._done = True
        return True


class DonchianTrail(_Base):
    """M1 — Donchian-55 breakout, ATR(14) x 3 trailing stop."""

    def __init__(self, bars, channel=55, atr_mult=3.0):
        h, l, c = bars[:, 1], bars[:, 2], bars[:, 3]
        self.c = c
        self.hi = rolling_max_prev(h, channel)
        self.atr = atr_series(h, l, c)
        self.atr_mult = atr_mult

    def entry(self, i):
        return (not np.isnan(self.hi[i]) and not np.isnan(self.atr[i])
                and self.c[i] > self.hi[i])

    def on_entry(self, i, price):
        self.stop = price - self.atr_mult * self.atr[i]

    def update(self, i):
        if not np.isnan(self.atr[i]):
            trail = self.c[i] - self.atr_mult * self.atr[i]
            self.stop = trail if self.stop is None else max(self.stop, trail)


class DonchianFixedRR(_Base):
    """M2 — Donchian-20 breakout, stop 2 ATR, target 6 ATR (3R)."""

    def __init__(self, bars, channel=20, stop_mult=2.0, rr=3.0):
        h, l, c = bars[:, 1], bars[:, 2], bars[:, 3]
        self.c = c
        self.hi = rolling_max_prev(h, channel)
        self.atr = atr_series(h, l, c)
        self.stop_mult, self.rr = stop_mult, rr

    def entry(self, i):
        return (not np.isnan(self.hi[i]) and not np.isnan(self.atr[i])
                and self.c[i] > self.hi[i])

    def on_entry(self, i, price):
        risk = self.stop_mult * self.atr[i]
        self.stop = price - risk
        self.target = price + self.rr * risk


class RegimeHold(_Base):
    """M3 — long while close > SMA200, flat otherwise. No stop."""

    def __init__(self, bars, period=200):
        self.c = bars[:, 3]
        self.ma = sma(self.c, period)

    def entry(self, i):
        return not np.isnan(self.ma[i]) and self.c[i] > self.ma[i]

    def exit_signal(self, i):
        return not np.isnan(self.ma[i]) and self.c[i] < self.ma[i]


class DipBuy(_Base):
    """M4 — RSI(14) < 30 while close > SMA200; exit RSI > 55 or 2 ATR stop."""

    def __init__(self, bars, rsi_in=30.0, rsi_out=55.0, stop_mult=2.0):
        h, l, c = bars[:, 1], bars[:, 2], bars[:, 3]
        self.c = c
        self.rsi = rsi_series(c)
        self.ma = sma(c, 200)
        self.atr = atr_series(h, l, c)
        self.rsi_in, self.rsi_out, self.stop_mult = rsi_in, rsi_out, stop_mult

    def entry(self, i):
        return (not np.isnan(self.rsi[i]) and not np.isnan(self.ma[i])
                and not np.isnan(self.atr[i])
                and self.rsi[i] < self.rsi_in and self.c[i] > self.ma[i])

    def on_entry(self, i, price):
        self.stop = price - self.stop_mult * self.atr[i]

    def exit_signal(self, i):
        return not np.isnan(self.rsi[i]) and self.rsi[i] > self.rsi_out


class MaCross(_Base):
    """M5 — SMA50/SMA200 golden cross in, death cross out."""

    def __init__(self, bars, fast=50, slow=200):
        c = bars[:, 3]
        self.f, self.s = sma(c, fast), sma(c, slow)

    def _valid(self, i):
        return (i > 0 and not np.isnan(self.s[i]) and not np.isnan(self.s[i - 1])
                and not np.isnan(self.f[i]) and not np.isnan(self.f[i - 1]))

    def entry(self, i):
        return (self._valid(i) and self.f[i] > self.s[i]
                and self.f[i - 1] <= self.s[i - 1])

    def exit_signal(self, i):
        return (self._valid(i) and self.f[i] < self.s[i]
                and self.f[i - 1] >= self.s[i - 1])


CANDIDATES = {
    "B0_buy_hold": BuyHold,
    "M1_donchian55_trail": DonchianTrail,
    "M2_donchian20_3R": DonchianFixedRR,
    "M3_sma200_hold": RegimeHold,
    "M4_rsi_dip": DipBuy,
    "M5_ma_cross": MaCross,
}


def run(bars: np.ndarray, name: str, start: int = 0,
        initial_equity: float = 10_000.0) -> StrategyResult:
    """Run one candidate over `bars`, trading only from index `start`.

    Bars before `start` are warm-up: they feed the indicators (they are past
    data, so this adds history without lookahead) but book no trade and are
    excluded from the equity curve.
    """
    return _simulate(bars, start, CANDIDATES[name](bars), initial_equity, name)
