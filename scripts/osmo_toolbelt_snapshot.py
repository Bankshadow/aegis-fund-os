"""Pull public snapshots for Osmo top-10 tool workflow (research only)."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "osmo-toolbelt-snapshot.json"


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "GridTradingResearch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


snap = {"asof": None, "sources": {}}

chains = sorted(get("https://api.llama.fi/v2/chains"), key=lambda x: -(x.get("tvl") or 0))[:15]
snap["sources"]["defillama_chains"] = [
    {"name": c.get("name"), "tvl": c.get("tvl")} for c in chains
]

fees = get(
    "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
)
protos = sorted(fees.get("protocols", []), key=lambda x: -(x.get("total24h") or 0))[:15]
snap["sources"]["defillama_fees_24h"] = [
    {
        "name": p.get("name"),
        "fees24h": p.get("total24h"),
        "category": p.get("category"),
        "symbol": p.get("symbol"),
    }
    for p in protos
]

dex = get(
    "https://api.llama.fi/overview/dexs?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
)
dprotos = sorted(dex.get("protocols", []), key=lambda x: -(x.get("total24h") or 0))[:12]
snap["sources"]["defillama_dex_vol_24h"] = [
    {
        "name": p.get("name"),
        "vol24h": p.get("total24h"),
        "chains": (p.get("chains") or [])[:3],
    }
    for p in dprotos
]

try:
    eth = get("https://api.llama.fi/v2/historicalChainTvl/Ethereum")
    if isinstance(eth, list) and len(eth) >= 30:
        last = eth[-1]["tvl"]
        prev30 = eth[-30]["tvl"]
        snap["sources"]["defillama_eth_tvl_30d_chg"] = {
            "last": last,
            "prev30": prev30,
            "chg_pct": (last / prev30 - 1) * 100 if prev30 else None,
        }
except Exception as e:
    snap["sources"]["defillama_eth_tvl_30d_chg"] = {"error": str(e)}

try:
    rev = get(
        "https://api.llama.fi/overview/fees?excludeTotalDataChart=true"
        "&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue"
    )
    rprotos = sorted(rev.get("protocols", []), key=lambda x: -(x.get("total24h") or 0))[:12]
    snap["sources"]["tokenterminal_proxy_revenue_24h"] = [
        {"name": p.get("name"), "rev24h": p.get("total24h"), "symbol": p.get("symbol")}
        for p in rprotos
    ]
except Exception as e:
    snap["sources"]["tokenterminal_proxy_revenue_24h"] = {"error": str(e)}

snap["sources"]["coinglass_proxy_binance"] = {
    "premium": get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"),
    "oi": get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"),
    "global_ls": get(
        "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
        "?symbol=BTCUSDT&period=1d&limit=7"
    ),
    "top_ls_acct": get(
        "https://fapi.binance.com/futures/data/topLongShortAccountRatio"
        "?symbol=BTCUSDT&period=1d&limit=7"
    ),
    "top_ls_pos": get(
        "https://fapi.binance.com/futures/data/topLongShortPositionRatio"
        "?symbol=BTCUSDT&period=1d&limit=7"
    ),
    "funding_recent": get(
        "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=21"
    ),
    "oi_hist": get(
        "https://fapi.binance.com/futures/data/openInterestHist"
        "?symbol=BTCUSDT&period=1d&limit=14"
    ),
    "taker_ls": get(
        "https://fapi.binance.com/futures/data/takerlongshortRatio"
        "?symbol=BTCUSDT&period=1d&limit=7"
    ),
}

sol_dex = [p for p in dex.get("protocols", []) if "Solana" in (p.get("chains") or [])]
sol_dex = sorted(sol_dex, key=lambda x: -(x.get("total24h") or 0))[:10]
snap["sources"]["birdeye_proxy_solana_dex"] = [
    {"name": p.get("name"), "vol24h": p.get("total24h")} for p in sol_dex
]

snap["sources"]["dune"] = {
    "status": "no_api_key",
    "note": "SQL proof layer blocked without Dune API key.",
}
snap["sources"]["nansen"] = {
    "status": "paywalled",
    "role": "smart-money labels — confirmation filter, not standalone entry",
}
snap["sources"]["arkham"] = {
    "status": "paywalled_or_login",
    "role": "entity fund flows — who is moving size",
}
snap["sources"]["bubblemaps"] = {
    "status": "interactive_ui",
    "role": "holder clustering — kill insider-concentrated tokens before size",
}
snap["sources"]["blockaid"] = {
    "status": "execution_guard",
    "role": "simulate before any onchain tx — security gate, not alpha",
}
snap["sources"]["tradingview"] = {
    "status": "charting",
    "role": "structure confirmation after mechanism filter",
}

try:
    trend = get("https://api.coingecko.com/api/v3/search/trending")
    snap["sources"]["narrative_proxy_coingecko_trending"] = [
        {
            "name": c["item"]["name"],
            "symbol": c["item"]["symbol"],
            "rank": c["item"].get("market_cap_rank"),
        }
        for c in trend.get("coins", [])[:10]
    ]
except Exception as e:
    snap["sources"]["narrative_proxy_coingecko_trending"] = {"error": str(e)}

wanted = (
    "Base",
    "Arbitrum",
    "Optimism",
    "Polygon",
    "Scroll",
    "Linea",
    "Blast",
    "Solana",
    "Sui",
    "Hyperliquid L1",
    "Ethereum",
    "BSC",
)
all_chains = get("https://api.llama.fi/v2/chains")
snap["sources"]["selected_chain_tvl"] = sorted(
    [
        {"name": c["name"], "tvl": c.get("tvl")}
        for c in all_chains
        if c.get("name") in wanted
    ],
    key=lambda x: -(x["tvl"] or 0),
)

snap["asof"] = datetime.now(timezone.utc).isoformat()
OUT.write_text(json.dumps(snap, indent=2), encoding="utf-8")
print("wrote", OUT)

print("\nTOP CHAINS")
for c in snap["sources"]["defillama_chains"][:8]:
    print(f"  {c['name']:16} ${(c['tvl'] or 0)/1e9:.2f}B")
print("\nTOP FEES")
for p in snap["sources"]["defillama_fees_24h"][:8]:
    name = (p["name"] or "?")[:24]
    print(f"  {name:24} ${(p['fees24h'] or 0)/1e6:.2f}M  {p.get('category')}")
print("\nTOP DEX")
for p in snap["sources"]["defillama_dex_vol_24h"][:8]:
    name = (p["name"] or "?")[:24]
    print(f"  {name:24} ${(p['vol24h'] or 0)/1e6:.1f}M")
prem = snap["sources"]["coinglass_proxy_binance"]["premium"]
print("\nBTC funding", prem.get("lastFundingRate"), "mark", prem.get("markPrice"))
ls = snap["sources"]["coinglass_proxy_binance"]["global_ls"][-1]
print("BTC global L/S", ls)
oi = snap["sources"]["coinglass_proxy_binance"]["oi_hist"][-1]
print("BTC OI value", oi.get("sumOpenInterestValue"))
