"""E58 - is S003 worth more than doing nothing, measured as a distribution?

Criteria declared in `docs/E58_CRITERIA.md` BEFORE this file existed. Run:

    python e58_vs_holding.py

E50 Y3 and E56 Z4 both compared S003 to buy & hold at 1% risk per trade, where
S003 is deliberately under-deployed and buy & hold is 100% invested the whole
time. Both failed. This asks the fair version of the question: size S003 so its
drawdown matches buy & hold's, then resample both through the SAME shuffled
history 500 times and count how often each wins.

Buy & hold pays no fees here and S003 pays 0.15% a side in the primary arm.
Both handicaps favour holding, on purpose.
"""

import datetime as dt
import json
import os

import numpy as np

from e45_s003_full import load, ASSETS, INITIAL
from e47_sizing_overlay import SPLIT, OOS_TO
from e56_honest_corner import trades_for, CORNER, SPEC_CELL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "vs-holding-e58.json")

W_OOS = ("W_OOS", SPLIT, OOS_TO)
W_COMMON = ("W_COMMON", "2020-04-10", OOS_TO)      # first bar SOL exists
WINDOWS = (W_OOS, W_COMMON)

BLOCK, RESAMPLES = 20, 500
SURVIVAL_FEE = 0.0015
BH_REF = {"cagr": 0.1040, "dd": 0.7406}
S2_BAR, S2B_BAR = 0.90, 0.60
PLAIN_RISK = 0.01


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


# --------------------------------------------------------------------------
# the two return series, on one shared date axis
# --------------------------------------------------------------------------

def bh_series(lo, hi):
    """50/50 at the first close, never rebalanced. Dates both assets share."""
    per = {}
    for s in ASSETS:
        dates, _, _, _, c, _ = load(s)
        per[s] = {d: c[i] for i, d in enumerate(dates) if lo <= d < hi}
    axis = sorted(set(per[ASSETS[0]]) & set(per[ASSETS[1]]))
    eq = np.zeros(len(axis))
    for s in ASSETS:
        p = np.array([per[s][d] for d in axis])
        eq += 0.5 * p / p[0]
    return axis, eq


def s003_daily(trades, risk, axis):
    """Daily returns of the S003 book on the same axis.

    P&L is booked on exit dates only - there is no mark-to-market while a
    position is open - so the series is lumpier than reality and the drawdown
    it produces is a floor, not an estimate. The criteria require this to be
    stated wherever the result appears; it flatters S003.
    """
    at = {d: i for i, d in enumerate(axis)}
    sel = [t for t in trades if t.entry_date in at and t.exit_date in at]
    events = sorted([(t.entry_date, 0, t) for t in sel]
                    + [(t.exit_date, 1, t) for t in sel],
                    key=lambda x: (x[0], x[1]))
    cash, risked = INITIAL, {}
    daily = np.zeros(len(axis))
    for _, kind, t in events:
        if kind == 0:
            risked[id(t)] = cash * risk
        else:
            before = cash
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            if before > 0:
                daily[at[t.exit_date]] += cash / before - 1.0
            if cash <= 0:
                break
    return daily


def curve_stats(rets):
    eq = np.cumprod(1.0 + rets)
    final = float(eq[-1])
    peak = np.maximum.accumulate(eq)
    dd = float(((peak - eq) / peak).max())
    return final, dd, (final - 1.0) - 2.0 * dd


def calibrate(trades, axis, target_dd):
    """One calibration on the realised path; frozen for every bootstrap path."""
    lo_r, hi_r = 0.0005, 0.40
    for _ in range(60):
        mid = (lo_r + hi_r) / 2
        _, dd, _ = curve_stats(s003_daily(trades, mid, axis))
        if dd < target_dd:
            lo_r = mid
        else:
            hi_r = mid
    return (lo_r + hi_r) / 2


def block_index(n, rng):
    out = []
    while len(out) < n:
        s = rng.integers(0, max(1, n - BLOCK + 1))
        out.extend(range(s, min(s + BLOCK, n)))
    return np.array(out[:n])


def paired_bootstrap(a, b):
    """Same block order applied to both series - one shuffled history, two arms."""
    wins_r, wins_w, dd_worse = 0, 0, 0
    rows = []
    for i in range(RESAMPLES):
        order = block_index(len(a), np.random.default_rng(6000 + i))
        fa, da, ra = curve_stats(a[order])
        fb, db, rb = curve_stats(b[order])
        wins_r += ra > rb
        wins_w += fa > fb
        dd_worse += da > db
        rows.append((fa, da, ra, fb, db, rb))
    arr = np.array(rows)
    return {"robust_win": wins_r / RESAMPLES, "wealth_win": wins_w / RESAMPLES,
            "dd_worse_share": dd_worse / RESAMPLES,
            "s003_final_median": float(np.median(arr[:, 0])),
            "bh_final_median": float(np.median(arr[:, 3])),
            "s003_dd_median": float(np.median(arr[:, 1])),
            "bh_dd_median": float(np.median(arr[:, 4]))}


def single_asset(symbol, axis):
    dates, _, _, _, c, _ = load(symbol)
    m = {d: c[i] for i, d in enumerate(dates)}
    p = np.array([m[d] for d in axis])
    return np.concatenate([[0.0], p[1:] / p[:-1] - 1.0])


def main():
    head("E58 - S003 vs doing nothing, as a distribution | docs/E58_CRITERIA.md")
    print("  buy & hold pays no fees; the primary S003 arm pays 0.15%/side")
    print("  both handicaps favour holding, on purpose")

    arms = {"corner": (CORNER, SURVIVAL_FEE), "spec": (SPEC_CELL, 0.0005)}
    books = {k: trades_for(cell[0], cell[1], fee) for k, (cell, fee) in arms.items()}

    # ---- S1 harness -------------------------------------------------------
    axis0, eq0 = bh_series(*W_OOS[1:])
    yrs = ((dt.date.fromisoformat(axis0[-1]) - dt.date.fromisoformat(axis0[0])).days
           / 365.25)
    bh_cagr = float(eq0[-1]) ** (1 / yrs) - 1
    peak = np.maximum.accumulate(eq0)
    bh_dd = float(((peak - eq0) / peak).max())
    s1 = (abs(bh_cagr - BH_REF["cagr"]) <= 0.0005
          and abs(bh_dd - BH_REF["dd"]) <= 0.0005)
    print(f"\n  S1 harness: buy&hold W_OOS CAGR {bh_cagr:+.2%} (E50 +10.40%) | "
          f"maxDD {bh_dd:.2%} (74.06%)  -> {tick(s1)}")
    if not s1:
        print("  STOP per criteria section 3.")
        return 1

    results = {}
    for name, lo, hi in WINDOWS:
        axis, eq = bh_series(lo, hi)
        bh_ret = np.concatenate([[0.0], eq[1:] / eq[:-1] - 1.0])
        bh_final, bh_maxdd, bh_robust = curve_stats(bh_ret)
        head(f"{name}  {lo} -> {hi}   ({len(axis)} days)")
        print(f"  buy & hold: total {bh_final - 1:+.1%}   maxDD {bh_maxdd:.1%}   "
              f"robust {bh_robust:+.3f}")

        win = {"days": len(axis), "from": lo, "to": hi,
               "bh": {"total": bh_final - 1, "maxDD": bh_maxdd,
                      "robust": bh_robust}, "arms": {}}

        for arm, trades in books.items():
            risk = calibrate(trades, axis, bh_maxdd)
            ser = s003_daily(trades, risk, axis)
            f, d, r = curve_stats(ser)
            boot = paired_bootstrap(ser, bh_ret)
            plain = s003_daily(trades, PLAIN_RISK, axis)
            pf, pd_, pr = curve_stats(plain)
            win["arms"][arm] = {
                "matched_risk": risk, "total": f - 1, "maxDD": d, "robust": r,
                "bootstrap": boot,
                "plain_1pct": {"total": pf - 1, "maxDD": pd_, "robust": pr},
            }
            tag = "PRIMARY" if arm == "corner" else "ceiling"
            print(f"\n  S003 {arm} ({tag})  risk {risk * 100:.2f}%/trade "
                  f"to match maxDD {bh_maxdd:.1%}")
            print(f"    realised: total {f - 1:+.1%}   maxDD {d:.1%}   "
                  f"robust {r:+.3f}")
            print(f"    paired bootstrap over {RESAMPLES} shuffled histories "
                  f"(blocks of {BLOCK} days):")
            print(f"      robust  win rate {boot['robust_win']:.1%}   "
                  f"(need >= {S2_BAR:.0%})")
            print(f"      wealth  win rate {boot['wealth_win']:.1%}   "
                  f"(need >= {S2B_BAR:.0%})")
            print(f"      median final: S003 {boot['s003_final_median']:.2f}x  vs "
                  f"buy&hold {boot['bh_final_median']:.2f}x")
            print(f"      S4 paths where S003 drew down MORE: "
                  f"{boot['dd_worse_share']:.1%}")
            print(f"    S7 at a plain {PLAIN_RISK:.0%} risk (E50/E56's setting): "
                  f"total {pf - 1:+.1%}  maxDD {pd_:.1%}  robust {pr:+.3f}")

        results[name] = win

    # ---- S6 single assets -------------------------------------------------
    head("S6 - against holding each coin on its own (W_OOS, matched-DD corner arm)")
    axis, eq = bh_series(*W_OOS[1:])
    corner_ser = s003_daily(books["corner"],
                            results["W_OOS"]["arms"]["corner"]["matched_risk"], axis)
    s6 = {}
    for sym in ASSETS:
        ser = single_asset(sym, axis)
        f, d, r = curve_stats(ser)
        boot = paired_bootstrap(corner_ser, ser)
        s6[sym] = {"total": f - 1, "maxDD": d, "robust": r, "bootstrap": boot}
        print(f"  hold {sym:<10} total {f - 1:>+8.1%}  maxDD {d:>6.1%}  "
              f"robust {r:>+7.3f}   S003 robust-win {boot['robust_win']:>6.1%}  "
              f"wealth-win {boot['wealth_win']:>6.1%}")

    # ---- verdict ----------------------------------------------------------
    prim = results["W_OOS"]["arms"]["corner"]["bootstrap"]
    s2 = prim["robust_win"] >= S2_BAR
    s2b = prim["wealth_win"] >= S2B_BAR
    com = results["W_COMMON"]["arms"]["corner"]["bootstrap"]
    s3 = com["robust_win"] >= S2_BAR and com["wealth_win"] >= S2B_BAR

    head("VERDICT")
    print(f"  S1 {tick(s1)}   S2 robust {prim['robust_win']:.1%} {tick(s2)}   "
          f"S2b wealth {prim['wealth_win']:.1%} {tick(s2b)}   "
          f"S3 W_COMMON {tick(s3)}")
    if s2 and s2b:
        verdict = "WORTH MORE THAN HOLDING"
        note = "research on S003 closes here; the next step is forward paper, not more backtests"
    elif s2:
        verdict = "A DRAWDOWN STRATEGY, NOT A RETURN STRATEGY"
        note = "it wins on robust because holding draws down hard, not by making more money"
    else:
        verdict = "NOT WORTH IT"
        note = "even spotted the sizing advantage it does not beat doing nothing"
    print(f"\n  {verdict}\n  {note}")
    print("\n  Standing caveat required by the criteria: S003's P&L is booked on")
    print("  exit dates with no mark-to-market while a position is open, so every")
    print("  drawdown quoted for it here is a FLOOR. Buy & hold is marked daily.")
    print("  No promotion. No live orders. Research artifact only.")

    payload = {"experiment": "E58", "criteria": "docs/E58_CRITERIA.md",
               "block": BLOCK, "resamples": RESAMPLES,
               "bars": {"S2": S2_BAR, "S2b": S2B_BAR},
               "windows": results, "S6_single_assets": s6,
               "checks": {"S1": s1, "S2": s2, "S2b": s2b, "S3": s3},
               "verdict": verdict}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
