"""E41 — DEX-vol relative-strength rotation (Osmo S2).

    python scripts/fetch_dex_vol.py
    python e41_dex_rotation.py
    python -m unittest tests.test_dex_rotation
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np

from dynamic_grid import dex_rotation as dr

ROOT = os.path.dirname(os.path.abspath(__file__))
UNI = os.path.join(ROOT, "data", "universe", "spot_1d.json")
VOL_DIR = os.path.join(ROOT, "data", "dex_vol")
OUT = os.path.join(ROOT, "docs", "dex-rotation-e41.json")


def head(title):
    print("\n" + "=" * 94)
    print(title)
    print("=" * 94)


def tick(ok):
    return "PASS" if ok else "FAIL"


def load_vol(chain: str) -> list:
    path = os.path.join(VOL_DIR, f"{chain.lower()}_dex_vol_daily.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["totalDataChart"]


def build_panel(symbols_chains: tuple[tuple[str, str], ...]):
    with open(UNI, encoding="utf-8") as fh:
        universe = json.load(fh)
    symbols = tuple(s for s, _ in symbols_chains)
    dates, closes = dr.load_universe_closes(universe, symbols)
    vols = {}
    growths = {}
    for sym, chain in symbols_chains:
        vol = dr.load_vol_chart(load_vol(chain), dates)
        vols[sym] = vol
        growths[sym] = dr.growth(vol)
    # drop leading days where any growth is still unusable after warmup window
    return dates, closes, vols, growths


def evaluate_universe(symbols_chains, label, use_held_out_tail=True):
    dates, closes, vols, growths = build_panel(symbols_chains)
    n = len(dates)
    # BTC benchmark on same dates
    with open(UNI, encoding="utf-8") as fh:
        universe = json.load(fh)
    btc_map = {int(b[0]): float(b[4]) for b in universe["BTC"]}
    btc = np.array([btc_map.get(int(t), np.nan) for t in dates])
    # align: require finite vols for all names for growth lookback
    ok = np.ones(n, dtype=bool)
    for sym in closes:
        ok &= np.isfinite(vols[sym]) & (vols[sym] > 0)
        ok &= np.isfinite(closes[sym])
    # trim to contiguous True from first good after lookback
    first = None
    for i in range(dr.LOOKBACK, n):
        if ok[i]:
            first = i
            break
    if first is None:
        raise RuntimeError(f"no usable overlap for {label}")
    # keep from first - LOOKBACK so growth at `first` is defined; actually growth
    # needs lookback bars of vol — start index for trading is first + 0 but warmup
    # applies inside runner. Slice arrays from first - LOOKBACK.
    start_idx = first - dr.LOOKBACK
    dates = dates[start_idx:]
    closes = {s: closes[s][start_idx:] for s in closes}
    growths = {s: growths[s][start_idx:] for s in growths}
    btc = btc[start_idx:]
    n = len(dates)

    rng = np.random.default_rng(dr.SEED)
    arms = {
        "R_dex": dr.run_rotation(closes, growths, mode="dex"),
        "R_price": dr.run_rotation(closes, growths, mode="price"),
        "R_eq": dr.run_rotation(closes, growths, mode="eq"),
        "R_rand": dr.run_rotation(closes, growths, mode="rand", rng=rng),
    }
    # BTC buy&hold on same slice
    btc_closes = {"BTC": btc}
    # fake score unused
    arms["R_btc"] = dr.run_rotation(
        btc_closes, {"BTC": np.zeros(n)}, mode="eq")

    windows = dr.oos_windows(n) if use_held_out_tail else dr.oos_windows(
        n, held_out_tail=0)
    by_window = []
    for a, b in windows:
        row = {"start": a, "end": b}
        for name, res in arms.items():
            row[name] = dr.window_metrics(res, a, b)
        by_window.append(row)

    def mean_robust(name):
        vals = [w[name]["robust"] for w in by_window]
        return float(np.mean(vals)) if vals else None

    summary = {
        name: {
            "mean_robust": mean_robust(name),
            "mean_return": float(np.mean([w[name]["return"] for w in by_window])) if by_window else None,
            "mean_dd": float(np.mean([w[name]["maxDD"] for w in by_window])) if by_window else None,
            "full_sample": {
                "return": res.total_return,
                "maxDD": res.max_drawdown,
                "robust": res.robust,
                "n_rebalances": res.n_rebalances,
                "turnover": res.turnover,
            },
        }
        for name, res in arms.items()
    }

    held = None
    if use_held_out_tail and n > dr.HELD_OUT_TAIL + dr.WARMUP:
        a, b = n - dr.HELD_OUT_TAIL, n
        held = {name: dr.window_metrics(res, a, b) for name, res in arms.items()}

    return {
        "label": label,
        "n_bars": n,
        "t0": int(dates[0]),
        "t1": int(dates[-1]),
        "t0_iso": datetime.fromtimestamp(dates[0] / 1000, timezone.utc).date().isoformat(),
        "t1_iso": datetime.fromtimestamp(dates[-1] / 1000, timezone.utc).date().isoformat(),
        "n_windows": len(by_window),
        "windows": by_window,
        "summary": summary,
        "held_out_time": held,
        "n_rebalances_dex": arms["R_dex"].n_rebalances,
    }


def gates(primary):
    windows = primary["windows"]
    if not windows:
        return {g: {"pass": False, "note": "no windows"} for g in
                ("G1", "G2", "G3", "G4", "G5a", "G5b")}

    dex_r = [w["R_dex"]["robust"] for w in windows]
    price_r = [w["R_price"]["robust"] for w in windows]
    eq_r = [w["R_eq"]["robust"] for w in windows]
    mean_dex = float(np.mean(dex_r))
    mean_price = float(np.mean(price_r))
    mean_eq = float(np.mean(eq_r))
    win_frac = float(np.mean([d > p for d, p in zip(dex_r, price_r)]))

    g1 = mean_dex > mean_price and win_frac > 0.5
    g2 = mean_dex > 0
    g3 = mean_dex > mean_eq
    g4 = primary["n_rebalances_dex"] >= 30

    held = primary["held_out_time"]
    g5a = None
    if held is not None:
        g5a = held["R_dex"]["robust"] > held["R_price"]["robust"] and held["R_dex"]["robust"] > 0

    return {
        "G1": {"pass": g1, "mean_dex": mean_dex, "mean_price": mean_price,
               "win_frac": win_frac, "n_windows": len(windows)},
        "G2": {"pass": g2, "mean_dex": mean_dex},
        "G3": {"pass": g3, "mean_dex": mean_dex, "mean_eq": mean_eq},
        "G4": {"pass": g4, "n_rebalances": primary["n_rebalances_dex"]},
        "G5a": {"pass": g5a, "held": held},
        "G5b": {"pass": None, "note": "BNB expansion untouched until G1–G4 pass"},
    }


def main():
    for chain in ("Ethereum", "Solana", "BSC"):
        path = os.path.join(VOL_DIR, f"{chain.lower()}_dex_vol_daily.json")
        if not os.path.exists(path):
            raise SystemExit(f"missing {path}\nRun: python scripts/fetch_dex_vol.py")

    head("E41 DEX-vol rotation — ETH+SOL (criteria locked before code)")
    primary = evaluate_universe(dr.PRIMARY_MAP, "ETH+SOL")
    print(f"  bars={primary['n_bars']}  {primary['t0_iso']} -> {primary['t1_iso']}")
    print(f"  OOS windows (excl. held-out tail)={primary['n_windows']}")
    print(f"  R_dex rebalances (full sample)={primary['n_rebalances_dex']}")

    head("Mean robust on decision windows")
    for name in ("R_dex", "R_price", "R_eq", "R_rand", "R_btc"):
        s = primary["summary"][name]
        print(f"  {name:<8} mean_robust={s['mean_robust']:.4f}  "
              f"mean_ret={s['mean_return']:.4f}  mean_dd={s['mean_dd']:.4f}")

    g = gates(primary)
    head("Gates")
    for gid, info in g.items():
        status = "SKIP" if info["pass"] is None else tick(info["pass"])
        print(f"  {gid}: {status}  { {k: v for k, v in info.items() if k != 'pass'} }")

    # G5b only if G1-G4 pass
    bnb_result = None
    if all(g[x]["pass"] is True for x in ("G1", "G2", "G3", "G4")):
        head("G5b — expand universe with BNB/BSC")
        bnb_result = evaluate_universe(dr.HELD_ASSET_MAP, "ETH+SOL+BNB")
        # compare mean robust dex vs price on same decision windows definition
        dex_m = bnb_result["summary"]["R_dex"]["mean_robust"]
        price_m = bnb_result["summary"]["R_price"]["mean_robust"]
        g5b = dex_m is not None and price_m is not None and dex_m > price_m
        g["G5b"] = {"pass": g5b, "mean_dex": dex_m, "mean_price": price_m,
                    "n_windows": bnb_result["n_windows"]}
        print(f"  G5b: {tick(g5b)}  dex={dex_m:.4f} price={price_m:.4f}")
    else:
        print("\n  held-out BNB untouched (G1–G4 not all pass)")

    verdict = all(g[x]["pass"] is True for x in ("G1", "G2", "G3", "G4"))
    head("Verdict")
    print(f"  G1–G4 all pass: {verdict}")
    if g["G5a"]["pass"] is True and g["G5b"]["pass"] is True:
        print("  Full pass including held-outs")
    elif verdict:
        print("  Primary windows survived — check G5a/G5b")
    else:
        print("  Primary did NOT survive — held-out asset untouched")

    payload = {
        "criteria": "docs/E41_CRITERIA.md",
        "primary": primary,
        "bnb_expansion": bnb_result,
        "gates": g,
        "verdict_g1_g4": verdict,
        "held_out_asset_touched": bnb_result is not None,
    }

    def convert(obj):
        if isinstance(obj, dict):
            return {str(k): convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(x) for x in obj]
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        return obj

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(convert(payload), fh, indent=2)
    print(f"\n  wrote {OUT}")


if __name__ == "__main__":
    main()
