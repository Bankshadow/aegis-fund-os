"""E38 - which reading of the spec produces the reported 73 trades / 78% win?

Criteria declared in `docs/E38_CRITERIA.md` BEFORE the axes were wired. Run:

    python e38_identify.py

This IDENTIFIES a spec; it does not validate one. Arms are matched on the
structural fingerprint (trade count, win rate) and never on return - and the
return of every arm is printed regardless of how it looks.
"""

import json
import os

import numpy as np

from dynamic_grid import dsl_runtime as dsl
from e37_dsl import load, buy_hold, INITIAL, WARMUP, BARS_PER_YEAR

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "spec-identification-e38.json")

CLAIM_TRADES, CLAIM_WR = 73, 0.78
TOL_TRADES, TOL_WR = 0.25, 0.10

WINDOWS = (("W1_2024-07_2026-08", "BTCUSDT_4h_2y.json", "BTCUSDT_funding_2y.json"),
           ("W2_2022-06_2024-07", "BTCUSDT_4h_prev2y.json", None))


def head(title):
    print("\n" + "=" * 106)
    print(title)
    print("=" * 106)


def pct(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


def tick(ok):
    return "PASS" if ok else "FAIL"


def arm(close, high, low, funding, reentry, halt_mode):
    r = dsl.run(close, high, low, funding, warmup=WARMUP, initial=INITIAL,
                reentry=reentry, halt_mode=halt_mode)
    s = r.stats()
    years = len(r.equity) / BARS_PER_YEAR
    return {
        "reentry": reentry, "halt_mode": halt_mode,
        "trades": s["trades"], "win_rate": s["win_rate"],
        "profit_factor": s["profit_factor"],
        "total_return": r.total_return, "max_dd": r.max_drawdown,
        "robust": r.robust, "liquidations": r.liquidations, "ruined": r.ruined,
        "halted_at": r.halted_at, "daily_stops": r.daily_stops,
        "trades_per_month": s["trades"] / (years * 12) if years else 0.0,
        "exit_reasons": s["exit_reasons"],
    }


def matches(a):
    return (abs(a["trades"] - CLAIM_TRADES) <= TOL_TRADES * CLAIM_TRADES,
            abs(a["win_rate"] - CLAIM_WR) <= TOL_WR)


def main():
    head("E38 - spec identification | criteria docs/E38_CRITERIA.md")
    print(f"  fingerprint sought: {CLAIM_TRADES} trades (+-{TOL_TRADES:.0%} "
          f"= {round(CLAIM_TRADES*(1-TOL_TRADES))}-{round(CLAIM_TRADES*(1+TOL_TRADES))}), "
          f"win {CLAIM_WR:.0%} (+-{TOL_WR:.0%})")
    print("  arms are matched on the fingerprint ONLY; returns are reported for all")

    report = {}
    for name, price_file, funding_file in WINDOWS:
        close, high, low, funding = load(price_file, funding_file)
        bh = buy_hold(close)
        arms = [arm(close, high, low, funding, re, hm)
                for re in dsl.REENTRY for hm in dsl.HALT_MODES]

        head(f"{name}  |  buy&hold ROI {pct(bh['total_return'])} robust {bh['robust']:.2f}")
        print(f"  {'re-entry':<18}{'halt':<12}{'trades':>8}{'win%':>8}{'PF':>7}"
              f"{'ROI':>10}{'maxDD':>9}{'robust':>9}{'liq':>5}{'I1':>5}{'I2':>5}")
        for a in arms:
            i1, i2 = matches(a)
            pf = f"{a['profit_factor']:.2f}" if a["profit_factor"] else "  n/a"
            flag = "  <<" if (i1 and i2) else ""
            print(f"  {a['reentry']:<18}{a['halt_mode']:<12}{a['trades']:>8}"
                  f"{pct(a['win_rate'])}{pf:>7}{pct(a['total_return'])}"
                  f"{pct(a['max_dd'])}{a['robust']:>9.2f}{a['liquidations']:>5}"
                  f"{('ok' if i1 else '-'):>5}{('ok' if i2 else '-'):>5}{flag}")
        report[name] = {"buy_hold": bh, "arms": arms}

    # ---- identification is decided on W1 only, as declared -----------------
    head("Identification (decided on W1, per section 4.1)")
    w1 = report["W1_2024-07_2026-08"]["arms"]
    hits = [a for a in w1 if all(matches(a))]
    print(f"  arms clearing I1 and I2: {len(hits)}")
    for a in hits:
        print(f"    {a['reentry']} + halt={a['halt_mode']}: "
              f"{a['trades']} trades, win {pct(a['win_rate'])}, "
              f"ROI {pct(a['total_return'])}, robust {a['robust']:.2f}")
    i3 = len(hits) == 1
    print(f"  I3 exactly one arm identified -> {tick(i3)}")

    if not hits:
        print("\n  IDENTIFICATION FAILED: no arm reproduces both numbers.")
        print("  Per section 5, reporting the remaining gap and stopping - no arms added.")
        closest = min(w1, key=lambda a: abs(a["trades"] - CLAIM_TRADES))
        print(f"  closest on trade count: {closest['reentry']} + halt={closest['halt_mode']}"
              f" -> {closest['trades']} trades, win {pct(closest['win_rate'])}")

    # ---- performance of whatever was identified ---------------------------
    q = {}
    if hits:
        head("Performance of the identified arm(s) - reported as-is (section 4.2)")
        for a in hits:
            key = f"{a['reentry']}+{a['halt_mode']}"
            w2 = next(b for b in report["W2_2022-06_2024-07"]["arms"]
                      if b["reentry"] == a["reentry"] and b["halt_mode"] == a["halt_mode"])
            checks = {
                "Q1 robust>0 both": a["robust"] > 0 and w2["robust"] > 0,
                "Q2 beats B&H both": (a["robust"] > report["W1_2024-07_2026-08"]["buy_hold"]["robust"]
                                      and w2["robust"] > report["W2_2022-06_2024-07"]["buy_hold"]["robust"]),
                "Q3 no liq/ruin": a["liquidations"] == 0 and not a["ruined"]
                                  and w2["liquidations"] == 0 and not w2["ruined"],
            }
            q[key] = checks
            print(f"  {key}")
            print(f"    W1 ROI {pct(a['total_return'])} robust {a['robust']:.2f}   "
                  f"W2 ROI {pct(w2['total_return'])} robust {w2['robust']:.2f}")
            for label, ok in checks.items():
                print(f"    {label}: {tick(ok)}")
        print("\n  Q4 held-out not evaluated unless Q1-Q3 pass.")

    payload = {"experiment": "E38", "criteria": "docs/E38_CRITERIA.md",
               "claim": {"trades": CLAIM_TRADES, "win_rate": CLAIM_WR},
               "tolerance": {"trades": TOL_TRADES, "win_rate": TOL_WR},
               "windows": report,
               "identified": [f"{a['reentry']}+{a['halt_mode']}" for a in hits],
               "I3_unique": i3, "Q": q}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
