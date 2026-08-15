"""Fetch Binance public crowding panel for E39 (L/S + OI + funding + 1h klines).

Criteria: docs/E39_CRITERIA.md — only the latest ~30 days are available.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "crowding"
UA = {"User-Agent": "GridTradingResearch/1.0"}


def get(url: str, retries: int = 3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001 — network probe
            last = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def fetch_symbol(symbol: str) -> dict:
    base = "https://fapi.binance.com"
    ls = get(
        f"{base}/futures/data/globalLongShortAccountRatio"
        f"?symbol={symbol}&period=1h&limit=500"
    )
    oi = get(
        f"{base}/futures/data/openInterestHist"
        f"?symbol={symbol}&period=1h&limit=500"
    )
    t0 = min(ls[0]["timestamp"], oi[0]["timestamp"])
    t1 = max(ls[-1]["timestamp"], oi[-1]["timestamp"])
    # funding over the same calendar window (+buffer)
    funding = get(
        f"{base}/fapi/v1/fundingRate?symbol={symbol}&startTime={t0 - 8 * 3600 * 1000}"
        f"&endTime={t1 + 8 * 3600 * 1000}&limit=1000"
    )
    # 1h klines: Binance returns max 1500; 30d*24=720
    klines = get(
        f"{base}/fapi/v1/klines?symbol={symbol}&interval=1h"
        f"&startTime={t0}&endTime={t1}&limit=1500"
    )
    return {
        "symbol": symbol,
        "long_short": ls,
        "open_interest": oi,
        "funding": funding,
        "klines_1h": klines,
        "t0": t0,
        "t1": t1,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"symbols": {}}
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        print(f"fetching {symbol}...")
        payload = fetch_symbol(symbol)
        path = OUT / f"{symbol.lower()}_1h_panel.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        meta["symbols"][symbol] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "n_ls": len(payload["long_short"]),
            "n_oi": len(payload["open_interest"]),
            "n_funding": len(payload["funding"]),
            "n_klines": len(payload["klines_1h"]),
            "t0": payload["t0"],
            "t1": payload["t1"],
        }
        print(
            f"  ls={meta['symbols'][symbol]['n_ls']} "
            f"oi={meta['symbols'][symbol]['n_oi']} "
            f"fund={meta['symbols'][symbol]['n_funding']} "
            f"klines={meta['symbols'][symbol]['n_klines']}"
        )
        time.sleep(0.3)
    (OUT / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("wrote", OUT / "manifest.json")


if __name__ == "__main__":
    main()
