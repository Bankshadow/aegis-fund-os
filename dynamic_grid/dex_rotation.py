"""E41 — DEX-vol relative-strength rotation (Osmo S2).

Criteria in `docs/E41_CRITERIA.md`, declared before this file existed.

Weekly long-only rotation among mapped chain assets. Signal at day t uses
DEX volume and prices through t only; execution at close[t].
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LOOKBACK = 7
REBALANCE = 7
WARMUP = 60
COST = 0.0015
OOS = 252
HELD_OUT_TAIL = 252
SEED = 0

# chain -> spot key in universe file
PRIMARY_MAP = (("ETH", "Ethereum"), ("SOL", "Solana"))
HELD_ASSET_MAP = (("ETH", "Ethereum"), ("SOL", "Solana"), ("BNB", "BSC"))


@dataclass
class BacktestResult:
    returns: np.ndarray          # daily portfolio simple returns (after cost on turn days)
    equity: np.ndarray
    total_return: float
    max_drawdown: float
    robust: float
    n_rebalances: int
    turnover: float


def load_universe_closes(universe: dict, symbols: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Return common dates (ms), date index alignment, closes[symbol]."""
    series = {}
    for sym in symbols:
        raw = universe[sym]
        series[sym] = {int(b[0]): float(b[4]) for b in raw}
    common = sorted(set.intersection(*(set(s.keys()) for s in series.values())))
    dates = np.array(common, dtype=np.int64)
    closes = {sym: np.array([series[sym][t] for t in common], dtype=float) for sym in symbols}
    return dates, closes


def load_vol_chart(chart: list, dates_ms: np.ndarray) -> np.ndarray:
    """Map llama [sec, vol] onto Binance day opens (ms). Missing → NaN."""
    by_day = {int(row[0]) * 1000: float(row[1]) for row in chart}
    return np.array([by_day.get(int(t), np.nan) for t in dates_ms], dtype=float)


def growth(values: np.ndarray, lookback: int = LOOKBACK) -> np.ndarray:
    out = np.full(len(values), np.nan)
    for i in range(lookback, len(values)):
        prev = values[i - lookback]
        if not np.isfinite(prev) or prev <= 0 or not np.isfinite(values[i]):
            continue
        out[i] = values[i] / prev - 1.0
    return out


def pick_winner(scores: dict[str, float]) -> list[str]:
    """Return list of symbols tied for max score (finite only)."""
    finite = {k: v for k, v in scores.items() if np.isfinite(v)}
    if not finite:
        return []
    best = max(finite.values())
    return sorted([k for k, v in finite.items() if v == best])


def run_rotation(
    closes: dict[str, np.ndarray],
    score_series: dict[str, np.ndarray],
    *,
    mode: str,
    rng: np.random.Generator | None = None,
) -> BacktestResult:
    """mode: dex|price|eq|rand — score_series ignored for eq/rand/price uses closes growth."""
    symbols = list(closes.keys())
    n = len(next(iter(closes.values())))
    weights = np.zeros((n, len(symbols)))
    sym_index = {s: j for j, s in enumerate(symbols)}

    # initial equal until first rebalance after warmup
    start = WARMUP
    for j in range(len(symbols)):
        weights[start, j] = 1.0 / len(symbols)

    n_reb = 0
    for i in range(start, n, REBALANCE):
        if mode == "eq":
            winners = symbols
        elif mode == "rand":
            assert rng is not None
            winners = [symbols[int(rng.integers(0, len(symbols)))]]
        elif mode == "price":
            scores = {
                s: (closes[s][i] / closes[s][i - LOOKBACK] - 1.0)
                if i >= LOOKBACK and closes[s][i - LOOKBACK] > 0 else np.nan
                for s in symbols
            }
            winners = pick_winner(scores) or symbols
        elif mode == "dex":
            scores = {s: float(score_series[s][i]) for s in symbols}
            winners = pick_winner(scores) or symbols
        else:
            raise ValueError(mode)
        w = 1.0 / len(winners)
        for s in winners:
            weights[i, sym_index[s]] = w
        n_reb += 1
        # hold constant until next rebalance
        end = min(i + REBALANCE, n)
        for k in range(i + 1, end):
            weights[k] = weights[i]

    # daily asset returns
    asset_ret = {s: np.zeros(n) for s in symbols}
    for s in symbols:
        c = closes[s]
        asset_ret[s][1:] = c[1:] / c[:-1] - 1.0

    port = np.zeros(n)
    turnover_cost = np.zeros(n)
    prev_w = weights[start].copy()
    total_turnover = 0.0
    for i in range(start, n):
        w = weights[i]
        # cost when weights change vs previous bar's weights
        if i > start:
            turned = 0.5 * np.abs(w - prev_w).sum()
            if turned > 1e-12:
                # both legs of the swapped notional pay COST
                turnover_cost[i] = turned * 2.0 * COST
                total_turnover += turned
        day_ret = sum(w[sym_index[s]] * asset_ret[s][i] for s in symbols)
        port[i] = day_ret - turnover_cost[i]
        prev_w = w

    equity = np.ones(n)
    for i in range(start + 1, n):
        equity[i] = equity[i - 1] * (1.0 + port[i])
    equity[:start] = np.nan
    # metrics from start
    path = equity[start:]
    path = path[np.isfinite(path)]
    if len(path) < 2:
        return BacktestResult(port, equity, 0.0, 0.0, 0.0, n_reb, 0.0)
    total_return = float(path[-1] / path[0] - 1.0)
    peak = np.maximum.accumulate(path)
    max_dd = float(np.max((peak - path) / peak))
    return BacktestResult(
        returns=port,
        equity=equity,
        total_return=total_return,
        max_drawdown=max_dd,
        robust=float(total_return - 2.0 * max_dd),
        n_rebalances=n_reb,
        turnover=float(total_turnover),
    )


def window_metrics(result: BacktestResult, start: int, end: int) -> dict:
    """Metrics on equity path slice [start, end)."""
    eq = result.equity[start:end]
    # rebuild from returns to avoid NaN warmup inside window
    rets = result.returns[start:end].copy()
    if start > 0:
        # first day in window: no return carry from outside
        rets[0] = 0.0
    equity = np.cumprod(1.0 + rets)
    total = float(equity[-1] - 1.0)
    peak = np.maximum.accumulate(equity)
    max_dd = float(np.max((peak - equity) / peak)) if len(equity) else 0.0
    return {
        "return": total,
        "maxDD": max_dd,
        "robust": float(total - 2.0 * max_dd),
        "n_days": int(end - start),
    }


def oos_windows(n: int, held_out_tail: int = HELD_OUT_TAIL, oos: int = OOS,
                warmup: int = WARMUP) -> list[tuple[int, int]]:
    """Non-overlapping OOS windows excluding the held-out tail."""
    end = n - held_out_tail
    windows = []
    t = warmup
    while t + oos <= end:
        windows.append((t, t + oos))
        t += oos
    return windows
