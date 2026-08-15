"""E48 - try to kill V4 (the equity-curve filter), and promote only if it survives.

Criteria declared in `docs/E48_CRITERIA.md` BEFORE this file existed. Run:

    python e48_v4_adversarial.py

E47 gave V4 a pass on a single OOS window, with a contradicting signal on IS.
Nothing here is designed to confirm it. W1 replaces its signal with noise of the
same duty cycle, W4 destroys the loss clustering it claims to exploit, and W6
strips away the extra base risk the drawdown-matching handed it. Promotion needs
all six.
"""

import json
import os

import numpy as np

from e47_sizing_overlay import (
    build, sigma_ref, simulate, cagr, INITIAL,
    IS_FROM, SPLIT, OOS_TO, EQ_MA,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "v4-adversarial-e48.json")

RISK_V4, RISK_V0 = 0.0576, 0.0470     # carried from E47, never recalibrated
E47_V4 = {"cagr": 0.724, "dd": 0.509}
E47_V0 = {"cagr": 0.583, "dd": 0.625}
SEEDS = 20
FOLD_MONTHS = 6


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def run(trades, risk, mode, lo, hi, *, lookback=EQ_MA, cut=0.5,
        rng=None, duty=None, order=None, symbols=None):
    """Generalised V4/V0 path. `mode`: flat | eqma | placebo."""
    sel = [t for t in trades if lo <= t.entry_date < hi]
    if symbols:
        sel = [t for t in sel if t.symbol in symbols]
    if not sel:
        return INITIAL, 0.0, 0
    if order is not None:                      # W4: shuffle the sequence
        sel = [sel[i] for i in order if i < len(sel)]
        events = []
        for k, t in enumerate(sel):
            events += [(k, 0, t), (k, 1, t)]
        events.sort(key=lambda x: (x[0], x[1]))
    else:
        events = sorted([(t.entry_date, 0, t) for t in sel]
                        + [(t.exit_date, 1, t) for t in sel],
                        key=lambda x: (x[0], x[1]))

    cash, risked, curve, closed = INITIAL, {}, [INITIAL], []
    for _, kind, t in events:
        if kind == 0:
            scale = 1.0
            if mode == "eqma" and len(closed) >= lookback:
                if cash < float(np.mean(closed[-lookback:])):
                    scale = cut
            elif mode == "placebo" and rng.random() < duty:
                scale = cut
            risked[id(t)] = cash * risk * scale
        else:
            cash += risked.pop(id(t), cash * risk) * t.pnl_r_net
            closed.append(cash)
            curve.append(cash)
            if cash <= 0:
                return 0.0, 1.0, len(sel)

    arr = np.array(curve)
    peak = np.maximum.accumulate(arr)
    return cash, float(((peak - arr) / peak).max()), len(sel)


def duty_cycle(trades, lo, hi):
    """Fraction of entries V4 actually halves - the placebo must match it."""
    sel = sorted([t for t in trades if lo <= t.entry_date < hi],
                 key=lambda t: (t.entry_date,))
    events = sorted([(t.entry_date, 0, t) for t in sel]
                    + [(t.exit_date, 1, t) for t in sel],
                    key=lambda x: (x[0], x[1]))
    cash, risked, closed, cut_n, tot = INITIAL, {}, [], 0, 0
    for _, kind, t in events:
        if kind == 0:
            tot += 1
            scale = 1.0
            if len(closed) >= EQ_MA and cash < float(np.mean(closed[-EQ_MA:])):
                scale, cut_n = 0.5, cut_n + 1
            risked[id(t)] = cash * RISK_V4 * scale
        else:
            cash += risked.pop(id(t), 0.0) * t.pnl_r_net
            closed.append(cash)
    return cut_n / tot


def folds():
    """Exactly the 8 half-year folds the criteria declare.

    Generating boundaries until they run past OOS_TO produced a ninth fold 12
    days long holding 3 trades. A stub that short is not an independent
    observation, and counting it would change the W2 denominator the criteria
    fixed at 8, so the remainder is absorbed into the final fold.
    """
    out, y, m = [], 2022, 8
    for _ in range(8):
        out.append(f"{y}-{m:02d}-01")
        m += FOLD_MONTHS
        if m > 12:
            m -= 12
            y += 1
    return out + [OOS_TO]


def calibrate_on(trades, mode, risk_hint, target_dd, lo, hi):
    """W6 only, and declared as a diagnostic: match maxDD on the OOS window itself."""
    lo_r, hi_r = 0.001, 0.40
    for _ in range(60):
        mid = (lo_r + hi_r) / 2
        _, dd, _ = run(trades, mid, mode, lo, hi)
        if dd < target_dd:
            lo_r = mid
        else:
            hi_r = mid
    return (lo_r + hi_r) / 2


def main():
    head("E48 - adversarial tests on V4 | criteria docs/E48_CRITERIA.md")
    trades = build()
    sigma_ref(trades)   # same construction path as E47

    # ---- W7 harness ------------------------------------------------------
    v4_f, v4_dd, n = run(trades, RISK_V4, "eqma", SPLIT, OOS_TO)
    v0_f, v0_dd, _ = run(trades, RISK_V0, "flat", SPLIT, OOS_TO)
    v4_c, v0_c = cagr(v4_f, trades, SPLIT, OOS_TO), cagr(v0_f, trades, SPLIT, OOS_TO)
    w7 = (abs(v4_c - E47_V4["cagr"]) <= 0.005 and abs(v4_dd - E47_V4["dd"]) <= 0.005
          and abs(v0_c - E47_V0["cagr"]) <= 0.005 and abs(v0_dd - E47_V0["dd"]) <= 0.005)
    print(f"  W7 harness: V4 {v4_c:+.1%}/{v4_dd:.1%} (E47 +72.4%/50.9%) | "
          f"V0 {v0_c:+.1%}/{v0_dd:.1%} (E47 +58.3%/62.5%)  -> {tick(w7)}")
    if not w7:
        print("  STOP per criteria section 3.")
        return 1
    print(f"  OOS trades = {n}")

    res = {}

    # ---- W1 placebo ------------------------------------------------------
    duty = duty_cycle(trades, SPLIT, OOS_TO)
    pl = []
    for s in range(SEEDS):
        f, _, _ = run(trades, RISK_V4, "placebo", SPLIT, OOS_TO,
                      rng=np.random.default_rng(1000 + s), duty=duty)
        pl.append(cagr(f, trades, SPLIT, OOS_TO))
    p90 = float(np.percentile(pl, 90))
    w1 = v4_c > p90
    head("W1 - placebo: random halving at the same duty cycle, 20 seeds")
    print(f"  V4 halves {duty:.1%} of entries; the placebo halves the same share at random")
    print(f"  placebo CAGR  min {min(pl):+.1%}  median {np.median(pl):+.1%}  "
          f"p90 {p90:+.1%}  max {max(pl):+.1%}")
    print(f"  V4 {v4_c:+.1%} vs p90 {p90:+.1%}   -> {tick(w1)}")
    beat = sum(1 for x in pl if x >= v4_c)
    print(f"  placebo seeds reaching V4 or better: {beat}/{SEEDS}")
    res["W1"] = {"pass": w1, "duty": duty, "p90": p90,
                 "median": float(np.median(pl)), "beat": beat}

    # ---- W2 fold by fold -------------------------------------------------
    b = folds()
    head("W2 - fold by fold, each fold restarted from $10,000")
    print(f"  {'fold':<26}{'n':>5}{'V4 final':>12}{'V0 final':>12}{'winner':>9}")
    wins, rows = 0, []
    for k in range(len(b) - 1):
        lo, hi = b[k], b[k + 1]
        f4, _, nk = run(trades, RISK_V4, "eqma", lo, hi)
        f0, _, _ = run(trades, RISK_V0, "flat", lo, hi)
        win = f4 > f0
        wins += win
        rows.append({"from": lo, "to": hi, "n": nk, "v4": f4, "v0": f0, "v4_wins": win})
        print(f"  {lo + ' -> ' + hi:<26}{nk:>5}{f4:>12,.0f}{f0:>12,.0f}"
              f"{('V4' if win else 'V0'):>9}")
    w2 = wins >= 6
    print(f"  V4 wins {wins}/{len(rows)} folds (need >= 6)   -> {tick(w2)}")
    res["W2"] = {"pass": w2, "wins": wins, "folds": rows}

    # ---- W3 parameter fragility -----------------------------------------
    head("W3 - parameter fragility: 5 lookbacks x 3 cut factors")
    print(f"  {'lookback':>9}" + "".join(f"{f'cut {c}':>12}" for c in (0.25, 0.5, 0.75)))
    survive, grid = 0, []
    for lb in (10, 15, 20, 30, 40):
        cells = []
        for cut in (0.25, 0.5, 0.75):
            f, _, _ = run(trades, RISK_V4, "eqma", SPLIT, OOS_TO, lookback=lb, cut=cut)
            cg = cagr(f, trades, SPLIT, OOS_TO)
            ok = cg > v0_c
            survive += ok
            cells.append(f"{cg:+.1%}{'*' if ok else ' '}")
            grid.append({"lookback": lb, "cut": cut, "cagr": cg, "beats_v0": ok})
        print(f"  {lb:>9}" + "".join(f"{c:>12}" for c in cells))
    w3 = survive >= 8
    print(f"  * = beats V0 ({v0_c:+.1%}) | {survive}/15 beat V0 (need >= 8)   -> {tick(w3)}")
    res["W3"] = {"pass": w3, "survive": survive, "grid": grid}

    # ---- W4 shuffle the trade order -------------------------------------
    real_gap = v4_c - v0_c
    sel_n = len([t for t in trades if SPLIT <= t.entry_date < OOS_TO])
    gaps = []
    for s in range(SEEDS):
        order = np.random.default_rng(2000 + s).permutation(sel_n)
        f4, _, _ = run(trades, RISK_V4, "eqma", SPLIT, OOS_TO, order=order)
        f0, _, _ = run(trades, RISK_V0, "flat", SPLIT, OOS_TO, order=order)
        gaps.append(cagr(f4, trades, SPLIT, OOS_TO) - cagr(f0, trades, SPLIT, OOS_TO))
    med_gap = float(np.median(gaps))
    w4 = real_gap > med_gap
    head("W4 - shuffle the trade order (destroys loss clustering), 20 seeds")
    print(f"  real V4-V0 gap {real_gap * 100:+.1f}pt | shuffled median "
          f"{med_gap * 100:+.1f}pt (min {min(gaps) * 100:+.1f}, max {max(gaps) * 100:+.1f})")
    print(f"  the claimed mechanism needs real > shuffled   -> {tick(w4)}")
    res["W4"] = {"pass": w4, "real_gap": real_gap, "shuffled_median": med_gap}

    # ---- W5 per asset ----------------------------------------------------
    head("W5 - each asset on its own")
    per, w5 = {}, True
    for sym in sorted({t.symbol for t in trades}):
        f4, d4, nk = run(trades, RISK_V4, "eqma", SPLIT, OOS_TO, symbols={sym})
        f0, d0, _ = run(trades, RISK_V0, "flat", SPLIT, OOS_TO, symbols={sym})
        ok = f4 > f0
        w5 &= ok
        per[sym] = {"n": nk, "v4": f4, "v0": f0, "v4_dd": d4, "v0_dd": d0, "v4_wins": ok}
        print(f"  {sym:<8} n={nk:<4} V4 {f4:>10,.0f} (DD {d4:.1%})   "
              f"V0 {f0:>10,.0f} (DD {d0:.1%})   -> {'V4' if ok else 'V0'}")
    print(f"  V4 must win both   -> {tick(w5)}")
    res["W5"] = {"pass": w5, "assets": per}

    # ---- W6 equal OOS drawdown ------------------------------------------
    target = v4_dd
    r0 = calibrate_on(trades, "flat", RISK_V0, target, SPLIT, OOS_TO)
    r4 = calibrate_on(trades, "eqma", RISK_V4, target, SPLIT, OOS_TO)
    f0b, d0b, _ = run(trades, r0, "flat", SPLIT, OOS_TO)
    f4b, d4b, _ = run(trades, r4, "eqma", SPLIT, OOS_TO)
    c0b, c4b = cagr(f0b, trades, SPLIT, OOS_TO), cagr(f4b, trades, SPLIT, OOS_TO)
    w6 = c4b > c0b
    head(f"W6 - strip the leverage difference: both matched to OOS maxDD {target:.1%}")
    print(f"  V0 risk {r0 * 100:.2f}%  CAGR {c0b:+.1%}  DD {d0b:.1%}")
    print(f"  V4 risk {r4 * 100:.2f}%  CAGR {c4b:+.1%}  DD {d4b:.1%}")
    print(f"  V4 must still win   -> {tick(w6)}")
    res["W6"] = {"pass": w6, "target_dd": target, "v0_risk": r0, "v4_risk": r4,
                 "v0_cagr": c0b, "v4_cagr": c4b}

    # ---- verdict ---------------------------------------------------------
    order_ = ("W1", "W2", "W3", "W4", "W5", "W6")
    failed = [k for k in order_ if not res[k]["pass"]]
    head("VERDICT")
    for k in order_:
        print(f"  {k}  {tick(res[k]['pass'])}")
    promote = not failed
    print(f"\n  {'PROMOTE - V4 survived every attack' if promote else 'DO NOT PROMOTE'}"
          f"{'' if promote else '  (failed: ' + ', '.join(failed) + ')'}")
    if not promote:
        print("  Per the decision table, V4 stays a challenger.")

    payload = {"experiment": "E48", "criteria": "docs/E48_CRITERIA.md",
               "risk": {"V4": RISK_V4, "V0": RISK_V0}, "seeds": SEEDS,
               "harness_W7": w7, "tests": res, "failed": failed,
               "verdict": "PROMOTE" if promote else "CHALLENGER"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
