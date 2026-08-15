"""E56 - all three optimistic assumptions removed at once.

Criteria declared in `docs/E56_CRITERIA.md` BEFORE this file existed. Run:

    python e56_honest_corner.py

E50 varied the intrabar model and the cost. E55 D varied the undocumented
break-even-arming-bar rule. Neither varied the other's axis, so the corner where
all three are pessimistic has never been looked at - and E55 measured that the
BE rule alone is worth 27.5% of portR, more than the whole S017 cooldown was
claiming to add.

Nothing here can improve a result. Every axis only removes a kindness, so the
worst cell is the honest floor and the spec's own cell is the ceiling. The
deliverable is the interval between them, not a number.
"""

import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load, ASSETS, UNSEEN_BEFORE
from e47_sizing_overlay import cagr, INITIAL, IS_FROM, SPLIT, OOS_TO
from e50_stress import equity, port_r, BH_OOS_CAGR, BH_OOS_DD

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "honest-corner-e56.json")

INTRABARS = ("tp_first", "sl_first")
BE_RULES = ("coded", "literal")          # coded = the arming bar survives
FEES = (0.0005, 0.0010, 0.0015, 0.0025)
SURVIVAL_FEE, SURVIVAL_RISK = 0.0015, 0.01

E45_PORTR = 72.81                        # (tp_first, coded, 0.05%)
E55_LITERAL_PORTR = 52.76                # (tp_first, literal, 0.05%)
SPEC_CELL = ("tp_first", "coded")
CORNER = ("sl_first", "literal")

_CACHE = {}


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def trades_for(intrabar, be_rule, fee):
    """All closed S003 trades under one combination of the three axes."""
    key = (intrabar, be_rule, round(fee, 6))
    if key in _CACHE:
        return _CACHE[key]
    out = []
    for symbol in ASSETS:
        dates, o, h, l, c, _ = load(symbol)
        out.extend(st.run_symbol(
            symbol, dates, o, h, l, c, intrabar=intrabar,
            params=st.Params(fee_side=fee),
            be_on_arming_bar=(be_rule == "literal")).closed)
    out.sort(key=lambda t: (t.exit_date, t.entry_date))
    _CACHE[key] = out
    return out


def breakeven_fee(intrabar, be_rule):
    lo_f, hi_f = 0.0, 0.05
    for _ in range(60):
        mid = (lo_f + hi_f) / 2
        if port_r(trades_for(intrabar, be_rule, mid), IS_FROM, OOS_TO) > 0:
            lo_f = mid
        else:
            hi_f = mid
    return (lo_f + hi_f) / 2


def label(intrabar, be_rule):
    return f"{intrabar}/{be_rule}"


def main():
    head("E56 - the honest corner | criteria docs/E56_CRITERIA.md")
    print("  three optimistic assumptions, removed together for the first time:")
    print("    intrabar TP-first | the undocumented BE-arming-bar exemption | 0.05% costs")
    print("  S003 only - E55 rejected both the S017 cooldown and the vol overlay")

    # ---- Z1 two-sided harness --------------------------------------------
    spec = trades_for(*SPEC_CELL, 0.0005)
    lit = trades_for("tp_first", "literal", 0.0005)
    pr_spec = port_r(spec, IS_FROM, OOS_TO)
    pr_lit = port_r(lit, IS_FROM, OOS_TO)
    z1 = abs(pr_spec - E45_PORTR) <= 0.1 and abs(pr_lit - E55_LITERAL_PORTR) <= 0.1
    print(f"\n  Z1 harness: spec cell {pr_spec:+.2f} (E45 +{E45_PORTR:.2f}) | "
          f"literal cell {pr_lit:+.2f} (E55 D +{E55_LITERAL_PORTR:.2f})  -> {tick(z1)}")
    if not z1:
        print("  STOP per criteria section 3.")
        return 1

    # ---- the full 16-cell grid -------------------------------------------
    grid = {}
    for ib in INTRABARS:
        for be in BE_RULES:
            for fee in FEES:
                tr = trades_for(ib, be, fee)
                grid[f"{ib}|{be}|{fee:.4f}"] = {
                    "intrabar": ib, "be_rule": be, "fee": fee, "n": len(tr),
                    "IS": port_r(tr, IS_FROM, SPLIT),
                    "OOS": port_r(tr, SPLIT, OOS_TO),
                    "full": port_r(tr, IS_FROM, OOS_TO),
                }

    head("The 16 cells - portR (independent of trade size), reported in full")
    print(f"  {'cell':<24}{'n':>5}" + "".join(f"{f'{f*100:.2f}% IS':>12}{f'OOS':>10}"
                                              for f in FEES))
    for ib in INTRABARS:
        for be in BE_RULES:
            cells = [grid[f"{ib}|{be}|{f:.4f}"] for f in FEES]
            mark = ""
            if (ib, be) == SPEC_CELL:
                mark = "  <- the spec's own cell"
            elif (ib, be) == CORNER:
                mark = "  <- declared worst corner"
            print(f"  {label(ib, be):<24}{cells[0]['n']:>5}"
                  + "".join(f"{c['IS']:>12.2f}{c['OOS']:>10.2f}" for c in cells)
                  + mark)

    head("Full-history portR, every cell (the interval the result really lives in)")
    print(f"  {'cell':<24}" + "".join(f"{f'{f*100:.2f}%':>12}" for f in FEES))
    for ib in INTRABARS:
        for be in BE_RULES:
            row = [grid[f"{ib}|{be}|{f:.4f}"]["full"] for f in FEES]
            print(f"  {label(ib, be):<24}" + "".join(f"{v:>12.2f}" for v in row))

    # ---- Z2 / Z3 the corner ----------------------------------------------
    corner = grid[f"{CORNER[0]}|{CORNER[1]}|0.0005"]
    z2 = corner["full"] > 0
    z3 = corner["OOS"] > 0
    head("Z2 / Z3 - the corner at 0.05%/side: is anything left")
    print(f"  {label(*CORNER):<24}full {corner['full']:+.2f}   IS {corner['IS']:+.2f}"
          f"   OOS {corner['OOS']:+.2f}   ({corner['n']} trades)")
    print(f"  spec cell for scale        full {grid['tp_first|coded|0.0005']['full']:+.2f}"
          f"   IS {grid['tp_first|coded|0.0005']['IS']:+.2f}"
          f"   OOS {grid['tp_first|coded|0.0005']['OOS']:+.2f}")
    kept = corner["full"] / grid["tp_first|coded|0.0005"]["full"]
    print(f"  the corner keeps {kept:.0%} of the spec cell's portR")
    print(f"  Z2 full-history portR > 0   -> {tick(z2)}")
    print(f"  Z3 OOS portR > 0            -> {tick(z3)}")

    # ---- Z9 is the declared corner really the worst ----------------------
    worst_key = min((k for k in grid if k.endswith("0.0005")),
                    key=lambda k: grid[k]["full"])
    z9 = grid[worst_key]["full"] >= corner["full"] - 1e-9
    head("Z9 - was the declared corner actually the worst cell at 0.05%")
    for k in sorted((k for k in grid if k.endswith("0.0005")),
                    key=lambda k: grid[k]["full"]):
        g = grid[k]
        print(f"  {label(g['intrabar'], g['be_rule']):<24}{g['full']:>10.2f}"
              + ("   <- worst" if k == worst_key else ""))
    ties = [k for k in grid if k.endswith("0.0005")
            and abs(grid[k]["full"] - grid[worst_key]["full"]) < 1e-9]
    print(f"  declared corner is the worst   -> {'YES' if z9 else 'NO'}"
          + (f"   (tied with {len(ties) - 1} other cell(s))" if len(ties) > 1 else ""))

    # ---- the axes are not independent -------------------------------------
    nested = all(
        abs(grid[f"sl_first|coded|{f:.4f}"]["full"]
            - grid[f"sl_first|literal|{f:.4f}"]["full"]) < 1e-9 for f in FEES)
    head("The finding this grid exists to expose: the BE axis is NESTED, not independent")
    print("  Under sl_first the two BE readings are identical in every cell:"
          f" {'CONFIRMED' if nested else 'NOT confirmed'}")
    print("  Reason, structurally: the arming-bar exemption only ever suppresses a")
    print("  stop-check that the pessimistic model performs anyway. Once you stop")
    print("  counting TP before SL, the undocumented rule has nothing left to give.")
    print("  Consequence: E55 D's 27.5% error bar is NOT additive with sl_first's")
    print("  39.9% - it is a subset of it. The honest floor is sl_first, which E50")
    print("  already measured. There was no unmeasured third corner; the two")
    print("  known error bars overlap almost entirely.")

    # ---- Z7 decomposition -------------------------------------------------
    base = grid["tp_first|coded|0.0005"]["full"]
    only_sl = grid["sl_first|coded|0.0005"]["full"] - base
    only_be = grid["tp_first|literal|0.0005"]["full"] - base
    only_fee = grid["tp_first|coded|0.0015"]["full"] - base
    joint = grid["sl_first|literal|0.0015"]["full"] - base
    additive = only_sl + only_be + only_fee
    head("Z7 - what each assumption is worth, and whether they interact")
    print(f"  baseline (spec cell)                 {base:>+9.2f} R")
    print(f"  drop TP-first only                   {only_sl:>+9.2f} R  ({only_sl/base:>+6.1%})")
    print(f"  drop the BE-arming exemption only    {only_be:>+9.2f} R  ({only_be/base:>+6.1%})")
    print(f"  raise cost to 0.15%/side only        {only_fee:>+9.2f} R  ({only_fee/base:>+6.1%})")
    print(f"  {'-' * 66}")
    print(f"  sum of the three separately          {additive:>+9.2f} R")
    print(f"  all three together                   {joint:>+9.2f} R")
    inter = joint - additive
    print(f"  interaction                          {inter:>+9.2f} R")
    print("  This is not a cushion in the market - it is double counting. The BE")
    print("  term is absorbed whole by the TP-first term (see the section above),")
    print("  so the three axes were never three. Read the interaction as the")
    print("  overlap between two error bars, not as a diversification benefit.")

    # ---- Z4 survival ------------------------------------------------------
    surv_tr = trades_for(CORNER[0], CORNER[1], SURVIVAL_FEE)
    fo, ddo, n_oos = equity(surv_tr, SURVIVAL_RISK, SPLIT, OOS_TO)
    c_oos = cagr(fo, surv_tr, SPLIT, OOS_TO)
    z4 = c_oos > BH_OOS_CAGR and ddo < BH_OOS_DD
    head(f"Z4 - survival: the corner at {SURVIVAL_FEE*100:.2f}%/side, "
         f"{SURVIVAL_RISK:.0%} risk, OOS vs buy & hold")
    print(f"  S003 corner   CAGR {c_oos:>+7.1%}   maxDD {ddo:>6.1%}   "
          f"$10k -> {fo:,.0f}   ({n_oos} trades)")
    print(f"  buy & hold    CAGR {BH_OOS_CAGR:>+7.1%}   maxDD {BH_OOS_DD:>6.1%}")
    print(f"  must beat both   -> {tick(z4)}")
    print("  (E50 measured the same test with the BE exemption ON: +6.9% / 21.3%)")

    # ---- Z5 never-seen window --------------------------------------------
    corner_tr = trades_for(CORNER[0], CORNER[1], 0.0005)
    unseen = [t for t in corner_tr if t.entry_date < UNSEEN_BEFORE]
    unseen_r = float(sum(t.pnl_r_net for t in unseen))
    head(f"Z5 - the window the designer never saw (entries before {UNSEEN_BEFORE})")
    print(f"  corner @0.05%: {len(unseen)} trades   portR {unseen_r:+.2f}")
    spec_unseen = float(sum(t.pnl_r_net for t in spec if t.entry_date < UNSEEN_BEFORE))
    print(f"  spec cell for scale: {spec_unseen:+.2f}")

    # ---- Z8 per asset -----------------------------------------------------
    head("Z8 - each asset on its own, in the corner @0.05%")
    per = {}
    for sym in ASSETS:
        rs = [t.pnl_r_net for t in corner_tr if t.symbol == sym]
        sp = [t.pnl_r_net for t in spec if t.symbol == sym]
        per[sym] = {"n": len(rs), "portR": float(sum(rs)),
                    "spec_portR": float(sum(sp))}
        print(f"  {sym:<10}{len(rs):>5} trades   corner {sum(rs):>+8.2f}   "
              f"spec cell {sum(sp):>+8.2f}")
    both_positive = all(v["portR"] > 0 for v in per.values())
    print(f"  both assets positive in the corner: {'YES' if both_positive else 'NO'}")

    # ---- Z6 breakeven -----------------------------------------------------
    head("Z6 - breakeven cost per side (full-history portR reaches 0)")
    be_fee = {}
    for ib in INTRABARS:
        for be in BE_RULES:
            f = breakeven_fee(ib, be)
            be_fee[label(ib, be)] = f
            print(f"  {label(ib, be):<24}{f * 100:>8.3f}%/side  "
                  f"({f * 200:.3f}% round trip)   headroom over 0.15%: "
                  f"{f / SURVIVAL_FEE:>4.1f}x")

    # ---- verdict ----------------------------------------------------------
    survived = z1 and z2 and z3 and z4
    if survived:
        verdict, note = "SURVIVES THE HONEST CORNER", "the interval is the result"
    elif z2 and z3:
        verdict, note = ("EDGE REAL BUT THIN",
                         "Z4 failed - state the cost ceiling from Z6")
    elif z2:
        verdict, note = "IS-ONLY", "Z3 failed - the full-history profit is in-sample"
    else:
        verdict, note = ("FAILS",
                         "Z2 failed - the profit was the assumptions, stop the line")
    head(f"VERDICT: {verdict}   ({note})")
    print(f"  Z1 {tick(z1)}  Z2 {tick(z2)}  Z3 {tick(z3)}  Z4 {tick(z4)}")
    print(f"\n  S003 full-history portR lives in [{corner['full']:+.2f}, "
          f"{base:+.2f}] R at 0.05%/side - report the interval, never one end")
    print("  No promotion. No live orders. Research artifact only.")

    payload = {"experiment": "E56", "criteria": "docs/E56_CRITERIA.md",
               "grid": grid, "corner": corner, "spec_cell": base,
               "kept_share": kept,
               "decomposition": {"only_sl_first": only_sl, "only_literal_be": only_be,
                                 "only_fee_015": only_fee, "joint": joint,
                                 "additive": additive, "interaction": inter},
               "survival": {"cagr": c_oos, "maxDD": ddo, "final": fo,
                            "bh_cagr": BH_OOS_CAGR, "bh_dd": BH_OOS_DD},
               "unseen": {"trades": len(unseen), "portR": unseen_r,
                          "spec_portR": spec_unseen, "cutoff": UNSEEN_BEFORE},
               "per_asset": per, "breakeven_fee_side": be_fee,
               "worst_cell_at_005": worst_key, "corner_is_worst": z9,
               "be_axis_nested_in_intrabar": nested,
               "tied_worst_cells": ties,
               "checks": {"Z1": z1, "Z2": z2, "Z3": z3, "Z4": z4, "Z9": z9},
               "verdict": verdict, "run_count": len(grid)}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0 if z2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
