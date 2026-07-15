"""Loader for real OHLC data (currently: Binance public klines JSON dump).

Source: `data/btc_binance_1d.json`, fetched via the unauthenticated endpoint

    GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000

1000 daily bars, Oct 2023 - present. No API key required. Re-fetch with:

    curl -sS "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000" \
        -o data/btc_binance_1d.json
"""

import json
import os

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_binance_klines(path: str = None) -> np.ndarray:
    """Return an (n, 4) [open, high, low, close] array, oldest first."""
    path = path or os.path.join(DATA_DIR, "btc_binance_1d.json")
    with open(path) as f:
        raw = json.load(f)
    ohlc = np.array([[float(k[1]), float(k[2]), float(k[3]), float(k[4])]
                     for k in raw])
    return ohlc


def load_bear_market() -> np.ndarray:
    """BTC/USDT daily, Jan 2021 - Sep 2023 (data/btc_bear_2021_2023.json).

    Includes the full 2022 bear market (peak ~67.5k -> trough ~15.8k, -77%)
    plus the 2021 double-top and early-2023 recovery. Fetched via:
        GET api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d
            &startTime=1609459200000&limit=1000
    """
    return load_binance_klines(
        os.path.join(DATA_DIR, "btc_bear_2021_2023.json"))
