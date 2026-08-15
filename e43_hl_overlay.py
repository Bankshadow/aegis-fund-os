"""E43 — Hyperliquid fees as BTC risk-on overlay (Osmo S3).

    python scripts/fetch_hl_fees.py
    python e43_hl_overlay.py
    python -m unittest tests.test_hl_overlay
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np

from dynamic_grid import cadence as cd
from dynamic_grid import hl_overlay as hl

ROOT = os.path.dirname(os.path.abspath(__file__))
BTC = os.path.join(ROOT, "data", "btc_daily_full.json")
ETH = os.path.join(ROOT, "data", "universe", "spot_1d.json")
FEES = os.path.join(ROOT, "data", "hl_fees", "hyperliquid_daily_fees.json")
OUT = os.path.join(ROOT, "docs", "hl-overlay-e43.json")


def head(title):
    print("\n" + "=" * 94)
    print(title)
    print("=" * 94)


def tick(ok):
    return "PASS" if ok else "FAIL"


def load_btc_panel():
    with open(BTC, encoding="utf-8") as fh:
        raw = json.load(fh)
    dates = np.array([int(b[0]) for b in raw], dtype=np.int64)
    close = np.array([float(b[4]) for b in raw], dtype=float)
    with open(FEES, encoding="utf-8") as fh:
        chart = json.load(fh)["totalDataChart"]
    fees = hl.align_fees_to_dates(chart, dates)
    # keep from first finite fee
    idx = np.where(np.isfinite(fees))[0]
    if len(idx) == 0:
        raise RuntimeError("no overlapping HL fees")
    lo = int(idx[0])
    return dates[lo:], close[lo:], fees[lo:]


def load_eth_on_btc_dates(dates_ms: np.ndarray):
    with open(ETH, encoding="utf-8") as fh:
        uni = json.load(fh)
    eth_map = {int(b[0]): float(b[4]) for b in uni["ETH"]}
    close = np.array([eth_map.get(int(t), np.nan) for t in dates_ms], dtype=float)
    return close


def evaluate(dates, close, fees, label):
    built = hl.arms(close, fees)
    p = hl.fee_percentile(fees)
    p1 = hl.spearman_p_vs_forward(close, p)
    windows = hl.oos_windows(len(close))
    by_window = []
    for a, b in windows:
        row = {"start": int(a), "end": int(b)}
        for name, weights in built.items():
            w = np.nan_to_num(weights[a:b], nan=0.0)
            run = cd.simulate(close[a:b], w, hl.CADENCE)
            m = cd.metrics(run)
            row[name] = {
                "return": m["total_return"],
                "maxDD": m["max_dd"],
                "robust": m["robust"],
                "trades": m["trades"],
                "exposure": m["exposure"],
            }
        by_window.append(row)

    def mean_field(name, field):
        return float(np.mean([w[name][field] for w in by_window])) if by_window else None

    summary = {
        name: {
            "mean_robust": mean_field(name, "robust"),
            "mean_return": mean_field(name, "return"),
            "mean_dd": mean_field(name, "maxDD"),
            "mean_exposure": mean_field(name, "exposure"),
        }
        for name in built
    }

    held = None
    n = len(close)
    if n > hl.HELD_OUT + hl.WARMUP:
        a, b = n - hl.HELD_OUT, n
        held = {}
        for name, weights in built.items():
            w = np.nan_to_num(weights[a:b], nan=0.0)
            run = cd.simulate(close[a:b], w, hl.CADENCE)
            m = cd.metrics(run)
            held[name] = {
                "return": m["total_return"],
                "maxDD": m["max_dd"],
                "robust": m["robust"],
                "trades": m["trades"],
            }

    total_trades = 0
    for name, weights in built.items():
        if name == "H_size":
            w = np.nan_to_num(weights, nan=0.0)
            total_trades = cd.simulate(close, w, hl.CADENCE)["trades"]

    return {
        "label": label,
        "n_bars": len(close),
        "t0_iso": datetime.fromtimestamp(int(dates[0]) / 1000, timezone.utc).date().isoformat(),
        "t1_iso": datetime.fromtimestamp(int(dates[-1]) / 1000, timezone.utc).date().isoformat(),
        "p1": p1,
        "n_windows": len(by_window),
        "windows": by_window,
        "summary": summary,
        "held_out_time": held,
        "h_size_trades_full": int(total_trades),
    }


def gates(primary):
    windows = primary["windows"]
    if len(windows) < 3:
        base = {g: {"pass": False, "note": "fewer than 3 windows"}
                for g in ("G1", "G2", "G3", "G4", "G5a", "G5b")}
        base["P1"] = {"pass": None, "detail": primary["p1"]}
        return base

    hs = [w["H_size"]["robust"] for w in windows]
    t1 = [w["T1_trend"]["robust"] for w in windows]
    cv = [w["C_vol"]["robust"] for w in windows]
    ho = [w["H_only"]["robust"] for w in windows]
    mean_hs, mean_t1 = float(np.mean(hs)), float(np.mean(t1))
    mean_cv, mean_ho = float(np.mean(cv)), float(np.mean(ho))
    win_frac = float(np.mean([a > b for a, b in zip(hs, t1)]))

    g1 = mean_hs > mean_t1 and win_frac > 0.5
    g2 = mean_hs > 0
    g3 = mean_hs > mean_cv and mean_hs > mean_ho
    g4 = len(windows) >= 3 and primary["h_size_trades_full"] >= 10

    held = primary["held_out_time"]
    g5a = None
    if held is not None:
        g5a = (held["H_size"]["robust"] > held["T1_trend"]["robust"]
               and held["H_size"]["robust"] > 0)

    p1 = primary["p1"]
    p1_note = {
        "spearman": p1.get("spearman"),
        "permutation_percentile": p1.get("permutation_percentile"),
        "n": p1.get("n"),
        "warn_negative": (p1.get("spearman") is not None and p1["spearman"] < 0),
    }

    return {
        "P1": {"pass": None, "detail": p1_note},
        "G1": {"pass": g1, "mean_h_size": mean_hs, "mean_t1": mean_t1,
               "win_frac": win_frac, "n_windows": len(windows)},
        "G2": {"pass": g2, "mean_h_size": mean_hs},
        "G3": {"pass": g3, "mean_h_size": mean_hs, "mean_c_vol": mean_cv,
               "mean_h_only": mean_ho},
        "G4": {"pass": g4, "n_windows": len(windows),
               "trades": primary["h_size_trades_full"]},
        "G5a": {"pass": g5a, "held": held},
        "G5b": {"pass": None, "note": "ETH untouched until G1-G4 pass"},
    }


def main():
    if not os.path.exists(FEES):
        raise SystemExit(f"missing {FEES}\nRun: python scripts/fetch_hl_fees.py")

    dates, close, fees = load_btc_panel()
    head("E43 HL fee overlay on BTC (criteria locked before code)")
    primary = evaluate(dates, close, fees, "BTC")
    print(f"  bars={primary['n_bars']}  {primary['t0_iso']} -> {primary['t1_iso']}")
    print(f"  windows={primary['n_windows']}  H_size trades={primary['h_size_trades_full']}")
    print(f"  P1 spearman={primary['p1'].get('spearman')}  "
          f"perm%={primary['p1'].get('permutation_percentile')}")

    head("Mean robust on decision windows")
    for name, s in primary["summary"].items():
        print(f"  {name:<12} robust={s['mean_robust']:.4f}  "
              f"ret={s['mean_return']:.4f}  dd={s['mean_dd']:.4f}  "
              f"exp={s['mean_exposure']:.3f}")

    g = gates(primary)
    head("Gates")
    for gid, info in g.items():
        status = "SKIP" if info["pass"] is None else tick(info["pass"])
        print(f"  {gid}: {status}  { {k: v for k, v in info.items() if k != 'pass'} }")

    eth_result = None
    if all(g[x]["pass"] is True for x in ("G1", "G2", "G3", "G4")):
        head("G5b — same overlay on ETH")
        eth_close = load_eth_on_btc_dates(dates)
        if np.isfinite(eth_close).sum() < len(dates) * 0.9:
            g["G5b"] = {"pass": False, "note": "ETH alignment incomplete"}
        else:
            eth_result = evaluate(dates, eth_close, fees, "ETH")
            # compare mean robust on eth windows
            hs = eth_result["summary"]["H_size"]["mean_robust"]
            t1 = eth_result["summary"]["T1_trend"]["mean_robust"]
            g5b = hs is not None and t1 is not None and hs > t1
            g["G5b"] = {"pass": g5b, "mean_h_size": hs, "mean_t1": t1}
            print(f"  G5b: {tick(g5b)}  H_size={hs:.4f} T1={t1:.4f}")
    else:
        print("\n  held-out ETH untouched (G1-G4 not all pass)")

    verdict = all(g[x]["pass"] is True for x in ("G1", "G2", "G3", "G4"))
    head("Verdict")
    print(f"  G1-G4 all pass: {verdict}")

    payload = {
        "criteria": "docs/E43_CRITERIA.md",
        "primary": primary,
        "eth_held_out": eth_result,
        "gates": g,
        "verdict_g1_g4": verdict,
        "held_out_asset_touched": eth_result is not None,
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
