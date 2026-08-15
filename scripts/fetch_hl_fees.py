"""Fetch Hyperliquid daily fees from DefiLlama for E43."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "hl_fees"
UA = {"User-Agent": "GridTradingResearch/1.0"}


def get(url: str):
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(last)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    url = "https://api.llama.fi/summary/fees/hyperliquid?dataType=dailyFees"
    payload = get(url)
    chart = payload.get("totalDataChart") or []
    path = OUT / "hyperliquid_daily_fees.json"
    path.write_text(
        json.dumps(
            {
                "name": payload.get("name"),
                "source": url,
                "totalDataChart": chart,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {path} n={len(chart)} first={chart[0] if chart else None} last={chart[-1] if chart else None}")


if __name__ == "__main__":
    main()
