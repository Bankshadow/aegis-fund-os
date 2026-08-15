"""E53 - walk-forward optimisation of M1-LS, and whether optimising pays at all.

Criteria declared in `docs/E53_CRITERIA.md` BEFORE this file existed. Run:

    python e53_walkforward.py

The deliverable is not the best parameter set. Every arm here picks parameters a
different way - best-on-train, fixed, median-on-train, and random - so the
reported number is what the *act of choosing* was worth, measured against a
placebo the way E48 taught us to.

Weights depend only on prices, never on equity, so each grid point's daily
returns can be computed once and the walk-forward blocks spliced out of them.
"""

import datetime as dt
import json
import os

import numpy as np

import e52_momentum as m
from e52_momentum import panel, stats

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs", "walkforward-e53.json")
FUNDING = os.path.join(ROOT, "data", "universe", "funding_daily.json")

KS = (14, 21, 30, 45, 60, 90)
VOLS = (10, 20, 40)
REBALS = (3, 7, 14)
FIXED = (30, 20, 7)
FEE = 0.0015
TRAIN, TEST = 730, 182
SEEDS = 20
E52_REF = {"cagr": 0.715, "dd": 0.509}


def head(title):
    print("\n" + "=" * 104)
    print(title)
    print("=" * 104)


def tick(ok):
    return "PASS" if ok else "FAIL"


def funding_matrix(dates, syms):
    with open(FUNDING, encoding="utf-8") as fh:
        fd = json.load(fh)
    F = np.zeros((len(dates), len(syms)))
    for j, s in enumerate(syms):
        tab = fd.get(s, {})
        for i, d in enumerate(dates):
            F[i, j] = tab.get(d, 0.0)
    return F


def daily_returns(px, k, vol_win, rebal, F=None, fee=FEE):
    """M1-LS daily net return series. Identical weighting rule to E52."""
    n_t, n_s = px.shape
    w = np.zeros(n_s)
    out = np.zeros(n_t)
    with np.errstate(invalid="ignore", divide="ignore"):
        rets = np.vstack([np.full((1, n_s), np.nan), np.diff(np.log(px), axis=0)])

    for t in range(1, n_t):
        r = float(w @ np.nan_to_num(np.exp(rets[t]) - 1.0, nan=0.0))
        if F is not None:
            r -= float(w @ F[t])
        cost = 0.0
        if t % rebal == 0 and t > max(k, vol_win):
            past = px[t - k, :]
            live = np.isfinite(px[t]) & np.isfinite(past) & (past > 0)
            mom = np.where(live, px[t] / np.where(past > 0, past, 1.0) - 1.0, np.nan)
            win = rets[t - vol_win + 1:t + 1]
            sig = np.where(np.isfinite(win).all(axis=0), np.nanstd(win, axis=0), np.nan)
            live &= np.isfinite(sig) & (sig > 0)
            new = np.zeros(n_s)
            if live.sum() >= 5:
                side = np.where(mom > 0, 1.0, -1.0)
                raw = np.where(live, side / np.where(sig > 0, sig, np.inf), 0.0)
                g = np.abs(raw).sum()
                if g > 0:
                    new = raw / g * m.GROSS
            cost = float(np.abs(new - w).sum()) * fee
            w = new
        out[t] = (1.0 + r) * (1.0 - cost) - 1.0
    return out


def score(seg):
    """The declared selection metric: return / maxDD on the segment."""
    curve = np.cumprod(1.0 + seg)
    if curve[-1] <= 0:
        return -1e9
    peak = np.maximum.accumulate(curve)
    dd = float(((peak - curve) / peak).max())
    return (curve[-1] - 1.0) / dd if dd > 1e-9 else (curve[-1] - 1.0) * 1e3


def curve_stats(seg, days):
    curve = np.cumprod(1.0 + seg)
    final = float(curve[-1])
    peak = np.maximum.accumulate(curve)
    dd = float(((peak - curve) / peak).max())
    years = days / 365.25
    return {"final": final, "maxDD": dd,
            "cagr": final ** (1 / years) - 1 if final > 0 and years > 0 else -1.0,
            "ret_dd": (final - 1) / dd if dd > 0 else 0.0}


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    d = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra @ rb) / d) if d > 0 else 0.0


def main():
    head("E53 - walk-forward optimisation of M1-LS | criteria docs/E53_CRITERIA.md")
    dates, syms, px = panel()
    F = funding_matrix(dates, syms)
    grid = [(k, v, r) for k in KS for v in VOLS for r in REBALS]
    print(f"  {len(syms)} symbols, {len(dates)} days | grid {len(grid)} parameter sets")
    print(f"  base cost {FEE * 100:.2f}%/side + real perp funding")

    # ---- P1 harness: reproduce E52 exactly (no funding, as E52 ran it) -----
    fix_nf = daily_returns(px, *FIXED, F=None)
    s = curve_stats(fix_nf[1:], len(dates) - 1)
    p1 = abs(s["cagr"] - E52_REF["cagr"]) <= 0.005 and abs(s["maxDD"] - E52_REF["dd"]) <= 0.005
    print(f"\n  P1 harness: fixed k=30/vol20/rebal7, no funding -> CAGR {s['cagr']:+.1%}"
          f" / DD {s['maxDD']:.1%} (E52 +71.5% / 50.9%)   -> {tick(p1)}")
    if not p1:
        print("  STOP per criteria section 5.")
        return 1

    print(f"  computing {len(grid)} return series (weights never depend on equity)...")
    R = np.vstack([daily_returns(px, k, v, r, F=F) for k, v, r in grid])

    # ---- P6 the grid, full span ------------------------------------------
    full = [curve_stats(R[i][1:], len(dates) - 1) for i in range(len(grid))]
    order = np.argsort([-f["ret_dd"] for f in full])
    head("P6 - all 54 sets over the FULL span (in-sample; NOT a recommendation)")
    print(f"  {'rank':>5}{'k':>5}{'vol':>5}{'rebal':>7}{'CAGR':>10}{'maxDD':>9}{'ret/DD':>10}")
    for rank, i in enumerate(list(order[:5]) + list(order[-3:]), 1):
        k, v, r = grid[i]
        tag = "  <- E52 default" if (k, v, r) == FIXED else ""
        pos = rank if rank <= 5 else len(grid) - (8 - rank)
        print(f"  {pos:>5}{k:>5}{v:>5}{r:>7}{full[i]['cagr']:>+10.1%}"
              f"{full[i]['maxDD']:>9.1%}{full[i]['ret_dd']:>10.1f}{tag}")
    fi = grid.index(FIXED)
    print(f"  the E52 default (k30/v20/r7) ranks {list(order).index(fi) + 1}/{len(grid)}"
          f" on the full span, CAGR {full[fi]['cagr']:+.1%}")
    print(f"  spread across the grid: CAGR {min(f['cagr'] for f in full):+.1%}"
          f" .. {max(f['cagr'] for f in full):+.1%}")

    # ---- walk-forward blocks ---------------------------------------------
    warm = max(KS) + max(VOLS) + 5
    blocks = []
    a = warm
    while a + TRAIN + TEST <= len(dates):
        blocks.append((a, a + TRAIN, a + TRAIN + TEST))
        a += TEST
    print(f"\n  walk-forward: {len(blocks)} blocks, train {TRAIN}d -> test {TEST}d, "
          f"first test starts {dates[blocks[0][1]]}")

    rng_pool = [np.random.default_rng(9000 + s) for s in range(SEEDS)]
    arms = {"W-OPT": [], "W-FIX": [], "W-MED": []}
    rnd = [[] for _ in range(SEEDS)]
    picks, rhos = [], []

    for b0, b1, b2 in blocks:
        tr = [score(R[i][b0:b1]) for i in range(len(grid))]
        te = [score(R[i][b1:b2]) for i in range(len(grid))]
        rhos.append(spearman(np.array(tr), np.array(te)))
        rank = np.argsort([-x for x in tr])
        best, med = int(rank[0]), int(rank[len(rank) // 2])
        picks.append(grid[best])
        arms["W-OPT"].append(R[best][b1:b2])
        arms["W-FIX"].append(R[fi][b1:b2])
        arms["W-MED"].append(R[med][b1:b2])
        for s in range(SEEDS):
            rnd[s].append(R[int(rng_pool[s].integers(0, len(grid)))][b1:b2])

    days = sum(b2 - b1 for _, b1, b2 in blocks)
    res = {a: curve_stats(np.concatenate(v), days) for a, v in arms.items()}
    rnd_stats = [curve_stats(np.concatenate(v), days) for v in rnd]

    head("P2 / P3 / P4 - the chained out-of-sample path")
    print(f"  {'arm':<10}{'CAGR':>10}{'maxDD':>9}{'ret/DD':>10}{'$10k ->':>12}")
    for a in ("W-OPT", "W-FIX", "W-MED"):
        print(f"  {a:<10}{res[a]['cagr']:>+10.1%}{res[a]['maxDD']:>9.1%}"
              f"{res[a]['ret_dd']:>10.1f}{res[a]['final'] * 10000:>12,.0f}")
    rr = np.array([x["ret_dd"] for x in rnd_stats])
    rc = np.array([x["cagr"] for x in rnd_stats])
    p90 = float(np.percentile(rr, 90))
    print(f"  {'W-RND':<10}{np.median(rc):>+10.1%}{'':>9}{np.median(rr):>10.1f}"
          f"{np.median([x['final'] for x in rnd_stats]) * 10000:>12,.0f}  (median of 20)")
    print(f"             random ret/DD: min {rr.min():.1f}  median {np.median(rr):.1f}"
          f"  p90 {p90:.1f}  max {rr.max():.1f}")

    p2 = res["W-OPT"]["ret_dd"] > res["W-FIX"]["ret_dd"]
    p3 = res["W-OPT"]["ret_dd"] > p90
    p4 = res["W-OPT"]["ret_dd"] > res["W-MED"]["ret_dd"]
    beat = int((rr >= res["W-OPT"]["ret_dd"]).sum())
    print(f"\n  P2 W-OPT {res['W-OPT']['ret_dd']:.1f} vs W-FIX {res['W-FIX']['ret_dd']:.1f}"
          f"   -> {tick(p2)}")
    print(f"  P3 W-OPT vs random p90 {p90:.1f}   -> {tick(p3)}"
          f"   ({beat}/{SEEDS} random seeds matched or beat it)")
    print(f"  P4 W-OPT vs W-MED {res['W-MED']['ret_dd']:.1f}   -> {tick(p4)}")

    head("P5 / P7 - was the past ever informative about the future?")
    changes = sum(1 for i in range(1, len(picks)) if picks[i] != picks[i - 1])
    print(f"  P5 chosen set changed {changes}/{len(picks) - 1} times between blocks")
    print(f"     picks: {' '.join(str(p) for p in picks)}")
    rhos = np.array(rhos)
    print(f"  P7 Spearman(train rank, test rank) per block:")
    print(f"     {'  '.join(f'{r:+.2f}' for r in rhos)}")
    print(f"     mean {rhos.mean():+.3f} | positive in {(rhos > 0).sum()}/{len(rhos)} blocks")

    helps = p2 and p3
    head(f"VERDICT: {'optimising pays' if helps else 'OPTIMISING DOES NOT PAY - fix the parameters'}")
    if not helps:
        print("  Per the decision table: recommendation is to fix k=30 and stop tuning.")
    if all(res[a]["final"] <= 1.0 for a in res):
        print("  Every arm lost on the chained OOS path: M1-LS does not survive"
              " walk-forward and the challenger label is withdrawn.")

    payload = {"experiment": "E53", "criteria": "docs/E53_CRITERIA.md",
               "grid": [list(g) for g in grid], "blocks": len(blocks),
               "train": TRAIN, "test": TEST, "fee": FEE, "funding": True,
               "full_span": {str(grid[i]): full[i] for i in range(len(grid))},
               "oos": res, "random": {"ret_dd": rr.tolist(), "p90": p90,
                                      "beat_opt": beat},
               "picks": [list(p) for p in picks],
               "spearman": rhos.tolist(),
               "checks": {"P1": p1, "P2": p2, "P3": p3, "P4": p4},
               "verdict": "OPTIMISING_PAYS" if helps else "FIX_THE_PARAMETERS"}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
