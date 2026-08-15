"""E51 - does the S003 edge appear on coins that were never used to design it?

Criteria declared in `docs/E51_CRITERIA.md` BEFORE this file existed. Run:

    python e51_universe.py

SOL and LINK are the design set, so they prove nothing about the rule itself.
The other 31 symbols in the universe file are a cross-section the strategy has
never seen - a stronger out-of-sample than another slice of the same two coins.
Base case is E50's harsh corner: sl_first fills at 0.15% a side.
"""

import datetime as dt
import json
import os

import numpy as np

from dynamic_grid import strat_trap as st
from e45_s003_full import load as load_yahoo, ASSETS as DESIGN_SET
from e47_sizing_overlay import INITIAL

ROOT = os.path.dirname(os.path.abspath(__file__))
UNIVERSE = os.path.join(ROOT, "data", "universe", "spot_1d.json")
OUT = os.path.join(ROOT, "docs", "universe-e51.json")

DESIGN = ("SOL", "LINK")
ARMS = (("sl_first", 0.0015), ("tp_first", 0.0005))   # base case first
RISKS = (0.0025, 0.005, 0.01)
BASE_PORTR = 72.81
TWO_ASSET_REF = {"cagr": 0.085, "dd": 0.180}   # E49: Yahoo SOL+LINK, 1%, tp_first
ERA_SPLIT = "2021-01-01"


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def load_universe():
    with open(UNIVERSE, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for sym, rows in raw.items():
        d = [dt.datetime.utcfromtimestamp(r[0] / 1000).strftime("%Y-%m-%d")
             for r in rows]
        o = np.array([float(r[1]) for r in rows])
        h = np.array([float(r[2]) for r in rows])
        l = np.array([float(r[3]) for r in rows])
        c = np.array([float(r[4]) for r in rows])
        out[sym] = (d, o, h, l, c)
    return out


def equity(trades, risk):
    """One position per symbol, unlimited symbols. Risk set at entry."""
    if not trades:
        return INITIAL, 0.0, 0, 0, 0.0
    events = sorted([(t.entry_date, 0, t) for t in trades]
                    + [(t.exit_date, 1, t) for t in trades],
                    key=lambda x: (x[0], x[1]))
    cash, risked, curve, open_n, peak_open, area = INITIAL, {}, [INITIAL], 0, 0, 0
    steps = 0
    for _, kind, t in events:
        if kind == 0:
            risked[id(t)] = cash * risk
            open_n += 1
            peak_open = max(peak_open, open_n)
        else:
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            open_n -= 1
            curve.append(cash)
            if cash <= 0:
                return 0.0, 1.0, len(trades), peak_open, float(peak_open)
        area += open_n
        steps += 1
    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return (cash, float(((peak - arr) / peak).max()), len(trades),
            peak_open, area / max(steps, 1))


def cagr_of(final, trades):
    if not trades or final <= 0:
        return -1.0
    a = dt.date.fromisoformat(min(t.entry_date for t in trades))
    b = dt.date.fromisoformat(max(t.exit_date for t in trades))
    y = (b - a).days / 365.25
    return (final / INITIAL) ** (1 / y) - 1 if y > 0 else -1.0


def main():
    head("E51 - cross-sectional out-of-sample | criteria docs/E51_CRITERIA.md")

    # ---- Z1 harness: the engine itself is untouched -----------------------
    pr = 0.0
    for sym in DESIGN_SET:
        d, o, h, l, c, _ = load_yahoo(sym)
        pr += st.run_symbol(sym, d, o, h, l, c).port_r
    z1 = abs(pr - BASE_PORTR) <= 0.1
    print(f"  Z1 harness: Yahoo SOL+LINK portR {pr:+.2f} (E45 +72.81)  -> {tick(z1)}")
    if not z1:
        print("  STOP per criteria section 4.")
        return 1

    uni = load_universe()
    test_set = [s for s in uni if s not in DESIGN]
    print(f"  universe {len(uni)} symbols | design set {DESIGN} "
          f"| test set {len(test_set)} symbols never used to design S003")
    print(f"  base case = sl_first @0.15%/side (E50's harsh corner)")

    runs = {}
    for intrabar, fee in ARMS:
        params = st.Params(fee_side=fee)
        per = {}
        for sym, (d, o, h, l, c) in uni.items():
            r = st.run_symbol(sym, d, o, h, l, c, intrabar=intrabar, params=params)
            per[sym] = {"portR": r.port_r, "n": len(r.closed),
                        "first": d[0], "last": d[-1], "trades": r.closed}
        runs[(intrabar, fee)] = per

    base_key = ARMS[0]
    alt_key = ARMS[1]

    head("Z5 - every symbol, both arms (reported in full, always)")
    print(f"  {'sym':<7}{'listed':>12}{'ends':>12}{'n':>5}"
          f"{'sl_first@0.15%':>16}{'tp_first@0.05%':>16}  set")
    for sym in sorted(uni, key=lambda s: -runs[base_key][s]["portR"]):
        b, a = runs[base_key][sym], runs[alt_key][sym]
        tag = "DESIGN" if sym in DESIGN else "test"
        print(f"  {sym:<7}{b['first']:>12}{b['last']:>12}{b['n']:>5}"
              f"{b['portR']:>16.2f}{a['portR']:>16.2f}  {tag}")

    # ---- Z2 / Z3 ---------------------------------------------------------
    head("Z2 / Z3 - the test set (31 symbols never used to design S003)")
    tot = {}
    for key in ARMS:
        tot[key] = sum(runs[key][s]["portR"] for s in test_set)
    z2 = all(tot[k] > 0 for k in ARMS)
    pos = sum(1 for s in test_set if runs[base_key][s]["portR"] > 0)
    share = pos / len(test_set)
    z3 = share >= 0.60
    for (ib, fee) in ARMS:
        n = sum(runs[(ib, fee)][s]["n"] for s in test_set)
        print(f"  {ib}@{fee * 100:.2f}%   total portR {tot[(ib, fee)]:+8.2f}   n={n}")
    print(f"  Z2 both arms positive   -> {tick(z2)}")
    print(f"  Z3 profitable symbols {pos}/{len(test_set)} = {share:.0%} (need >= 60%)"
          f"   -> {tick(z3)}")
    design_tot = sum(runs[base_key][s]["portR"] for s in DESIGN)
    print(f"  (design set SOL+LINK on Binance data, base case: {design_tot:+.2f})")

    # ---- Z6 era + dead symbols ------------------------------------------
    head("Z6 - by listing era, and the symbols whose data ends early")
    old = [s for s in test_set if runs[base_key][s]["first"] < ERA_SPLIT]
    new = [s for s in test_set if runs[base_key][s]["first"] >= ERA_SPLIT]
    for label, grp in (("listed before 2021", old), ("listed 2021+", new)):
        t = sum(runs[base_key][s]["portR"] for s in grp)
        p = sum(1 for s in grp if runs[base_key][s]["portR"] > 0)
        print(f"  {label:<20} {len(grp):>2} symbols   portR {t:>+8.2f}   "
              f"profitable {p}/{len(grp)}")
    last_day = max(runs[base_key][s]["last"] for s in uni)
    dead = [s for s in uni if runs[base_key][s]["last"] < last_day]
    print(f"  data ends before {last_day} (delisted/dead): {dead or 'none'}")

    # ---- Z4 diversification ---------------------------------------------
    head("Z4 - does breadth buy a lower drawdown at the same return?")
    print(f"  reference: 2 symbols @1%/trade = CAGR {TWO_ASSET_REF['cagr']:+.1%}, "
          f"maxDD {TWO_ASSET_REF['dd']:.1%}")
    print(f"  {'risk':>7}{'CAGR':>10}{'maxDD':>9}{'$10k ->':>11}"
          f"{'peak open':>11}{'avg open':>10}")
    port, z4 = {}, False
    all_tr = [t for s in uni for t in runs[base_key][s]["trades"]]
    for risk in RISKS:
        f, dd, n, pk, avg = equity(all_tr, risk)
        cg = cagr_of(f, all_tr)
        port[f"{risk:.4f}"] = {"cagr": cg, "maxDD": dd, "final": f,
                               "peak_open": pk, "avg_open": avg, "n": n}
        print(f"  {risk * 100:>6.2f}%{cg:>+10.1%}{dd:>9.1%}{f:>11,.0f}"
              f"{pk:>11}{avg:>10.1f}")
    matched = [r for r in port.values() if r["cagr"] >= TWO_ASSET_REF["cagr"]]
    if matched:
        best = min(matched, key=lambda r: r["maxDD"])
        z4 = best["maxDD"] < TWO_ASSET_REF["dd"]
        print(f"  lowest maxDD among levels reaching {TWO_ASSET_REF['cagr']:+.1%}: "
              f"{best['maxDD']:.1%} vs {TWO_ASSET_REF['dd']:.1%}   -> {tick(z4)}")
    else:
        print(f"  no risk level reaches the 2-symbol CAGR   -> {tick(False)}")

    general = z1 and z2 and z3
    head(f"VERDICT: {'edge is GENERAL (not a 2-coin artifact)' if general else 'edge does NOT generalise'}"
         f"   (promotion forbidden regardless)")

    payload = {
        "experiment": "E51", "criteria": "docs/E51_CRITERIA.md",
        "universe": sorted(uni), "design_set": list(DESIGN),
        "test_set_size": len(test_set),
        "per_symbol": {f"{ib}@{fee}": {s: {k: v for k, v in runs[(ib, fee)][s].items()
                                           if k != "trades"} for s in uni}
                       for ib, fee in ARMS},
        "test_totals": {f"{ib}@{fee}": tot[(ib, fee)] for ib, fee in ARMS},
        "profitable_share": share, "portfolio": port,
        "dead_symbols": dead,
        "checks": {"Z1": z1, "Z2": z2, "Z3": z3, "Z4": z4},
        "verdict": "GENERAL" if general else "NOT_GENERAL",
        "bias_disclosure": ("universe file assembled in 2026 for an earlier "
                            "experiment; not point-in-time; upward biased"),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
