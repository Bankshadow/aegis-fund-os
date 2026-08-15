"""E44 — S003 "fade failed breakout" engine, implemented from the given spec.

Spec: `s003_agent_spec.md` sections 2-5. Criteria: `docs/E44_CRITERIA.md`.

This is a **reproduction**, not a design. Every constant below is copied from the
spec and none of them is tunable here — the whole point of E44 is to find out
whether a literal implementation lands on the locked baseline.

Two rules do most of the work and are easy to get subtly wrong, so they are
stated once here and pinned by tests:

* **The entry bar is not managed.** Stops and targets are only evaluated from
  the bar after entry. Checking them on the signal bar would let a trade both
  open and hit its target inside the same candle, which the spec forbids.
* **Optimistic TP-first**: when one bar touches both TP3 and the stop, the spec
  counts TP3. `sl_first` inverts that and is the declared stress model, not a
  fix — the gap between the two is the honest error bar on the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SL_BUFFER = 0.25
MIN_STOP_ATR = 0.5
MAX_RISK_ATR = 3.0
FEE_SIDE = 0.0005          # 0.05% per side, 0.1% round trip
WARMUP = 201
DOJI_EPS = 1e-12


def wilder_atr(high, low, close, period: int = 14) -> np.ndarray:
    """Wilder ATR. NaN until seeded; index i uses bars 0..i only."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev = close[:-1]
    tr[1:] = np.maximum.reduce([high[1:] - low[1:],
                                np.abs(high[1:] - prev),
                                np.abs(low[1:] - prev)])
    out = np.full(n, np.nan)
    if n < period:
        return out
    out[period - 1] = tr[:period].mean()
    for i in range(period, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def strat_type(high, low) -> list:
    """STRAT classification against the prior bar (spec section 2)."""
    out = [None]
    for i in range(1, len(high)):
        h, l, h1, l1 = high[i], low[i], high[i - 1], low[i - 1]
        if h <= h1 and l >= l1:
            out.append("1")
        elif h > h1 and l < l1:
            out.append("3")
        elif h > h1 and l >= l1:
            out.append("2U")
        elif l < l1 and h <= h1:
            out.append("2D")
        elif h > h1:
            out.append("2U")
        elif l < l1:
            out.append("2D")
        else:
            out.append("1")
    return out


@dataclass
class Trade:
    symbol: str
    side: int                 # +1 long, -1 short
    entry_bar: int
    entry_date: str
    entry: float
    stop: float
    r: float
    tp1: float
    tp2: float
    tp3: float
    exit_bar: int = -1
    exit_date: str = ""
    exit_price: float = 0.0
    reason: str = ""
    be_armed: bool = False
    pnl_r_gross: float = 0.0
    fee_r: float = 0.0
    pnl_r_net: float = 0.0


@dataclass
class Result:
    symbol: str
    trades: list = field(default_factory=list)

    @property
    def closed(self):
        return [t for t in self.trades if t.exit_bar >= 0]

    @property
    def port_r(self):
        return float(sum(t.pnl_r_net for t in self.closed))


@dataclass(frozen=True)
class Params:
    """One module's worth of knobs. Defaults ARE the S003 spec, bit for bit.

    E46 changes exactly one field at a time; a test pins that the defaults
    reproduce the locked engine so a variant run can never be confused with a
    silently altered baseline.
    """

    sl_buffer: float = SL_BUFFER
    min_stop_atr: float = MIN_STOP_ATR
    max_risk_atr: float = MAX_RISK_ATR
    tp3_mult: float = 3.0
    be_rule: str = "after_tp2"      # "after_tp2" | "after_tp1" | "none"
    fee_side: float = FEE_SIDE      # E50 stresses this; the default is the spec's


BASE = Params()


def plan_trade(symbol, i, dates, o, h, l, c, atr, side,
               params: Params = BASE) -> Trade | None:
    """Stop / R / targets exactly as spec section 4. None when the trade is skipped."""
    entry, band = c[i], atr[i]
    if np.isnan(band) or band <= 0:
        return None
    if side > 0:
        stop = min(l[i] - params.sl_buffer * band, entry - params.min_stop_atr * band)
        if entry - stop < params.min_stop_atr * band:
            stop = entry - params.min_stop_atr * band
        r = entry - stop
    else:
        stop = max(h[i] + params.sl_buffer * band, entry + params.min_stop_atr * band)
        if stop - entry < params.min_stop_atr * band:
            stop = entry + params.min_stop_atr * band
        r = stop - entry
    if r <= 0 or r > params.max_risk_atr * band:
        return None
    return Trade(symbol=symbol, side=side, entry_bar=i, entry_date=dates[i],
                 entry=float(entry), stop=float(stop), r=float(r),
                 tp1=float(entry + side * r), tp2=float(entry + 2 * side * r),
                 tp3=float(entry + params.tp3_mult * side * r))


def close_trade(t: Trade, bar: int, dates, price: float, reason: str,
                fee_side: float = FEE_SIDE):
    t.exit_bar, t.exit_date, t.exit_price, t.reason = bar, dates[bar], float(price), reason
    t.pnl_r_gross = (price - t.entry) * t.side / t.r
    t.fee_r = (2.0 * fee_side * t.entry) / t.r
    t.pnl_r_net = t.pnl_r_gross - t.fee_r


def manage_bar(t: Trade, i: int, dates, h, l, intrabar: str, params: Params,
               be_on_arming_bar: bool = False) -> bool:
    """Evaluate bar `i` against the open trade. True when the trade closed.

    `be_on_arming_bar` is the literal reading of the locked spec, where the bar
    that arms break-even may also stop out on the new stop. The default is the
    engine E44-E51 were all measured with; E55 D1 quantifies the gap rather than
    silently switching, because every logged result depends on this choice.

    **`intrabar="sl_first"` does two separate things, and the name only says the
    first.** Read both before quoting a number from it:

    1. *tie-break*: a bar touching TP3 and the live stop books the stop;
    2. *arming bar*: the break-even stop is live on the very bar that arms it.

    Under the spec's `be_rule="after_tp2"` these are not independent. TP2 sits
    between the entry and TP3, so **any bar that reaches TP3 has already tagged
    TP2**; break-even is therefore armed on that same bar and the stop that
    races TP3 is always the break-even stop, never the original one. The race
    the name describes cannot happen at the original stop level at all - not
    rarely, never - so on this rule set `sl_first` reduces to (2) and is
    numerically identical to `be_on_arming_bar=True`.

    E56 counted zero such bars on SOL+LINK and reported it as an empirical
    finding; it is structural, and would be zero on any data. The name is left
    alone because renaming it to something like `be_literal` would hide (1),
    which does still govern once `be_rule="none"`, and because every logged JSON
    from E44 on keys its results by these strings.

    E56's premise and E57's R2 were both built on reading the name instead of
    the rule. `tests/test_strat_trap.py` pins both halves.
    """
    hit_tp3 = h[i] >= t.tp3 if t.side > 0 else l[i] <= t.tp3
    hit_stop = l[i] <= t.stop if t.side > 0 else h[i] >= t.stop
    trigger = t.tp1 if params.be_rule == "after_tp1" else t.tp2
    arms_now = (params.be_rule != "none"
                and ((h[i] >= trigger) if t.side > 0 else (l[i] <= trigger)))

    if arms_now and not t.be_armed:
        t.be_armed = True
        t.stop = t.entry
        # Spec 5.7: a bar that arms BE does not also stop out on the new
        # stop under the optimistic model.
        if intrabar == "tp_first" and not be_on_arming_bar:
            hit_stop = False
        else:
            hit_stop = l[i] <= t.stop if t.side > 0 else h[i] >= t.stop

    if hit_tp3 and hit_stop:
        if intrabar == "tp_first":
            close_trade(t, i, dates, t.tp3, "TP3", params.fee_side)
        else:
            close_trade(t, i, dates, t.stop,
                        "BE_SL" if t.be_armed else "SL", params.fee_side)
        return True
    if hit_tp3:
        close_trade(t, i, dates, t.tp3, "TP3", params.fee_side)
        return True
    if hit_stop:
        close_trade(t, i, dates, t.stop, "BE_SL" if t.be_armed else "SL",
                    params.fee_side)
        return True
    return False


def signal_side(strat_i, o_i, c_i) -> int:
    """Spec section 3: red 2U fades short, green 2D fades long. 0 = no signal."""
    if strat_i not in ("2U", "2D") or abs(c_i - o_i) < DOJI_EPS:
        return 0
    if strat_i == "2U" and c_i < o_i:
        return -1
    if strat_i == "2D" and c_i > o_i:
        return +1
    return 0


def run_symbol(symbol, dates, o, h, l, c, intrabar: str = "tp_first",
               params: Params = BASE, be_on_arming_bar: bool = False) -> Result:
    """One asset, one open position at a time (spec section 3)."""
    if intrabar not in ("tp_first", "sl_first"):
        raise ValueError(f"unknown intrabar model: {intrabar!r}")
    atr = wilder_atr(h, l, c)
    strat = strat_type(h, l)
    res = Result(symbol=symbol)
    open_trade: Trade | None = None

    for i in range(len(c)):
        # ---- manage an existing position, never on its own entry bar --------
        if open_trade is not None and i > open_trade.entry_bar:
            if manage_bar(open_trade, i, dates, h, l, intrabar, params,
                          be_on_arming_bar):
                open_trade = None

        # ---- entries -------------------------------------------------------
        if open_trade is None and i >= WARMUP:
            side = signal_side(strat[i], o[i], c[i])
            if side:
                planned = plan_trade(symbol, i, dates, o, h, l, c, atr, side,
                                     params)
                if planned is not None:
                    open_trade = planned
                    res.trades.append(planned)

    if open_trade is not None:
        close_trade(open_trade, len(c) - 1, dates, c[-1], "EOD", params.fee_side)
    return res


# --------------------------------------------------------------------------
# S017 — portfolio-level cooldown (locked spec section 5)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Cooldown:
    """After `streak` consecutive losing closes, skip the next `skip` signals.

    The locked spec is `streak=4, skip=2` counted across the whole book. The
    spec also names two variants it says failed walk-forward — per-coin streaks
    and pausing after two losses — so `per_symbol` exists to measure the first
    of them rather than to be used.
    """

    streak: int = 4
    skip: int = 2
    per_symbol: bool = False


S017 = Cooldown()


@dataclass
class PortfolioResult:
    per_symbol: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)   # (date, symbol) of skipped signals
    signals: int = 0                              # signals that reached the cooldown gate

    @property
    def closed(self):
        out = [t for r in self.per_symbol.values() for t in r.closed]
        out.sort(key=lambda t: (t.exit_date, t.symbol))
        return out

    @property
    def port_r(self):
        return float(sum(t.pnl_r_net for t in self.closed))

    @property
    def duty(self):
        """Share of gated signals the cooldown actually skipped."""
        return len(self.skipped) / self.signals if self.signals else 0.0


def run_portfolio(feeds, *, cooldown: Cooldown | None = None,
                  intrabar: str = "tp_first", params: Params = BASE,
                  be_on_arming_bar: bool = False,
                  skip_decider=None) -> PortfolioResult:
    """Every asset on one clock, so a portfolio-level rule can see them all.

    `feeds` maps symbol -> (dates, o, h, l, c). Symbols keep independent
    entries and one position each, exactly as `run_symbol`; only the cooldown
    is shared. With `cooldown=None` and no `skip_decider` this reproduces
    `run_symbol` per asset trade for trade — E55 H1 pins that.

    A skipped signal is not a deferred one: the bar passes and the setup is
    gone. That is why this cannot be post-processed from a finished trade list
    — skipping frees the asset earlier, so the *next* signal that a held
    position would have blocked becomes tradeable and the whole sequence moves.

    `skip_decider(symbol, date) -> bool` replaces the cooldown with an
    arbitrary rule; E55 A3 uses it for the placebo. It is mutually exclusive
    with `cooldown`.
    """
    if intrabar not in ("tp_first", "sl_first"):
        raise ValueError(f"unknown intrabar model: {intrabar!r}")
    if cooldown is not None and skip_decider is not None:
        raise ValueError("pass either a cooldown or a skip_decider, not both")

    syms = sorted(feeds)
    state = {}
    for s in syms:
        dates, o, h, l, c = feeds[s]
        state[s] = {"dates": dates, "o": o, "h": h, "l": l, "c": c,
                    "atr": wilder_atr(h, l, c), "strat": strat_type(h, l),
                    "at": {d: i for i, d in enumerate(dates)},
                    "open": None}

    res = PortfolioResult(per_symbol={s: Result(symbol=s) for s in syms})
    axis = sorted({d for s in syms for d in state[s]["dates"]})
    # one loss streak and one skip budget for the whole book (spec section 5)
    streaks = {s: 0 for s in syms} if (cooldown and cooldown.per_symbol) else {"": 0}
    cools = dict.fromkeys(streaks, 0)
    bucket = (lambda s: s) if (cooldown and cooldown.per_symbol) else (lambda s: "")

    for day in axis:
        # ---- manage every open position first, book-wide --------------------
        # Exits happen intrabar, entries at the close, so a loss booked today
        # is already part of the streak when today's signals are judged.
        for s in syms:
            st = state[s]
            i = st["at"].get(day)
            t = st["open"]
            if i is None or t is None or i <= t.entry_bar:
                continue
            if manage_bar(t, i, st["dates"], st["h"], st["l"], intrabar, params,
                          be_on_arming_bar):
                st["open"] = None
                k = bucket(s)
                if t.pnl_r_net < 0:
                    streaks[k] += 1
                    if cooldown is not None and streaks[k] >= cooldown.streak:
                        cools[k] = cooldown.skip
                        streaks[k] = 0
                else:
                    streaks[k] = 0

        # ---- then entries, assets in a fixed order --------------------------
        for s in syms:
            st = state[s]
            i = st["at"].get(day)
            if i is None or st["open"] is not None or i < WARMUP:
                continue
            side = signal_side(st["strat"][i], st["o"][i], st["c"][i])
            if not side:
                continue
            res.signals += 1
            k = bucket(s)
            if cooldown is not None and cools[k] > 0:
                cools[k] -= 1
                res.skipped.append((day, s))
                continue
            if skip_decider is not None and skip_decider(s, day):
                res.skipped.append((day, s))
                continue
            planned = plan_trade(s, i, st["dates"], st["o"], st["h"], st["l"],
                                 st["c"], st["atr"], side, params)
            if planned is not None:
                st["open"] = planned
                res.per_symbol[s].trades.append(planned)

    for s in syms:
        st = state[s]
        if st["open"] is not None:
            close_trade(st["open"], len(st["c"]) - 1, st["dates"], st["c"][-1],
                        "EOD", params.fee_side)
    return res


def fold_of(entry_date: str, boundaries) -> int:
    """Index of the OOS fold a trade's ENTRY date falls in, or -1."""
    for k in range(len(boundaries) - 1):
        if boundaries[k] <= entry_date < boundaries[k + 1]:
            return k
    return -1
