"""E46 - tune S003 one module at a time, and measure whether tuning adds anything.

Criteria declared in `docs/E46_CRITERIA.md` BEFORE this file existed. Run:

    python e46_s003_tune.py

The question is NOT "which variant is best". It is "does picking a variant on
past data beat the locked S003 on later data" - which this ledger has repeatedly
measured at roughly chance. Selection happens on IS only; OOS is read once.
"""

import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load, ASSETS

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "s003-tune-e46.json")

IS_FROM, SPLIT, OOS_TO = "2017-11-09", "2022-08-01", "2026-08-13"
BASE_FULL_PORTR = 72.81
FOLD_MONTHS = 6

VARIANTS = {
    "base": st.Params(),
    "A_sl_buffer_0.10": st.Params(sl_buffer=0.10),
    "A_sl_buffer_0.50": st.Params(sl_buffer=0.50),
    "B_max_risk_2.0": st.Params(max_risk_atr=2.0),
    "B_max_risk_4.0": st.Params(max_risk_atr=4.0),
    "C_be_none": st.Params(be_rule="none"),
    "C_be_after_tp1": st.Params(be_rule="after_tp1"),
    "D_tp3_2R": st.Params(tp3_mult=2.0),
    "D_tp3_4R": st.Params(tp3_mult=4.0),
    "E_min_stop_0.25": st.Params(min_stop_atr=0.25),
    "E_min_stop_1.0": st.Params(min_stop_atr=1.0),
}


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def fold_bounds():
    out, y, m = [], 2018, 2
    while f"{y}-{m:02d}-01" <= "2026-08-01":
        out.append(f"{y}-{m:02d}-01")
        m += FOLD_MONTHS
        if m > 12:
            m -= 12
            y += 1
    return out


BOUNDS = fold_bounds()


def run_variant(params):
    trades = []
    for symbol in ASSETS:
        dates, o, h, l, c, _ = load(symbol)
        trades.extend(st.run_symbol(symbol, dates, o, h, l, c, params=params).closed)
    return trades


def slice_stats(trades, lo, hi):
    sel = [t for t in trades if lo <= t.entry_date < hi]
    port = float(sum(t.pnl_r_net for t in sel))
    folds = []
    for k in range(len(BOUNDS) - 1):
        a, b = BOUNDS[k], BOUNDS[k + 1]
        if b <= lo or a >= hi:
            continue
        rs = [t.pnl_r_net for t in sel if a <= t.entry_date < b]
        if rs:
            folds.append(float(sum(rs)))
    return {"trades": len(sel), "portR": port,
            "minFold": float(min(folds)) if folds else 0.0,
            "folds": len(folds),
            "positive_folds": sum(1 for f in folds if f > 0)}


def main():
    head("E46 - tuning S003 one module at a time | criteria docs/E46_CRITERIA.md")
    print(f"  IS  {IS_FROM} -> {SPLIT}   (selection only)")
    print(f"  OOS {SPLIT} -> {OOS_TO}   (measured once, never used to select)")
    print(f"  {len(VARIANTS) - 1} variants, each changing exactly ONE module (spec section 7)")

    rows = {}
    for name, params in VARIANTS.items():
        trades = run_variant(params)
        rows[name] = {
            "full": slice_stats(trades, IS_FROM, OOS_TO),
            "IS": slice_stats(trades, IS_FROM, SPLIT),
            "OOS": slice_stats(trades, SPLIT, OOS_TO),
        }

    t5 = abs(rows["base"]["full"]["portR"] - BASE_FULL_PORTR) <= 0.1
    print(f"\n  T5 harness: base full portR {rows['base']['full']['portR']:+.2f} "
          f"vs E45 {BASE_FULL_PORTR:+.2f}  -> {tick(t5)}")
    if not t5:
        print("  STOP: harness does not reproduce E45 (criteria section 5).")
        return 1

    head("All 11 arms, both periods (reported in full, always)")
    print(f"  {'variant':<20}{'IS n':>6}{'IS portR':>10}{'OOS n':>7}{'OOS portR':>11}"
          f"{'OOS minFold':>13}{'OOS +folds':>12}")
    for name, r in rows.items():
        mark = "  <- base" if name == "base" else ""
        print(f"  {name:<20}{r['IS']['trades']:>6}{r['IS']['portR']:>10.2f}"
              f"{r['OOS']['trades']:>7}{r['OOS']['portR']:>11.2f}"
              f"{r['OOS']['minFold']:>13.2f}"
              f"{r['OOS']['positive_folds']:>7}/{r['OOS']['folds']}{mark}")

    # ---- selection: one rule, declared in advance -------------------------
    others = {k: v for k, v in rows.items() if k != "base"}
    picked = max(others, key=lambda k: others[k]["IS"]["portR"])
    base_oos, pick_oos = rows["base"]["OOS"], rows[picked]["OOS"]

    head("Selection (IS portR only) and the declared tests")
    print(f"  picked on IS: {picked}  (IS portR {rows[picked]['IS']['portR']:+.2f} "
          f"vs base {rows['base']['IS']['portR']:+.2f})")
    t1 = pick_oos["portR"] > base_oos["portR"]
    t2 = pick_oos["minFold"] > base_oos["minFold"]
    oos_values = [v["OOS"]["portR"] for k, v in others.items()]
    median_oos = float(np.median(oos_values))
    t3 = pick_oos["portR"] > median_oos
    beats = sum(1 for v in oos_values if v > base_oos["portR"])
    print(f"  T1 OOS portR   {pick_oos['portR']:+.2f} vs base {base_oos['portR']:+.2f}"
          f"   -> {tick(t1)}")
    print(f"  T2 OOS minFold {pick_oos['minFold']:+.2f} vs base {base_oos['minFold']:+.2f}"
          f"   -> {tick(t2)}")
    print(f"  T3 picked beats the variant median OOS ({median_oos:+.2f})   -> {tick(t3)}")
    print(f"  T4 variants beating base on OOS: {beats}/{len(oos_values)} "
          f"({beats / len(oos_values) * 100:.0f}%)")

    hit = t1 and t2
    head(f"VERDICT: {'HIT (tuning helped)' if hit else 'NO HIT - tuning did not help'}"
         f"   (promotion forbidden regardless)")
    if not hit:
        print("  Per the decision table: this confirms the E23-E25 / C7 lesson again.")

    payload = {"experiment": "E46", "criteria": "docs/E46_CRITERIA.md",
               "split": {"is_from": IS_FROM, "split": SPLIT, "oos_to": OOS_TO},
               "arms": rows, "picked_on_IS": picked,
               "checks": {"T1": t1, "T2": t2, "T3": t3, "T5": t5},
               "T4_beats_base_oos": f"{beats}/{len(oos_values)}",
               "median_oos_portR": median_oos,
               "verdict": "HIT" if hit else "NO_HIT",
               "run_count": len(VARIANTS) * 2}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
