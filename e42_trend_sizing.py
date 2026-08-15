"""E42 - does the trend filter size better than it switches?

Criteria declared in `docs/E42_CRITERIA.md` BEFORE this file existed. Run:

    python e40_trend_sizing.py
    python -m unittest tests.test_trend_sizing

Read-only backtest. Long-only spot, no leverage, no short, no order path.
"""

import json
import os

import numpy as np

from dynamic_grid import cadence as cd
from dynamic_grid import trend_sizing as ts

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "trend-sizing-e42.json")

WARMUP = 252
OOS = 252
CADENCE = 21
INITIAL = 10_000.0


def head(title):
    print("\n" + "=" * 98)
    print(title)
    print("=" * 98)


def pct(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


def tick(ok):
    return "PASS" if ok else "FAIL"


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as fh:
        return np.array([float(b[4]) for b in json.load(fh)])


def windows(n):
    out, start = [], WARMUP
    while start + OOS <= n:
        out.append((start, start + OOS))
        start += OOS
    return out


def arms(close):
    """The five declared arms as target-weight series (NaN -> flat)."""
    a1 = ts.a1_binary(close)
    a1_exposure = float(np.nanmean(np.nan_to_num(a1, nan=0.0)[WARMUP:]))
    a2 = ts.a2_graded(close)
    built = {
        "A0_buy_hold": ts.a0_buy_hold(close),
        "A1_binary": a1,
        "A2_graded": a2,
        "A3_inverse_vol": ts.a3_inverse_vol(close),
        "A4_constant_mix": ts.a4_constant(close, a1_exposure),
        # Declared robustness arm: A2 rescaled on warm-up statistics only.
        "A2s_graded_matched": ts.rescale_from_warmup(a2, a1_exposure, WARMUP),
    }
    return {k: np.nan_to_num(v, nan=0.0) for k, v in built.items()}, a1_exposure


def evaluate(close, label):
    built, a1_exposure = arms(close)
    folds = windows(len(close))
    per_arm = {}
    for name, weights in built.items():
        rows = []
        for lo, hi in folds:
            run = cd.simulate(close[lo:hi], weights[lo:hi], CADENCE, initial=INITIAL)
            rows.append(cd.metrics(run))
        per_arm[name] = {
            "mean_robust": float(np.mean([r["robust"] for r in rows])),
            "median_robust": float(np.median([r["robust"] for r in rows])),
            "mean_return": float(np.mean([r["total_return"] for r in rows])),
            "mean_max_dd": float(np.mean([r["max_dd"] for r in rows])),
            "mean_exposure": float(np.mean([r["exposure"] for r in rows])),
            "trades_per_year": float(np.mean([r["trades_per_year"] for r in rows])),
            "windows": len(rows),
            "per_window_robust": [r["robust"] for r in rows],
        }
    return {"label": label, "folds": len(folds), "a1_exposure": a1_exposure,
            "arms": per_arm}


def show(block):
    head(f"{block['label']} - {block['folds']} non-overlapping OOS windows, "
         f"monthly cadence")
    print(f"  {'arm':<22}{'meanRobust':>12}{'medRobust':>11}{'meanRet':>10}"
          f"{'meanDD':>9}{'expo':>7}{'trd/y':>8}")
    for name, s in block["arms"].items():
        print(f"  {name:<22}{s['mean_robust']:>11.3f}{s['median_robust']:>11.3f}"
              f"{pct(s['mean_return'])}{pct(s['mean_max_dd'])}"
              f"{s['mean_exposure']:>7.2f}{s['trades_per_year']:>8.1f}")


def main():
    close = load("btc_daily_full.json")
    head(f"E42 - trend strength as SIZE, not as a switch | {len(close)} daily bars")
    print("  criteria docs/E42_CRITERIA.md | basis: E34 K6, the only positive")
    print("  mechanism finding in the ledger (binary filter beat constant-mix by 0.121)")

    # --- P1 first, before any backtest is read -----------------------------
    head("R1 / P1 - does trend STRENGTH order forward returns? (measured first)")
    strength = ts.a2_graded(close)
    p1 = ts.decile_forward_returns(close, strength, horizon=CADENCE, warmup=WARMUP)
    print(f"  n = {p1['n']} bars, forward horizon {CADENCE}")
    print(f"  {'decile':<9}{'mean fwd':>11}{'n':>7}")
    for k, (m, c) in enumerate(zip(p1["decile_means"], p1["decile_counts"]), start=1):
        bar = "#" * max(0, int(round(m * 200))) if not np.isnan(m) else ""
        print(f"  {k:<9}{pct(m, 2)}{c:>7}  {bar}")
    r1 = p1["spearman"] > 0 and p1["permutation_percentile"] >= 0.90
    print(f"\n  Spearman(decile, mean fwd) = {p1['spearman']:.3f}   "
          f"permutation percentile = {p1['permutation_percentile'] * 100:.1f}%   -> {tick(r1)}")

    if not r1:
        print("\n  R1 FAILED - strength adds nothing beyond direction.")
        print("  Per section 6, reporting and stopping. No arms tuned, held-out untouched.")
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump({"experiment": "E40", "criteria": "docs/E42_CRITERIA.md",
                       "p1": p1, "R1": False, "stopped_at": "R1"}, fh, indent=1,
                      default=float)
        print(f"\nwrote {OUT}")
        return 1

    # --- walk-forward -------------------------------------------------------
    btc = evaluate(close, "BTC")
    show(btc)

    a = btc["arms"]
    gap = abs(a["A2_graded"]["mean_exposure"] - a["A1_binary"]["mean_exposure"])
    print(f"\n  exposure gap A2 vs A1 = {gap * 100:.1f} pp "
          f"({'confounded, see A2s' if gap > 0.05 else 'within the declared 5pp band'})")

    head("Criteria")
    checks = {
        "R2 A2 > A1 (the question)": a["A2_graded"]["mean_robust"] > a["A1_binary"]["mean_robust"],
        "R3 A2 robust > 0": a["A2_graded"]["mean_robust"] > 0,
        "R4 A2 > A4 constant-mix": a["A2_graded"]["mean_robust"] > a["A4_constant_mix"]["mean_robust"],
        "R5 A2 > A3 inverse-vol": a["A2_graded"]["mean_robust"] > a["A3_inverse_vol"]["mean_robust"],
        "R6 A2 > A0 buy&hold": a["A2_graded"]["mean_robust"] > a["A0_buy_hold"]["mean_robust"],
    }
    for label, ok in checks.items():
        print(f"  {label:<34} {tick(ok)}")

    # K6 reproduction check, as the criteria's decision table demands
    k6 = a["A1_binary"]["mean_robust"] > a["A4_constant_mix"]["mean_robust"]
    print(f"\n  harness check - E34 K6 reproduces (A1 > A4): {tick(k6)} "
          f"({a['A1_binary']['mean_robust']:.3f} vs {a['A4_constant_mix']['mean_robust']:.3f})")

    passed = all(checks.values())
    print(f"\n  R2-R6: {tick(passed)}")
    held = {}
    if passed:
        head("R7 - held-out (touched only because R2-R6 passed)")
        for symbol, filename in (("ETH", "ETHUSDT_1d.json"), ("SOL", "SOLUSDT_1d.json")):
            other = load(filename)
            held[symbol] = evaluate(other, symbol)
            score = held[symbol]["arms"]["A2_graded"]["mean_robust"]
            print(f"  {symbol}: A2 mean robust {score:.3f}  {tick(score > 0)}")
    else:
        print("  R7 not evaluated: held-out stays untouched (section 7).")

    payload = {"experiment": "E40", "criteria": "docs/E42_CRITERIA.md",
               "config": {"warmup": WARMUP, "oos": OOS, "cadence": CADENCE,
                          "initial": INITIAL, "cost_per_side": cd.COST_PER_SIDE},
               "p1": p1, "btc": btc, "held_out": held,
               "checks": {"R1": r1, **checks}, "k6_reproduces": k6,
               "verdict": "PASS" if (r1 and passed) else "FAIL"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
