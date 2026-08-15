"""Fetch DefiLlama daily DEX volume charts for E40 chains."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dex_vol"
CHAINS = ("Ethereum", "Solana", "BSC")
UA = {"User-Agent": "GridTradingResearch/1.0"}


def get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"chains": {}}
    for chain in CHAINS:
        print(f"fetching DEX vol {chain}...")
        url = (
            f"https://api.llama.fi/overview/dexs/{chain}"
            "?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true"
        )
        payload = get(url)
        chart = payload.get("totalDataChart") or []
        path = OUT / f"{chain.lower()}_dex_vol_daily.json"
        path.write_text(
            json.dumps({"chain": chain, "totalDataChart": chart}, indent=2),
            encoding="utf-8",
        )
        manifest["chains"][chain] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "n": len(chart),
            "first": chart[0] if chart else None,
            "last": chart[-1] if chart else None,
        }
        print(f"  n={len(chart)}")
        time.sleep(0.4)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("wrote", OUT / "manifest.json")


if __name__ == "__main__":
    main()
