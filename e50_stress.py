"""E50 - does the S003 edge survive a pessimistic fill model and real costs?

Criteria declared in `docs/E50_CRITERIA.md` BEFORE this file existed. Run:

    python e50_stress.py

Nothing here can improve a result. The spec counts TP3 when one bar touches both
TP3 and the stop, and charges 0.05% a side with no slippage; both are the kindest
assumptions available. This removes them and reports where the edge dies.
"""

import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load, ASSETS
from e47_sizing_overlay import cagr, INITIAL, IS_FROM, SPLIT, OOS_TO

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "stress-e50.json")

INTRABARS = ("tp_first", "sl_first")
FEES = (0.0005, 0.0010, 0.0015, 0.0025)
BASE_PORTR = 72.81
BH_OOS_CAGR, BH_OOS_DD = 0.104, 0.741      # buy & hold 50/50, same OOS window
SURVIVAL_FEE, SURVIVAL_RISK = 0.0015, 0.01


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def trades_for(intrabar, fee):
    out = []
    for symbol in ASSETS:
        dates, o, h, l, c, _ = load(symbol)
        out.extend(st.run_symbol(symbol, dates, o, h, l, c, intrabar=intrabar,
                                 params=st.Params(fee_side=fee)).closed)
    out.sort(key=lambda t: (t.exit_date, t.entry_date))
    return out


def equity(trades, risk, lo, hi):
    sel = [t for t in trades if lo <= t.entry_date < hi]
    if not sel:
        return INITIAL, 0.0, 0
    events = sorted([(t.entry_date, 0, t) for t in sel]
                    + [(t.exit_date, 1, t) for t in sel],
                    key=lambda x: (x[0], x[1]))
    cash, risked, curve = INITIAL, {}, [INITIAL]
    for _, kind, t in events:
        if kind == 0:
            risked[id(t)] = cash * risk
        else:
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            curve.append(cash)
            if cash <= 0:
                return 0.0, 1.0, len(sel)
    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return cash, float(((peak - arr) / peak).max()), len(sel)


def port_r(trades, lo, hi):
    return float(sum(t.pnl_r_net for t in trades if lo <= t.entry_date < hi))


def main():
    head("E50 - pessimistic fills x real costs | criteria docs/E50_CRITERIA.md")

    cache = {(ib, f): trades_for(ib, f) for ib in INTRABARS for f in FEES}

    # ---- Y1 harness ------------------------------------------------------
    base = cache[("tp_first", 0.0005)]
    pr = port_r(base, IS_FROM, OOS_TO)
    f6, dd6, _ = equity(base, 0.06, IS_FROM, OOS_TO)
    c6 = cagr(f6, base, IS_FROM, OOS_TO)
    y1 = (abs(pr - BASE_PORTR) <= 0.1 and abs(dd6 - 0.721) <= 0.005
          and abs(c6 - 0.372) <= 0.005)
    print(f"  Y1 harness: portR {pr:+.2f} (E45 +72.81) | 6% -> DD {dd6:.1%} / "
          f"CAGR {c6:+.1%}   -> {tick(y1)}")
    if not y1:
        print("  STOP per criteria section 3.")
        return 1

    rows = {}
    head("Y2/Y5 - portR by fill model and cost (portR does not depend on trade size)")
    print(f"  {'fee/side':>9}{'tp_first IS':>13}{'tp_first OOS':>14}"
          f"{'sl_first IS':>13}{'sl_first OOS':>14}{'OOS gap':>10}")
    for fee in FEES:
        cells = {}
        for ib in INTRABARS:
            tr = cache[(ib, fee)]
            cells[ib] = {"IS": port_r(tr, IS_FROM, SPLIT),
                         "OOS": port_r(tr, SPLIT, OOS_TO),
                         "full": port_r(tr, IS_FROM, OOS_TO),
                         "n": len(tr)}
        gap = cells["tp_first"]["OOS"] - cells["sl_first"]["OOS"]
        rows[f"{fee:.4f}"] = {"fee": fee, "arms": cells, "oos_gap": gap}
        print(f"  {fee * 100:>8.2f}%{cells['tp_first']['IS']:>13.2f}"
              f"{cells['tp_first']['OOS']:>14.2f}{cells['sl_first']['IS']:>13.2f}"
              f"{cells['sl_first']['OOS']:>14.2f}{gap:>10.2f}")

    y2 = rows["0.0005"]["arms"]["sl_first"]["OOS"] > 0
    print(f"\n  Y2 sl_first @0.05% OOS portR "
          f"{rows['0.0005']['arms']['sl_first']['OOS']:+.2f} > 0   -> {tick(y2)}")

    head("Equity outcomes at the usable risk levels (1% and 2%)")
    print(f"  {'model':<10}{'fee':>7}{'risk':>7}{'OOS CAGR':>11}{'OOS DD':>9}"
          f"{'$10k ->':>11}{'full CAGR':>11}{'full DD':>10}")
    eq = {}
    for ib in INTRABARS:
        for fee in FEES:
            tr = cache[(ib, fee)]
            for risk in (0.01, 0.02):
                fo, ddo, _ = equity(tr, risk, SPLIT, OOS_TO)
                ff, ddf, _ = equity(tr, risk, IS_FROM, OOS_TO)
                rec = {"oos_cagr": cagr(fo, tr, SPLIT, OOS_TO), "oos_dd": ddo,
                       "oos_final": fo, "full_cagr": cagr(ff, tr, IS_FROM, OOS_TO),
                       "full_dd": ddf}
                eq[f"{ib}|{fee:.4f}|{risk:.2f}"] = rec
                print(f"  {ib:<10}{fee * 100:>6.2f}%{risk * 100:>6.1f}%"
                      f"{rec['oos_cagr']:>+11.1%}{ddo:>9.1%}{fo:>11,.0f}"
                      f"{rec['full_cagr']:>+11.1%}{ddf:>10.1%}")

    # ---- Y3 survival -----------------------------------------------------
    s = eq[f"sl_first|{SURVIVAL_FEE:.4f}|{SURVIVAL_RISK:.2f}"]
    y3 = s["oos_cagr"] > BH_OOS_CAGR and s["oos_dd"] < BH_OOS_DD
    head("Y3 - survival test: sl_first @0.15%/side, 1% risk, vs buy & hold on OOS")
    print(f"  S003       CAGR {s['oos_cagr']:+.1%}   maxDD {s['oos_dd']:.1%}")
    print(f"  buy & hold CAGR {BH_OOS_CAGR:+.1%}   maxDD {BH_OOS_DD:.1%}")
    print(f"  must beat both   -> {tick(y3)}")

    # ---- Y4 breakeven cost ----------------------------------------------
    head("Y4 - where the edge dies: fee/side at which full-history portR reaches 0")
    be = {}
    for ib in INTRABARS:
        lo_f, hi_f = 0.0, 0.05
        for _ in range(60):
            mid = (lo_f + hi_f) / 2
            if port_r(trades_for(ib, mid), IS_FROM, OOS_TO) > 0:
                lo_f = mid
            else:
                hi_f = mid
        be[ib] = (lo_f + hi_f) / 2
        print(f"  {ib:<10} breakeven {be[ib] * 100:.3f}%/side "
              f"({be[ib] * 200:.3f}% round trip)")
    print(f"  headroom over the 0.15% survival test: "
          f"{be['sl_first'] / SURVIVAL_FEE:.1f}x (sl_first)")

    # The criteria's decision table is three-way, not a single boolean. Collapsing
    # it to `y1 and y2 and y3` printed "E51 cancelled" on a Y3-only failure, which
    # the declared table assigns to Y2 alone. The table governs.
    survived = y1 and y2 and y3
    if survived:
        verdict, note = "SURVIVES", "proceed to E51"
    elif y2:
        verdict, note = ("EDGE REAL BUT THIN",
                         "Y3 failed, Y2 held -> E51 proceeds, reported under the cost ceiling")
    else:
        verdict, note = "FAILS", "Y2 failed -> E51 is cancelled"
    head(f"VERDICT: {verdict}  ({note})")

    payload = {"experiment": "E50", "criteria": "docs/E50_CRITERIA.md",
               "portR": rows, "equity": eq, "breakeven_fee_side": be,
               "checks": {"Y1": y1, "Y2": y2, "Y3": y3},
               "verdict": verdict,
               "run_count": len(INTRABARS) * len(FEES)}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0 if y2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
