"""Multi-asset market data with real volume, spread estimate, and funding.

Sources (all public Binance endpoints, saved under data/):
  {SYM}_1d.json / {SYM}_4h.json  - spot klines: OHLC + base volume + quote
                                   (USDT) volume per bar
  {SYM}_funding.json             - perpetual funding events (rate per 8h)

Spread: Binance does not publish historical bid-ask, so we estimate the
effective spread from real high/low data with the Corwin-Schultz (2012)
estimator and take the median across bars. This is an approximation and is
flagged as such wherever results are reported; it errs conservative (CS
tends to overestimate spreads for liquid pairs).

Funding: applied as a constant per-bar rate = mean(real events) x events
per bar (8h cycle -> 3/day, 0.5 per 4h bar). Real funding varies bar to
bar; using the mean understates variance but uses the true average cost.
Coverage is the last 500 events (~167 days) - noted as a limitation.

``funding_series`` aligns each bar to the latest funding event at or before
the bar open (forward-fill). Bars before the first funding event are 0.0
(neutral for bias; mean cost path is unchanged via ``funding_per_bar``).
"""

import json
import os

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = ["1d", "4h"]
FUNDING_EVENTS_PER_BAR = {"1d": 3.0, "4h": 0.5}   # funding settles every 8h


def load_klines(symbol: str, tf: str) -> dict:
    """Return ohlc, volume, quote_volume, and open timestamps (ms)."""
    with open(os.path.join(DATA_DIR, f"{symbol}_{tf}.json")) as f:
        raw = json.load(f)
    return {
        "ohlc": np.array([[float(k[1]), float(k[2]), float(k[3]), float(k[4])]
                          for k in raw]),
        "volume": np.array([float(k[5]) for k in raw]),
        "quote_volume": np.array([float(k[7]) for k in raw]),
        "timestamps": np.array([int(k[0]) for k in raw], dtype=np.int64),
    }


def load_funding_events(symbol: str) -> list[dict]:
    with open(os.path.join(DATA_DIR, f"{symbol}_funding.json")) as f:
        return json.load(f)


def corwin_schultz_spread(high: np.ndarray, low: np.ndarray) -> float:
    """Median effective spread (fraction of price) via Corwin-Schultz."""
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = np.log(high / low) ** 2
        beta = hl[:-1] + hl[1:]
        h2 = np.maximum(high[:-1], high[1:])
        l2 = np.minimum(low[:-1], low[1:])
        gamma = np.log(h2 / l2) ** 2
        k = 3 - 2 * np.sqrt(2)
        alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
        spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    spread = spread[np.isfinite(spread)]
    spread = spread[spread > 0]
    return float(np.median(spread)) if len(spread) else 0.0


def funding_per_bar(symbol: str, tf: str) -> float:
    """Mean real funding rate per bar (sign: positive = longs pay)."""
    events = load_funding_events(symbol)
    mean_8h = float(np.mean([float(e["fundingRate"]) for e in events]))
    return mean_8h * FUNDING_EVENTS_PER_BAR[tf]


def align_funding_to_bars(bar_timestamps_ms: np.ndarray,
                          events: list[dict]) -> np.ndarray:
    """Per-bar funding rate: last event at or before bar open (no lookahead).

    Bars before the first funding event get 0.0 (neutral bias).
    """
    if len(bar_timestamps_ms) == 0:
        return np.zeros(0, dtype=float)
    if not events:
        return np.zeros(len(bar_timestamps_ms), dtype=float)

    times = np.array([int(e["fundingTime"]) for e in events], dtype=np.int64)
    rates = np.array([float(e["fundingRate"]) for e in events], dtype=float)
    order = np.argsort(times)
    times, rates = times[order], rates[order]

    # searchsorted: index of last event with time <= bar_ts
    idx = np.searchsorted(times, bar_timestamps_ms, side="right") - 1
    out = np.zeros(len(bar_timestamps_ms), dtype=float)
    valid = idx >= 0
    out[valid] = rates[idx[valid]]
    return out


def market_profile(symbol: str, tf: str) -> dict:
    """Everything a cost-aware backtest needs for one asset/timeframe."""
    d = load_klines(symbol, tf)
    half_spread = corwin_schultz_spread(d["ohlc"][:, 1], d["ohlc"][:, 2]) / 2
    events = load_funding_events(symbol)
    return {
        **d,
        "half_spread": half_spread,
        "funding_per_bar": funding_per_bar(symbol, tf),
        "funding_series": align_funding_to_bars(d["timestamps"], events),
        "median_quote_volume": float(np.median(d["quote_volume"])),
    }


def pair_ratio_series(alt_symbol: str, base_symbol: str, tf: str,
                      lookback: int = 20) -> dict:
    """Aligned alt/base ratio and log-ratio momentum (no lookahead).

    ``momentum[t] = log(ratio_t) - log(ratio_{t-lookback})`` for t >= lookback,
    else 0. Timestamps must match (true for current BTC/ETH/SOL 4h dumps).
    """
    alt = load_klines(alt_symbol, tf)
    base = load_klines(base_symbol, tf)
    if not np.array_equal(alt["timestamps"], base["timestamps"]):
        raise ValueError(
            f"timestamp mismatch: {alt_symbol} vs {base_symbol} on {tf}")
    alt_c = alt["ohlc"][:, 3]
    base_c = np.maximum(base["ohlc"][:, 3], 1e-12)
    ratio = alt_c / base_c
    log_r = np.log(np.maximum(ratio, 1e-12))
    lb = max(int(lookback), 1)
    momentum = np.zeros(len(log_r), dtype=float)
    if len(log_r) > lb:
        momentum[lb:] = log_r[lb:] - log_r[:-lb]
    return {
        "timestamps": alt["timestamps"],
        "ratio": ratio,
        "momentum": momentum,
        "lookback": lb,
        "alt_symbol": alt_symbol,
        "base_symbol": base_symbol,
        "timeframe": tf,
    }
