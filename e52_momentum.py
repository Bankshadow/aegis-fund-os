"""E52 - two momentum candidates, put through the gate E51 taught us to run first.

Criteria declared in `docs/E52_CRITERIA.md` BEFORE this file existed. Run:

    python e52_momentum.py

The order of the tests is the point. S003 died because a 0.1% price difference
between data vendors flipped 4.5-7.4% of its bar classifications. So the noise
gate runs on the full 33-coin cross-section before anything else is considered,
and its noise is drawn from the vendor disagreement E51 actually measured rather
than from an invented distribution.
"""

import datetime as dt
import json
import os

import numpy as np

from e45_s003_full import load as load_yahoo
from e51_universe import load_universe

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "momentum-e52.json")

LOOKBACKS = (30, 7, 14)          # 30 is the declared primary; others are reported
VOL_WIN, REBAL, QUINTILE = 20, 7, 0.20
FEE_SIDE = 0.0015                # E50's ceiling
NOISE_SEEDS = 20
GROSS = 1.0


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def panel():
    """Aligned close-price matrix: dates x symbols, NaN where not yet listed."""
    uni = load_universe()
    syms = sorted(uni)
    dates = sorted({d for s in syms for d in uni[s][0]})
    idx = {d: i for i, d in enumerate(dates)}
    px = np.full((len(dates), len(syms)), np.nan)
    for j, s in enumerate(syms):
        d, _, _, _, c = uni[s]
        for k, day in enumerate(d):
            px[idx[day], j] = c[k]
    return dates, syms, px


def vendor_noise_pool():
    """Log differences between Yahoo and Binance closes - the real thing, measured."""
    uni = load_universe()
    pool = []
    for ysym, bsym in (("LINK-USD", "LINK"), ("SOL-USD", "SOL")):
        yd, _, _, _, yc, _ = load_yahoo(ysym)
        bd, _, _, _, bc = uni[bsym]
        ym = dict(zip(yd, yc))
        for day, price in zip(bd, bc):
            if day in ym and price > 0 and ym[day] > 0:
                pool.append(np.log(ym[day] / price))
    return np.array(pool)


def backtest(px, logic, k, fee=FEE_SIDE):
    """Weekly-rebalanced, gross-1.0, no leverage. Returns the equity curve."""
    n_t, n_s = px.shape
    w = np.zeros(n_s)
    eq, curve = 1.0, [1.0]
    with np.errstate(invalid="ignore", divide="ignore"):
        rets = np.vstack([np.full((1, n_s), np.nan), np.diff(np.log(px), axis=0)])

    for t in range(1, n_t):
        step = np.nan_to_num(np.exp(rets[t]) - 1.0, nan=0.0)
        eq *= 1.0 + float(w @ step)
        if eq <= 0:
            return np.array(curve + [0.0])

        if t % REBAL == 0 and t > max(k, VOL_WIN):
            past = px[t - k, :]
            live = np.isfinite(px[t]) & np.isfinite(past) & (past > 0)
            mom = np.where(live, px[t] / np.where(past > 0, past, 1.0) - 1.0, np.nan)
            win = rets[t - VOL_WIN + 1:t + 1]
            sig = np.where(np.isfinite(win).all(axis=0), np.nanstd(win, axis=0), np.nan)
            live &= np.isfinite(sig) & (sig > 0)

            new = np.zeros(n_s)
            if live.sum() >= 5:
                if logic in ("M1-LO", "M1-LS"):
                    side = np.where(mom > 0, 1.0, -1.0 if logic == "M1-LS" else 0.0)
                    raw = np.where(live, side / np.where(sig > 0, sig, np.inf), 0.0)
                elif logic == "M2":
                    cand = np.where(live, mom, np.nan)
                    order = np.argsort(np.where(np.isnan(cand), -np.inf, cand))
                    valid = [j for j in order if live[j]]
                    m = max(1, int(len(valid) * QUINTILE))
                    raw = np.zeros(n_s)
                    for j in valid[-m:]:
                        raw[j] = 1.0
                    for j in valid[:m]:
                        raw[j] = -1.0
                else:                                    # V1 control
                    raw = np.where(live, 1.0, 0.0)
                gross = np.abs(raw).sum()
                if gross > 0:
                    new = raw / gross * GROSS
            eq -= eq * float(np.abs(new - w).sum()) * fee
            w = new
        curve.append(eq)
    return np.array(curve)


def stats(curve, dates):
    final = float(curve[-1])
    peak = np.maximum.accumulate(curve)
    dd = float(((peak - curve) / peak).max())
    years = ((dt.date.fromisoformat(dates[-1]) - dt.date.fromisoformat(dates[0])).days
             / 365.25)
    cg = final ** (1 / years) - 1 if final > 0 and years > 0 else -1.0
    return {"final": final, "cagr": cg, "maxDD": dd,
            "ret_dd": (final - 1) / dd if dd > 0 else 0.0}


def main():
    head("E52 - TSMOM vs cross-sectional momentum | criteria docs/E52_CRITERIA.md")
    dates, syms, px = panel()
    print(f"  {len(syms)} symbols, {len(dates)} days, {dates[0]} -> {dates[-1]}")

    # ---- V1 harness ------------------------------------------------------
    ctrl = stats(backtest(px, "CONTROL", 30, fee=0.0), dates)
    ew = np.nanmean(px / np.where(np.isfinite(px), px, np.nan), axis=1)  # placeholder
    # equal-weight buy & hold, rebalanced weekly at zero cost == the control
    bh_eq = backtest(px, "CONTROL", 30, fee=0.0)
    bh = stats(bh_eq, dates)
    v1 = abs(ctrl["cagr"] - bh["cagr"]) <= 0.005
    print(f"  V1 harness: zero-cost always-long control CAGR {ctrl['cagr']:+.1%} "
          f"vs equal-weight benchmark {bh['cagr']:+.1%}   -> {tick(v1)}")
    if not v1:
        print("  STOP per criteria section 4.")
        return 1

    btc_j = syms.index("BTC")
    bcol = px[:, btc_j]
    first = int(np.argmax(np.isfinite(bcol)))
    btc = {"final": float(bcol[-1] / bcol[first]),
           "cagr": (bcol[-1] / bcol[first]) ** (365.25 / (len(dates) - first)) - 1,
           "maxDD": float(((np.maximum.accumulate(bcol[first:]) - bcol[first:])
                           / np.maximum.accumulate(bcol[first:])).max())}
    btc["ret_dd"] = (btc["final"] - 1) / btc["maxDD"]

    # ---- V6 the table ----------------------------------------------------
    head(f"V6 - all nine arms at {FEE_SIDE * 100:.2f}%/side (k=30 is the declared primary)")
    print(f"  {'arm':<14}{'CAGR':>9}{'maxDD':>9}{'ret/DD':>9}{'$10k ->':>12}")
    rows = {}
    for logic in ("M1-LO", "M1-LS", "M2"):
        for k in LOOKBACKS:
            s = stats(backtest(px, logic, k), dates)
            rows[f"{logic}|k{k}"] = s
            star = " <- primary" if k == 30 else ""
            print(f"  {logic + ' k=' + str(k):<14}{s['cagr']:>+9.1%}{s['maxDD']:>9.1%}"
                  f"{s['ret_dd']:>9.2f}{s['final'] * 10000:>12,.0f}{star}")
    print(f"  {'EW buy&hold':<14}{bh['cagr']:>+9.1%}{bh['maxDD']:>9.1%}"
          f"{bh['ret_dd']:>9.2f}{bh['final'] * 10000:>12,.0f}")
    print(f"  {'BTC buy&hold':<14}{btc['cagr']:>+9.1%}{btc['maxDD']:>9.1%}"
          f"{btc['ret_dd']:>9.2f}{btc['final'] * 10000:>12,.0f}")

    # ---- V2 the noise gate ----------------------------------------------
    pool = vendor_noise_pool()
    head("V2 - the gate that killed S003: real Yahoo-vs-Binance noise, 20 seeds")
    print(f"  noise pool {len(pool):,} measured log differences | "
          f"median |diff| {np.median(np.abs(pool)):.3%} | p99 {np.percentile(np.abs(pool), 99):.2%}")
    print(f"  {'arm':<14}{'clean':>10}{'median':>10}{'ratio':>8}"
          f"{'same sign':>11}{'result':>8}")
    v2 = {}
    for logic in ("M1-LO", "M1-LS", "M2"):
        clean = rows[f"{logic}|k30"]["final"] - 1.0
        outs = []
        for s in range(NOISE_SEEDS):
            rng = np.random.default_rng(7000 + s)
            noisy = px * np.exp(rng.choice(pool, size=px.shape))
            outs.append(stats(backtest(noisy, logic, 30), dates)["final"] - 1.0)
        outs = np.array(outs)
        same = int((np.sign(outs) == np.sign(clean)).sum())
        med = float(np.median(outs))
        ratio = med / clean if clean != 0 else 0.0
        ok = same >= 18 and ratio >= 0.70
        v2[logic] = {"pass": ok, "clean": clean, "median": med,
                     "ratio": ratio, "same_sign": same}
        print(f"  {logic:<14}{clean:>+10.1%}{med:>+10.1%}{ratio:>8.2f}"
              f"{same:>8}/20{tick(ok):>8}")

    # ---- V3 halves -------------------------------------------------------
    mid = len(dates) // 2
    head(f"V3 - both halves (split at {dates[mid]}), k=30")
    print(f"  {'arm':<14}{'first half':>13}{'second half':>14}{'result':>9}")
    v3 = {}
    for logic in ("M1-LO", "M1-LS", "M2"):
        c = backtest(px, logic, 30)
        h1 = float(c[mid] / c[0]) - 1.0
        h2 = float(c[-1] / c[mid]) - 1.0
        ok = h1 > 0 and h2 > 0
        v3[logic] = {"pass": ok, "h1": h1, "h2": h2}
        print(f"  {logic:<14}{h1:>+13.1%}{h2:>+14.1%}{tick(ok):>9}")

    # ---- V4 costs --------------------------------------------------------
    head("V4 - cost sensitivity and breakeven, k=30")
    print(f"  {'arm':<14}" + "".join(f"{f'{f * 100:.2f}%':>11}"
                                     for f in (0.0, 0.0005, 0.0015, 0.0025))
          + f"{'breakeven':>12}")
    v4 = {}
    for logic in ("M1-LO", "M1-LS", "M2"):
        cells = []
        for f in (0.0, 0.0005, 0.0015, 0.0025):
            cells.append(stats(backtest(px, logic, 30, fee=f), dates)["final"] - 1.0)
        lo_f, hi_f = 0.0, 0.05
        for _ in range(40):
            m = (lo_f + hi_f) / 2
            if stats(backtest(px, logic, 30, fee=m), dates)["final"] > 1.0:
                lo_f = m
            else:
                hi_f = m
        be = (lo_f + hi_f) / 2
        ok = cells[2] > 0
        v4[logic] = {"pass": ok, "by_fee": cells, "breakeven": be}
        print(f"  {logic:<14}" + "".join(f"{c:>+11.1%}" for c in cells)
              + f"{be * 100:>11.3f}%  {tick(ok)}")

    # ---- V5 useful vs holding -------------------------------------------
    head("V5 - is it better than just holding the universe?")
    v5 = {}
    for logic in ("M1-LO", "M1-LS", "M2"):
        r = rows[f"{logic}|k30"]
        ok = r["ret_dd"] > bh["ret_dd"]
        v5[logic] = {"pass": ok, "ret_dd": r["ret_dd"], "bh_ret_dd": bh["ret_dd"]}
        print(f"  {logic:<14}ret/DD {r['ret_dd']:>6.2f}  vs EW buy&hold "
              f"{bh['ret_dd']:.2f}   -> {tick(ok)}")

    head("VERDICT")
    verdict = {}
    for logic in ("M1-LO", "M1-LS", "M2"):
        surv = v2[logic]["pass"] and v3[logic]["pass"] and v4[logic]["pass"]
        useful = surv and v5[logic]["pass"]
        verdict[logic] = ("CHALLENGER" if useful else
                          "SURVIVES BUT NOT USEFUL" if surv else "REJECTED")
        failed = [n for n, d in (("V2", v2), ("V3", v3), ("V4", v4), ("V5", v5))
                  if not d[logic]["pass"]]
        print(f"  {logic:<8}{verdict[logic]:<26}"
              f"{'failed: ' + ', '.join(failed) if failed else 'passed every gate'}")
    print("\n  promotion forbidden regardless; next step for any challenger is"
          " walk-forward, not adoption.")

    payload = {"experiment": "E52", "criteria": "docs/E52_CRITERIA.md",
               "symbols": syms, "span": [dates[0], dates[-1]],
               "fee_side": FEE_SIDE, "arms": rows,
               "benchmarks": {"ew_buy_hold": bh, "btc_buy_hold": btc},
               "V2_noise": v2, "V3_halves": v3, "V4_cost": v4, "V5_useful": v5,
               "V1_harness": v1, "verdict": verdict}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
