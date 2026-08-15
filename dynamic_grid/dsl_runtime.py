"""E37 — single-slot leveraged runtime with DSL exits, dedup and risk halts.

Criteria in `docs/E37_CRITERIA.md`, declared before this file existed.

Why this is not `leveraged.py`: that engine takes a target weight per bar and
has no concept of an intrabar stop. This spec exits on a 3×ATR stop and a
ratcheting profit lock, both of which are decided *inside* the bar, so the
position must be simulated bar by bar with the high/low actually consulted.

Order of checks inside a bar, and the reason for it (§4 of the criteria):

1. **Liquidation first.** At 5x the account dies before any stop can help; a
   simulator that checked its own stop first would quietly survive bars that
   would have wiped a real account.
2. **Stop before target.** A bar that touches both books the stop. The engine
   never credits itself the favourable ordering.
3. **Gaps fill at the open**, never at the stop price, so a jump through the
   level costs what it really costs.

Nothing here places an order or touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

PERP_COST = 0.0010        # taker 0.05% + slippage 0.05%
MAINTENANCE = 0.005       # 0.5% maintenance margin
BARS_PER_DAY = 6          # 4h cadence

#: "balanced preset" ladder, denominated in **price move**, not ROE.
#:
#: The published preset is stated in ROE (+10% -> lock 30%, +35% -> 50%,
#: +100% -> 85%). ROE is leverage x price move, so an ROE-denominated ladder
#: silently changes the exit rule whenever leverage changes: at 5x the first
#: tier arms on a 2% move, at 1x it needs 10%. That entangles position sizing
#: with exit logic and made E37's "5x beats 1x" comparison uninterpretable.
#:
#: These thresholds are the exact 5x equivalents of the published ROE tiers, so
#: **at the declared 5x the behaviour is identical** (pinned by a test) while
#: every other leverage now keeps the same exit rule. No new parameter is
#: introduced and nothing is tuned.
PRICE_LADDER = ((0.20, 0.85), (0.07, 0.50), (0.02, 0.30))

#: Kept for reference: the original ROE-denominated form, no longer used.
PROFIT_LADDER_ROE = ((1.00, 0.85), (0.35, 0.50), (0.10, 0.30))


def atr(high, low, close, period=14):
    """Wilder's ATR, causal: index i uses bars 0..i only."""
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


def floor_from_ladder(peak_move: float) -> float:
    """Locked floor, as a fraction of the peak favourable **price move**.

    Zero until the first tier arms. Leverage does not appear anywhere here —
    that is the whole point of the change.
    """
    for tier, fraction in PRICE_LADDER:
        if peak_move >= tier:
            return fraction * peak_move
    return 0.0


@dataclass
class Trade:
    side: int
    entry_bar: int
    entry_price: float
    exit_bar: int = -1
    exit_price: float = 0.0
    reason: str = ""
    pnl: float = 0.0


@dataclass
class RunResult:
    equity: np.ndarray
    trades: list = field(default_factory=list)
    liquidations: int = 0
    halted_at: int = -1
    daily_stops: int = 0
    funding_paid: float = 0.0
    initial: float = 5_000.0

    @property
    def total_return(self):
        return float(self.equity[-1] / self.initial - 1.0)

    @property
    def max_drawdown(self):
        curve = np.concatenate(([self.initial], self.equity))
        peak = np.maximum.accumulate(curve)
        return float(((peak - curve) / peak).max())

    @property
    def robust(self):
        return self.total_return - 2.0 * self.max_drawdown

    @property
    def ruined(self):
        return bool(self.equity.min() < self.initial * 0.10)

    def stats(self):
        closed = [t for t in self.trades if t.exit_bar >= 0]
        wins = [t.pnl for t in closed if t.pnl > 0]
        losses = [-t.pnl for t in closed if t.pnl <= 0]
        gross_loss = sum(losses)
        reasons = {}
        for t in closed:
            reasons[t.reason] = reasons.get(t.reason, 0) + 1
        return {
            "trades": len(closed),
            "win_rate": (len(wins) / len(closed)) if closed else 0.0,
            "profit_factor": (sum(wins) / gross_loss) if gross_loss > 0 else None,
            "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
            "avg_loss": (gross_loss / len(losses)) if losses else 0.0,
            "exit_reasons": reasons,
        }


def signals(close, fast_p=9, slow_p=21, rsi_p=14, rsi_long=45.0, rsi_short=55.0,
            use_rsi=True):
    """Per-bar entry intent: +1 long, -1 short, 0 none. Fires only on a cross.

    Dedup is structural: intent is non-zero only on the bar the EMAs actually
    cross, so holding a position through a hundred confirming bars cannot
    re-fire the same signal.
    """
    from dynamic_grid.ema_rsi import ema, rsi as rsi_series

    fast, slow = ema(close, fast_p), ema(close, slow_p)
    strength = rsi_series(close, rsi_p)
    intent = np.zeros(len(close), dtype=int)
    for i in range(1, len(close)):
        if np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(fast[i - 1]) or np.isnan(slow[i - 1]):
            continue
        crossed_up = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
        crossed_down = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]
        if crossed_up:
            if not use_rsi or (not np.isnan(strength[i]) and strength[i] > rsi_long):
                intent[i] = 1
        elif crossed_down:
            if not use_rsi or (not np.isnan(strength[i]) and strength[i] < rsi_short):
                intent[i] = -1
    return intent


#: Re-entry policies (E38 §2, axis A). The entry signal only fires on the bar
#: the EMAs actually cross, so what happens *after* a position closes is a
#: separate, undeclared degree of freedom in the source spec.
REENTRY = ("cross_only", "rearm", "rearm_after_win")

#: Readings of `drawdown_halt` (E38 §2, axis B).
HALT_MODES = ("permanent", "daily", "off")


def trend_state(close, fast_p=9, slow_p=21, rsi_p=14, rsi_long=45.0,
                rsi_short=55.0, use_rsi=True):
    """+1 / -1 / 0 for the *standing* trend, not the crossing event.

    `signals` answers "did it cross here"; this answers "which way is it now",
    which is what a re-arm policy needs.
    """
    from dynamic_grid.ema_rsi import ema, rsi as rsi_series

    fast, slow = ema(close, fast_p), ema(close, slow_p)
    strength = rsi_series(close, rsi_p)
    state = np.zeros(len(close), dtype=int)
    for i in range(len(close)):
        if np.isnan(fast[i]) or np.isnan(slow[i]):
            continue
        if fast[i] > slow[i]:
            if not use_rsi or (not np.isnan(strength[i]) and strength[i] > rsi_long):
                state[i] = 1
        elif fast[i] < slow[i]:
            if not use_rsi or (not np.isnan(strength[i]) and strength[i] < rsi_short):
                state[i] = -1
    return state


def run(close, high, low, funding=None, *, leverage=5.0, atr_mult=3.0,
        initial=5_000.0, cost=PERP_COST, drawdown_halt=0.25, daily_loss_limit=0.08,
        halt_is_permanent=True, use_rsi=False, warmup=60,
        reentry="cross_only", halt_mode=None):
    """Simulate the declared spec. Returns a `RunResult`.

    `reentry` and `halt_mode` are the two E38 axes. `halt_mode` supersedes
    `halt_is_permanent` when given, so E37's calls keep their exact meaning.

    `use_rsi` defaults to **off**. E37 measured the declared 45/55 band
    rejecting **0 of 204** signals on 2024-07..2026-08 and **0 of 185** on
    2022-06..2024-07: at an EMA9/21 cross the RSI is always already on the
    permitting side, so the filter never binds. The flag is kept so that result
    stays reproducible, and because "inert on BTC 4h over these two windows" is
    not the same claim as "inert everywhere".
    """
    if reentry not in REENTRY:
        raise ValueError(f"unknown reentry policy: {reentry!r}")
    if halt_mode is not None:
        if halt_mode not in HALT_MODES:
            raise ValueError(f"unknown halt mode: {halt_mode!r}")
        halt_is_permanent = halt_mode == "permanent"
    halt_disabled = halt_mode == "off"
    n = len(close)
    band = atr(high, low, close, 14)
    intent = signals(close, use_rsi=use_rsi)
    standing = trend_state(close, use_rsi=use_rsi)
    funding = np.zeros(n) if funding is None else funding

    equity = np.empty(n - warmup)
    cash = float(initial)
    peak_equity = cash
    day_open_equity = cash
    day_index = warmup // BARS_PER_DAY
    day_blocked = False
    halted = False
    halted_at = -1
    daily_stops = 0
    liquidations = 0
    funding_paid = 0.0
    trades: list[Trade] = []

    side = 0
    last_exit_reason = ""
    last_exit_bar = -1
    entry_price = 0.0
    stop_price = 0.0
    peak_roe = 0.0
    floor_roe = 0.0

    def close_position(bar, price, reason):
        nonlocal cash, side, peak_roe, floor_roe, last_exit_reason, last_exit_bar
        move = (price / entry_price - 1.0) * side
        gross = cash * leverage * move
        cash += gross
        cash -= abs(cash) * leverage * cost if cash > 0 else 0.0
        trade = trades[-1]
        trade.exit_bar, trade.exit_price, trade.reason = bar, float(price), reason
        trade.pnl = float(gross)
        side, peak_roe, floor_roe = 0, 0.0, 0.0
        last_exit_reason, last_exit_bar = reason, bar

    for i in range(warmup, n):
        # --- new UTC day resets the daily loss gate
        if i // BARS_PER_DAY != day_index:
            day_index = i // BARS_PER_DAY
            day_open_equity = cash
            day_blocked = False
            if halted and not halt_is_permanent:
                # Resume next day and re-baseline the peak, otherwise the book
                # sits below the old high-water mark and re-halts immediately —
                # which is what made this arm silently identical to the
                # permanent one on the first run.
                halted = False
                peak_equity = cash

        if side != 0 and not halted:
            # 1) liquidation first — the account dies before a stop can help
            adverse = (low[i] if side > 0 else high[i])
            excursion = (adverse / close[i - 1] - 1.0) * side
            if 1.0 + leverage * excursion <= MAINTENANCE:
                cash *= MAINTENANCE
                trade = trades[-1]
                trade.exit_bar, trade.exit_price = i, float(adverse)
                trade.reason, trade.pnl = "liquidation", float(-cash)
                side, peak_roe, floor_roe = 0, 0.0, 0.0
                last_exit_reason, last_exit_bar = "liquidation", i
                liquidations += 1
            else:
                # 2) hard stop, gap-aware: a jump through fills at the open
                hit = (low[i] <= stop_price) if side > 0 else (high[i] >= stop_price)
                if hit:
                    gapped = (open_through(close[i - 1], stop_price, side))
                    fill = min(close[i - 1], stop_price) if side > 0 else max(close[i - 1], stop_price)
                    close_position(i, fill if gapped else stop_price, "stop_3atr")
                else:
                    # 3) profit ladder on the bar's favourable excursion,
                    #    measured in price move so leverage cannot move the tiers
                    favourable = (high[i] if side > 0 else low[i])
                    move = (favourable / entry_price - 1.0) * side
                    peak_roe = max(peak_roe, move)
                    floor_roe = max(floor_roe, floor_from_ladder(peak_roe))
                    close_move = (close[i] / entry_price - 1.0) * side
                    if floor_roe > 0.0 and close_move <= floor_roe:
                        close_position(i, close[i], "profit_lock")

            # funding on the notional actually carried
            if side != 0 and funding[i] != 0.0:
                paid = cash * leverage * funding[i] * side
                cash -= paid
                funding_paid += float(paid)

        # --- risk halts, evaluated on the running book
        peak_equity = max(peak_equity, cash)
        if not halt_disabled and not halted and cash <= peak_equity * (1.0 - drawdown_halt):
            if side != 0:
                close_position(i, close[i], "drawdown_halt")
            halted, halted_at = True, i
        if not halted and not day_blocked and cash <= day_open_equity * (1.0 - daily_loss_limit):
            if side != 0:
                close_position(i, close[i], "daily_loss_limit")
            day_blocked = True
            daily_stops += 1

        # --- entries: one slot, dedup by construction
        wants = int(intent[i])
        if wants == 0 and reentry != "cross_only" and 0 <= last_exit_bar < i:
            # Re-arm: the cross already happened, the trend still stands. This
            # is the undeclared degree of freedom in the source spec.
            if reentry == "rearm" or (reentry == "rearm_after_win"
                                      and last_exit_reason == "profit_lock"):
                wants = int(standing[i])

        if not halted and not day_blocked and side == 0 and wants != 0 \
                and not np.isnan(band[i]) and cash > 0:
            side = wants
            entry_price = float(close[i])
            stop_price = entry_price - side * atr_mult * band[i]
            cash -= cash * leverage * cost
            peak_roe = floor_roe = 0.0
            trades.append(Trade(side=side, entry_bar=i, entry_price=entry_price))

        equity[i - warmup] = max(cash, 0.0)
        if halt_is_permanent and halted:
            equity[i - warmup:] = max(cash, 0.0)
            break

    return RunResult(equity=equity, trades=trades, liquidations=liquidations,
                     halted_at=halted_at, daily_stops=daily_stops,
                     funding_paid=funding_paid, initial=initial)


def open_through(prev_close, stop, side):
    """True when the previous close was already beyond the stop (a gap)."""
    return (prev_close < stop) if side > 0 else (prev_close > stop)
