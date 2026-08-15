"""E54 - ten specialist candidates, one harness, gates declared before they existed.

Criteria: `docs/E54_CRITERIA.md`. Run:

    python e54_bakeoff.py

G6 is the gate the whole design turns on. Testing ten candidates and keeping the
best produces a winner even when none of them has an edge, so each candidate is
paired with placebos of its own turnover and the bar every candidate must clear
is the maximum over ALL candidates' placebos. More candidates, higher bar.
"""

import json
import os

import numpy as np

from dynamic_grid import bakeoff as bk
from dynamic_grid.candidates_e54 import CANDIDATES, params_for

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "bakeoff-e54.json")

M1LS_REF = {"cagr": 0.715, "dd": 0.509}


def head(t):
    print("\n" + "=" * 104)
    print(t)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def m1ls_weights(data, p):
    """The incumbent, used as G1's harness check and as a benchmark."""
    C, R, live = data["C"], data["R"], data["live"]
    k, vw = 30, 20
    n_t, n_s = C.shape
    past = np.vstack([np.full((k, n_s), np.nan), C[:-k]])
    with np.errstate(invalid="ignore", divide="ignore"):
        mom = C / past - 1.0
    vol = bk.rolling_std(R, vw)
    ok = live & np.isfinite(mom) & np.isfinite(vol) & (vol > 0)
    side = np.where(mom > 0, 1.0, -1.0)
    W = np.where(ok, side / np.where(vol > 0, vol, np.inf), 0.0)
    W[(ok.sum(axis=1) < 5)] = 0.0
    return bk.normalise_rows(W)


def main():
    head("E54 - ten specialist candidates | criteria docs/E54_CRITERIA.md")
    dates, syms, O, H, L, C, V = bk.load_panel()
    F = bk.load_funding(dates, syms)
    data = bk.build_data(O, H, L, C, V, F, dates, syms)
    n_t = len(dates)
    print(f"  {len(syms)} symbols, {n_t} days, {dates[0]} -> {dates[-1]}")
    print(f"  cost {bk.FEE_SIDE * 100:.2f}%/side + real perp funding, gross <= 1.0")

    # ---- G1 harness -------------------------------------------------------
    Wm = m1ls_weights(data, None)
    ref = bk.curve_stats(bk.simulate(Wm, data, 7, funding=False)[1:], n_t - 1)
    g1 = (abs(ref["cagr"] - M1LS_REF["cagr"]) <= 0.005
          and abs(ref["maxDD"] - M1LS_REF["dd"]) <= 0.005)
    print(f"\n  G1 harness: M1-LS rebuilt here -> CAGR {ref['cagr']:+.1%} / "
          f"DD {ref['maxDD']:.1%} (E52 +71.5% / 50.9%)   -> {tick(g1)}")
    if not g1:
        print("  STOP per criteria section 3.")
        return 1

    m1 = bk.curve_stats(bk.simulate(Wm, data, 7)[1:], n_t - 1)
    ewW = bk.normalise_rows(np.where(data["live"], 1.0, 0.0))
    ew = bk.curve_stats(bk.simulate(ewW, data, 7, fee=0.0, funding=False)[1:], n_t - 1)

    pool = bk.vendor_noise_pool()
    print(f"  vendor noise pool {len(pool):,} measured diffs, median "
          f"|d| {np.median(np.abs(pool)):.3%}")

    # ---- run every candidate ---------------------------------------------
    rows, placebo_all = {}, []
    for name, spec in CANDIDATES.items():
        rebal = spec["rebal"]
        Wc = spec["fn"](data, params_for(name, spec["centre"]))
        daily = bk.simulate(Wc, data, rebal)
        st = bk.curve_stats(daily[1:], n_t - 1)
        turn = bk.mean_turnover(Wc, rebal)

        # G2 vendor noise
        outs = []
        for s in range(bk.NOISE_SEEDS):
            rng = np.random.default_rng(11000 + s)
            nd = bk.perturb(data, rng, pool)
            Wn = spec["fn"](nd, params_for(name, spec["centre"]))
            outs.append(bk.curve_stats(bk.simulate(Wn, nd, rebal)[1:], n_t - 1)["total"])
        outs = np.array(outs)
        same = int((np.sign(outs) == np.sign(st["total"])).sum())
        ratio = float(np.median(outs) / st["total"]) if st["total"] != 0 else 0.0
        g2 = same >= bk.NOISE_SIGN_MIN and ratio >= bk.NOISE_RATIO_MIN

        # G3 halves
        mid = n_t // 2
        cur = np.cumprod(1.0 + daily[1:])
        h1 = float(cur[mid]) - 1.0
        h2 = float(cur[-1] / cur[mid]) - 1.0
        g3 = h1 > 0 and h2 > 0

        # G4 cost + funding already in `st`
        g4 = st["total"] > 0

        # G5 neighbourhood
        neigh = []
        for v in spec["neigh"]:
            Wv = spec["fn"](data, params_for(name, v))
            neigh.append(bk.curve_stats(bk.simulate(Wv, data, rebal)[1:],
                                        n_t - 1)["ret_dd"])
        base_rd = st["ret_dd"]
        g5 = (base_rd > 0 and all(x >= bk.NEIGHBOUR_FLOOR * base_rd for x in neigh))

        # G7 walk-forward, fixed parameters
        seg, a = [], max(400, 0)
        while a + bk.TRAIN + bk.TEST <= n_t:
            seg.append(daily[a + bk.TRAIN:a + bk.TRAIN + bk.TEST])
            a += bk.TEST
        wf = bk.curve_stats(np.concatenate(seg), sum(len(s) for s in seg)) if seg else None
        g7 = bool(wf and wf["total"] > 0)

        # placebos matched to this candidate's turnover
        pl = []
        for s in range(bk.PLACEBO_SEEDS):
            rng = np.random.default_rng(12000 + s)
            Wp = bk.placebo_weights(data, rebal, turn, rng)
            pl.append(bk.curve_stats(bk.simulate(Wp, data, rebal)[1:], n_t - 1)["ret_dd"])
        placebo_all.extend(pl)

        rows[name] = {"src": spec["src"], "rebal": rebal, "turnover": turn,
                      "stats": st, "neigh_ret_dd": neigh, "h1": h1, "h2": h2,
                      "noise": {"same": same, "ratio": ratio,
                                "median": float(np.median(outs))},
                      "wf": wf, "placebo": pl,
                      "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G7": g7}
        print(f"    {name:<12} done  CAGR {st['cagr']:+7.1%}  DD {st['maxDD']:5.1%}"
              f"  turnover {turn:.2f}")

    ceiling = float(np.max(placebo_all))
    head("G8 - every candidate, full span (never trimmed to the winners)")
    print(f"  {'candidate':<12}{'CAGR':>9}{'maxDD':>8}{'ret/DD':>9}{'1st half':>11}"
          f"{'2nd half':>11}{'noise':>8}{'WF':>9}")
    for n, r in rows.items():
        wf = f"{r['wf']['total']:+.0%}" if r["wf"] else "n/a"
        print(f"  {n:<12}{r['stats']['cagr']:>+9.1%}{r['stats']['maxDD']:>8.1%}"
              f"{r['stats']['ret_dd']:>9.1f}{r['h1']:>+11.0%}{r['h2']:>+11.0%}"
              f"{r['noise']['same']:>6}/20{wf:>9}")
    print(f"  {'M1-LS (incumbent)':<12}{m1['cagr']:>+9.1%}{m1['maxDD']:>8.1%}"
          f"{m1['ret_dd']:>9.1f}")
    print(f"  {'EW buy&hold':<12}{ew['cagr']:>+9.1%}{ew['maxDD']:>8.1%}{ew['ret_dd']:>9.1f}")

    head("G6 - the placebo ceiling rises with the number of candidates")
    print(f"  {len(placebo_all)} placebos across {len(rows)} candidates")
    print(f"  median {np.median(placebo_all):.1f} | p90 "
          f"{np.percentile(placebo_all, 90):.1f} | **ceiling (max) {ceiling:.1f}**")

    head("Gate results")
    print(f"  {'candidate':<12}{'G2':>5}{'G3':>5}{'G4':>5}{'G5':>5}{'G6':>5}{'G7':>5}"
          f"   verdict")
    survivors = []
    for n, r in rows.items():
        g6 = r["stats"]["ret_dd"] > ceiling
        r["G6"] = g6
        passed = all(r[g] for g in ("G2", "G3", "G4", "G5", "G6", "G7"))
        if passed:
            survivors.append(n)
        failed = [g for g in ("G2", "G3", "G4", "G5", "G6", "G7") if not r[g]]
        print(f"  {n:<12}" + "".join(f"{'ok' if r[g] else 'X':>5}"
                                     for g in ("G2", "G3", "G4", "G5", "G6", "G7"))
              + ("   SURVIVES" if passed else f"   failed {', '.join(failed)}"))

    head("VERDICT")
    if survivors:
        print(f"  survivors: {', '.join(survivors)}")
        print("  reported as equal survivors - the criteria forbid ranking them.")
        print("  promotion still forbidden; next step is execution and slippage.")
    else:
        print("  NO CANDIDATE SURVIVES.")
        print("  Ten specialists, ten mechanisms, one shared harness: none cleared")
        print("  the gates once the placebo ceiling was raised to match the search.")

    payload = {"experiment": "E54", "criteria": "docs/E54_CRITERIA.md",
               "symbols": syms, "span": [dates[0], dates[-1]],
               "G1_harness": g1, "placebo_ceiling": ceiling,
               "benchmarks": {"M1-LS": m1, "EW": ew},
               "candidates": {n: {k: v for k, v in r.items() if k != "placebo"}
                              for n, r in rows.items()},
               "survivors": survivors,
               "verdict": "SURVIVORS" if survivors else "NONE"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
