"""E33 diagnostics — why the declared setup failed, and what the control arm did.

Diagnostics only. E33's verdict is already recorded and does not change here.
Two questions:

  1. The screen was the one new mechanism in E33 and it cost 15.7 points of CAGR.
     Was it wrong about the assets it removed, or was it right and unlucky?
     Measured directly: forward returns of the names it dropped versus the names
     it kept, at the moment it dropped them.
  2. The control arm (same basket, screen disabled) is put through the SAME ten
     criteria. Choosing it after seeing E33's result would be exactly the
     E23-E25 mistake, so this is evidence about the control arm, not a promotion.

Run:  python e33_diag.py
"""

import json
import math
import os
import statistics as st

import numpy as np

from crypto_leverage_e31 import build_panel
from dynamic_grid import leveraged as lv
from dynamic_grid import trend_overlay as t
from e32_depth import Lagged, episodes, norm_cdf, norm_ppf, EULER
from stvb_e33 import EqualWeightHold, BURNED, derisked, head, pct, tick
from trend_leverage_e32 import _BuyHold, INITIAL, WARMUP, run

OUT = os.path.join(os.path.dirname(__file__), "docs", "stvb-e33-diag.json")
HORIZONS = (30, 90, 180)


def main():
    dates, symbols, closes, highs, lows, funding = build_panel()
    stats = t.Stats(closes)
    n = len(dates)
    btc = symbols.index("BTC")
    clean = [j for j, s in enumerate(symbols) if s not in BURNED]
    n_win = (n - WARMUP) // 365
    offset = n - n_win * 365
    rep = {}

    print("E33 diagnostics — the screen, and the control arm under the same ten tests")
    print(f"primary universe: {len(clean)} coins never used to design the mechanism\n")

    # ------------------------------------------------------------------ 1
    head("1. WAS THE SCREEN RIGHT? forward returns of what it dropped vs kept")
    print("   At every rebalance day, among names the three filters already voted")
    print("   long, split by whether the screen admitted them, then look forward.")
    gap = stats.conditional_gap(730, 200)
    probe = t.ScreenedTrendVoteBasket(stats, assets=clean, use_screen=False,
                                      rebalance=5)
    kept, dropped = {h: [] for h in HORIZONS}, {h: [] for h in HORIZONS}
    n_kept = n_drop = 0
    for i in range(offset, n - max(HORIZONS), 5):
        conv = probe._votes(i)
        for j in clean:
            if conv[j] <= 0 or np.isnan(closes[i, j]):
                continue
            g = gap[i, j]
            if np.isnan(g):
                continue
            admitted = g > 0
            if admitted:
                n_kept += 1
            else:
                n_drop += 1
            for h in HORIZONS:
                fut = closes[i + h, j]
                if np.isnan(fut):
                    continue
                r = fut / closes[i, j] - 1.0
                (kept if admitted else dropped)[h].append(r)
    print(f"   decisions: {n_kept} admitted, {n_drop} dropped "
          f"({n_drop / (n_kept + n_drop):.0%} of trend-positive names removed)")
    print(f"   {'horizon':<10}{'kept mean':>12}{'dropped mean':>15}"
          f"{'kept median':>14}{'dropped median':>17}{'screen right?':>16}")
    scr = {}
    for h in HORIZONS:
        k, d = kept[h], dropped[h]
        if not k or not d:
            continue
        right = st.mean(k) > st.mean(d)
        scr[h] = {"kept_mean": st.mean(k), "dropped_mean": st.mean(d),
                  "kept_median": st.median(k), "dropped_median": st.median(d),
                  "n_kept": len(k), "n_dropped": len(d), "right": bool(right)}
        print(f"   {h:>4}d     {pct(st.mean(k)):>12}{pct(st.mean(d)):>15}"
              f"{pct(st.median(k)):>14}{pct(st.median(d)):>17}"
              f"{('yes' if right else 'NO'):>16}")
    rep["screen_discrimination"] = scr
    print("\n   a screen that adds value must show kept > dropped. If it does not,")
    print("   the 15.7 points it cost were not a risk premium, they were a mistake.")

    # exposure the screen removed, by year
    print(f"\n   {'year':<10}{'exposure on':>14}{'exposure off':>15}{'removed':>10}")
    exp_rows = []
    for w in range(n_win):
        s0, e0 = offset + w * 365, offset + (w + 1) * 365
        a, ra = run(dates, closes, highs, lows, funding, symbols,
                    lambda: t.ScreenedTrendVoteBasket(stats, assets=clean,
                                                      use_screen=True),
                    lv.SPOT_COST, False, s0, e0)
        b, rb = run(dates, closes, highs, lows, funding, symbols,
                    lambda: t.ScreenedTrendVoteBasket(stats, assets=clean,
                                                      use_screen=False),
                    lv.SPOT_COST, False, s0, e0)
        exp_rows.append({"year": dates[s0][:7], "on": a["exposure"],
                         "off": b["exposure"]})
        print(f"   {dates[s0][:7]:<10}{pct(a['exposure'], 0):>14}"
              f"{pct(b['exposure'], 0):>15}{pct(b['exposure'] - a['exposure'], 0):>10}")
    rep["exposure_by_year"] = exp_rows

    # ------------------------------------------------------------------ 2
    head("2. THE CONTROL ARM UNDER THE SAME TEN CRITERIA")
    print("   Same basket, same weights, same cap, screen disabled. This arm was")
    print("   NOT the declared setup: reading it as a winner is post-hoc.\n")

    def arm():
        return t.ScreenedTrendVoteBasket(stats, assets=clean, use_screen=False,
                                         name="STVB_control_noscreen")

    m, res = run(dates, closes, highs, lows, funding, symbols, arm,
                 lv.SPOT_COST, False, offset, n)
    ew, _ = run(dates, closes, highs, lows, funding, symbols,
                lambda: EqualWeightHold(stats, clean), lv.SPOT_COST, False, offset, n)
    bh, _ = run(dates, closes, highs, lows, funding, symbols,
                lambda: _BuyHold(stats, btc), lv.SPOT_COST, False, offset, n)
    dr = derisked(closes, btc, offset, n, m["worst_dd"])
    print(f"   {'book':<26}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'Sharpe':>8}"
          f"{'Sortino':>9}{'expo':>7}{'TUW':>6}")
    for label, x in (("control arm", m), ("equal-weight B&H", ew), ("BTC B&H", bh)):
        print(f"   {label:<26}{pct(x['cagr'])}{pct(x['worst_dd'])}{x['mar']:>6.2f}"
              f"{x['sharpe']:>8.2f}{x['sortino']:>9.2f}"
              f"{pct(x['exposure'], 0):>7}{x['max_time_under_water']:>6}")
    print(f"   {'BTC de-risked to same DD':<26}{pct(dr['cagr'])}"
          f"{pct(m['worst_dd'])}{'':>6}{'':>8}{'':>9}{'':>7}   f = {dr['fraction']:.2f}")

    # windows
    beats = 0
    wr = []
    for w in range(n_win):
        s0, e0 = offset + w * 365, offset + (w + 1) * 365
        a, _ = run(dates, closes, highs, lows, funding, symbols, arm,
                   lv.SPOT_COST, False, s0, e0)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: EqualWeightHold(stats, clean), lv.SPOT_COST, False, s0, e0)
        wr.append({"year": dates[s0][:7], "arm": a["cagr"], "bench": b["cagr"],
                   "dd": a["worst_dd"]})
        beats += a["cagr"] > b["cagr"]
    print(f"\n   {'window':<12}{'control':>10}{'eq-wt B&H':>12}{'edge':>10}{'DD':>9}")
    for r in wr:
        print(f"   {r['year']:<12}{pct(r['arm']):>10}{pct(r['bench']):>12}"
              f"{pct(r['arm'] - r['bench']):>10}{pct(r['dd']):>9}")
    print(f"   beats benchmark {beats}/{n_win}")

    # concentration
    eps = [e[2] for e in episodes(res.gross_leverage, res.equity, INITIAL)]
    total = math.prod(1 + r for r in eps)
    srt = sorted(range(len(eps)), key=lambda k: eps[k], reverse=True)
    top1 = math.log1p(max(eps)) / math.log(total)
    yrs = m["days"] / t.TRADING_DAYS
    ex_best = math.prod(1 + eps[k] for k in range(len(eps)) if k != srt[0]) ** (1 / yrs) - 1
    print(f"\n   concentration: {len(eps)} stretches, best = {pct(top1, 0)} of log "
          f"growth, CAGR without it {pct(ex_best)} (bench {pct(ew['cagr'])})")

    # decay
    dec, s0 = [], offset
    while s0 + 730 <= n:
        a, _ = run(dates, closes, highs, lows, funding, symbols, arm,
                   lv.SPOT_COST, False, s0, s0 + 730)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: EqualWeightHold(stats, clean), lv.SPOT_COST, False,
                   s0, s0 + 730)
        dec.append(a["cagr"] - b["cagr"])
        s0 += 182
    h1, h2 = st.mean(dec[:len(dec) // 2]), st.mean(dec[len(dec) // 2:])
    print(f"   decay: rolling 2-year edge, first half {pct(h1)}, second half {pct(h2)}")

    # timing luck and lag
    cs = []
    for k in range(12):
        s0 = offset + k * 30
        if s0 + 365 * 5 > n:
            continue
        a, _ = run(dates, closes, highs, lows, funding, symbols, arm,
                   lv.SPOT_COST, False, s0, n)
        cs.append(a["cagr"])
    spread = max(cs) - min(cs)
    lags = []
    for L in (0, 1, 2, 3):
        def wrapped(LL=L):
            s = arm()
            return s if LL == 0 else Lagged(s, LL)
        a, _ = run(dates, closes, highs, lows, funding, symbols, wrapped,
                   lv.SPOT_COST, False, offset, n)
        lags.append(a["cagr"])
    print(f"   timing luck: median {pct(st.median(cs))} spread {pct(spread)}"
          f"   |   lag: " + " ".join(f"{pct(x)}" for x in lags))

    # deflated Sharpe, same family size as E33
    curve = np.concatenate(([INITIAL], res.equity))
    r = curve[1:] / curve[:-1] - 1.0
    mu, sd = r.mean(), r.std(ddof=1)
    skew = float(np.mean(((r - mu) / sd) ** 3))
    kurt = float(np.mean(((r - mu) / sd) ** 4))
    sr_d = mu / sd
    N = 34
    sd_sr = 0.180
    sr0 = sd_sr * ((1 - EULER) * norm_ppf(1 - 1.0 / N)
                   + EULER * norm_ppf(1 - 1.0 / (N * math.e)))
    denom = math.sqrt(max(1 - skew * sr_d + (kurt - 1) / 4 * sr_d ** 2, 1e-12))
    dsr = norm_cdf((sr_d - sr0 / math.sqrt(365.25)) * math.sqrt(len(r) - 1) / denom)
    print(f"   deflated Sharpe: SR {m['sharpe']:.3f}, skew {skew:+.2f}, "
          f"kurtosis {kurt:.1f}, SR0 {sr0:.3f} -> DSR {dsr:.3f}")

    H = {
        "H1 CAGR > equal-weight B&H": m["cagr"] > ew["cagr"],
        "H2 MAR > both benchmarks": m["mar"] > ew["mar"] and m["mar"] > bh["mar"],
        "H3 CAGR > de-risked B&H at same DD": m["cagr"] > dr["cagr"],
        "H4 no liquidation, no ruin": m["liquidations"] == 0 and not m["ruined"],
        "H5 beats benchmark >= 5/8 windows": beats >= 5,
        "H6 top-1 < 40% and ex-best still wins": top1 < 0.40 and ex_best > ew["cagr"],
        "H7 second-half edge >= 0": h2 >= 0,
        "H8 timing-luck spread < 15 pts": spread < 0.15,
        "H9 lag-1 loss < 3 pts": (lags[0] - lags[1]) < 0.03,
        "H10 deflated Sharpe >= 0.95": dsr >= 0.95,
    }
    print()
    for k, v in H.items():
        print(f"   {k:<44}{tick(v)}")
    failed = [k.split()[0] for k, v in H.items() if not v]
    print(f"\n   control arm: {'would clear all ten' if not failed else 'fails ' + ', '.join(failed)}")
    print("   This is NOT a pass. The arm was selected after seeing E33's result;")
    print("   a real pass requires pre-declaration on data not used above.")
    rep["control_arm"] = {"metrics": m, "bench": ew, "btc": bh, "derisked": dr,
                          "windows": wr, "beats": beats, "top1": top1,
                          "cagr_ex_best": ex_best, "decay": [h1, h2],
                          "timing_spread": spread, "lags": lags, "dsr": dsr,
                          "verdict": {k: bool(v) for k, v in H.items()}}

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, default=float)
    print(f"\nraw -> {os.path.relpath(OUT, os.path.dirname(__file__))}")


if __name__ == "__main__":
    main()
