"""Meta-analysis across the recorded experiments — no new backtest, no tuning.

Reads only artefacts that already exist in `docs/` and `results/` and recomputes
decompositions that the individual experiment reports did not ask for:

  1. AOT grid (E26-E29): regress OOS alpha on the market's own return.
  2. AOT grid vs a *risk-matched* benchmark (static asset/cash split).
  3. BTC directional (E30): per-window matrix, correlation, up/down capture,
     bootstrap CI on the difference vs buy-and-hold, and the same difference
     measured against a de-levered buy-and-hold at matched drawdown.
  4. E30 held-out ETH/SOL, benchmarked against those assets' own buy-and-hold.
  5. Crypto leverage (E31): correlation, geometric growth, and the
     growth-optimal static sleeve fraction.

Nothing here promotes anything or changes a gate. Every number below is a
re-reading of a run that is already in `docs/VALIDATION_LOG.md`.

Run:  python meta_analysis_demo.py
"""

from __future__ import annotations

import json
import math
import os
import random
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
MODE = "CONSERVATIVE_OHLC"
BOOTSTRAP = 20_000
SEED = 11


def load(rel: str):
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return json.load(fh)


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else float("nan")


def ols(x, y):
    mx, my = st.mean(x), st.mean(y)
    slope = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    return slope, my - slope * mx


def r2(x, y):
    slope, icpt = ols(x, y)
    resid = sum((c - (icpt + slope * d)) ** 2 for d, c in zip(x, y))
    total = sum((c - st.mean(y)) ** 2 for c in y)
    return 1 - resid / total


def boot_ci(sample, rng, b=BOOTSTRAP):
    means = sorted(st.mean([rng.choice(sample) for _ in sample]) for _ in range(b))
    return means[int(0.025 * b)], means[int(0.975 * b)]


def cagr(returns, years):
    if min(returns) <= -1:
        return float("nan")
    return math.prod(1 + r for r in returns) ** (1 / years) - 1


def head(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------------- #
# 1-2. AOT grid: what is the grid actually a function of?
# --------------------------------------------------------------------------- #
def aot():
    e26 = load("docs/aot-walkforward-e26.json")
    folds = e26["folds"]
    bh = [f["oos"][MODE]["buyAndHoldReturn"] for f in folds]
    grid = [f["oos"][MODE]["totalReturn"] for f in folds]
    gdd = [f["oos"][MODE]["maxDrawdown"] for f in folds]
    bdd = [f["buyAndHoldDrawdown"] for f in folds]
    alpha = [f["oos"][MODE]["alpha"] for f in folds]

    head("1. AOT grid (E26, 18 OOS folds): the grid as a function of the market")
    slope, icpt = ols(bh, grid)
    print(f"   grid return = {slope:.3f} * buy&hold + {icpt:.2f}      R^2 = {r2(bh, grid):.3f}")
    sd, id_ = ols(bdd, gdd)
    print(f"   grid maxDD  = {sd:.3f} * buy&hold maxDD + {id_:.2f}   R^2 = {r2(bdd, gdd):.3f}")
    print(f"   corr(alpha, market return) = {corr(bh, alpha):.3f}")
    sa, ia = ols(bh, alpha)
    print(f"   alpha turns negative once the market returns more than {-ia / sa:.1f}%")

    med = st.median(bh)
    for label, idx in (
        ("quiet / down half", [i for i in range(len(bh)) if bh[i] < med]),
        ("strong-up half   ", [i for i in range(len(bh)) if bh[i] >= med]),
    ):
        wins = sum(1 for i in idx if alpha[i] > 0)
        print(f"   {label}: mean market {st.mean([bh[i] for i in idx]):7.1f}%  "
              f"mean alpha {st.mean([alpha[i] for i in idx]):7.2f}  beats B&H {wins}/{len(idx)}")

    head("2. AOT grid vs a RISK-MATCHED benchmark (static asset/cash split)")
    f = st.mean(gdd) / st.mean(bdd)
    half_r = [f * x for x in bh]
    half_d = [f * x for x in bdd]
    print(f"   grid mean maxDD {st.mean(gdd):.2f}% = {f:.3f} x buy&hold maxDD {st.mean(bdd):.2f}%")
    print(f"   grid        : ret {st.mean(grid):6.2f}%  DD {st.mean(gdd):6.2f}%  "
          f"robust {st.mean([r - 2 * d for r, d in zip(grid, gdd)]):7.2f}")
    print(f"   {f:.0%} asset : ret {st.mean(half_r):6.2f}%  DD {st.mean(half_d):6.2f}%  "
          f"robust {st.mean([r - 2 * d for r, d in zip(half_r, half_d)]):7.2f}")
    edge = st.mean(grid) - st.mean(half_r)
    print(f"   edge of the whole grid machine over a static cash split: {edge:+.2f} pct pts")

    head("3. AOT variants E26-E29 (same 18 folds)")
    print(f"   {'':<5}{'ret':>8}{'alpha':>9}{'DD':>8}{'robust':>9}{'engaged':>9}{'beatB&H':>9}{'flatsurf':>10}")
    for tag in ("e26", "e27", "e28", "e29"):
        d = load(f"docs/aot-walkforward-{tag}.json")
        m = [x for x in d["modeResults"] if x["mode"] == MODE][0]
        print(f"   {tag.upper():<5}{m['meanReturn']:>7.2f}%{m['meanAlpha']:>9.2f}"
              f"{m['meanDrawdown']:>7.2f}%{m['meanRobust']:>9.2f}"
              f"{m['engagedPct']:>8.0f}%{m['beatsBuyHoldPct']:>8.0f}%{d['flatSurfacePct']:>9.1f}%")


# --------------------------------------------------------------------------- #
# 3-4. BTC directional
# --------------------------------------------------------------------------- #
def e30():
    rng = random.Random(SEED)
    d = load("docs/btc-directional-e30.json")
    pc = d["layer_a"]["per_candidate"]
    names = list(pc)
    short = [k.split("_")[0] for k in names]
    R = {k: [w["return"] for w in v] for k, v in pc.items()}
    DD = {k: [w["maxDD"] for w in v] for k, v in pc.items()}
    n = len(R[names[0]])
    years = n * 252 / 365.25
    b0r, b0d = R["B0_buy_hold"], DD["B0_buy_hold"]

    head("4. E30 BTC directional: up-capture vs down-capture (12 OOS windows)")
    up = [i for i in range(n) if b0r[i] > 0]
    dn = [i for i in range(n) if b0r[i] <= 0]
    bu, bd = st.mean([b0r[i] for i in up]), st.mean([b0r[i] for i in dn])
    print(f"   market: {len(up)} up windows (mean {bu:+.1%}), {len(dn)} down (mean {bd:+.1%})")
    print(f"   {'':<5}{'upCapture':>11}{'downCapture':>13}{'ratio':>8}{'CAGR':>8}{'meanDD':>9}")
    for k, s in zip(names, short):
        cu = st.mean([R[k][i] for i in up]) / bu
        cd = st.mean([R[k][i] for i in dn]) / bd
        ratio = cu / cd if cd else float("nan")
        print(f"   {s:<5}{cu:>10.0%}{cd:>12.0%}{ratio:>8.2f}"
              f"{cagr(R[k], years):>7.1%}{st.mean(DD[k]):>8.1%}")
    print("   (down-capture below 100% = lost less than the market; ratio > 1 = asymmetric)")

    head("5. E30 vs buy&hold, and vs a DE-LEVERED buy&hold at matched drawdown")
    print(f"   {'':<5}{'f':>6}{'logic':>9}{'B&H@f':>8}{'edge':>8}{'95% CI (bootstrap)':>24}{'wins':>7}")
    for k, s in zip(names, short):
        if k.startswith("B0"):
            continue
        f = st.mean(DD[k]) / st.mean(b0d)
        diff = [R[k][i] - f * b0r[i] for i in range(n)]
        lo, hi = boot_ci(diff, rng)
        wins = sum(1 for x in diff if x > 0)
        print(f"   {s:<5}{f:>6.2f}{st.mean(R[k]):>8.1%}{f * st.mean(b0r):>8.1%}"
              f"{st.mean(diff):>8.1%}   [{lo:>6.1%},{hi:>6.1%}]{wins:>5}/{n}")
    print("   raw (unmatched) difference vs full-size buy&hold:")
    for k, s in zip(names, short):
        if k.startswith("B0"):
            continue
        diff = [R[k][i] - b0r[i] for i in range(n)]
        lo, hi = boot_ci(diff, rng)
        print(f"   {s:<5}{'':>6}{st.mean(R[k]):>8.1%}{st.mean(b0r):>8.1%}"
              f"{st.mean(diff):>8.1%}   [{lo:>6.1%},{hi:>6.1%}]"
              f"{sum(1 for x in diff if x > 0):>5}/{n}")

    head("6. E30 held-out ETH/SOL, benchmarked against those assets' own buy&hold")
    ho = d["descriptive_held_out"]
    for sym, path in (("ETHUSDT", "data/ETHUSDT_1d.json"), ("SOLUSDT", "data/SOLUSDT_1d.json")):
        raw = load(path)
        close = [float(k[4]) for k in raw]
        low = [float(k[3]) for k in raw]
        high = [float(k[2]) for k in raw]
        start = 200
        peak, mdd = -1.0, 0.0
        for i in range(start, len(close)):
            peak = max(peak, high[i])
            mdd = max(mdd, (peak - low[i]) / peak)
        bret = (close[-1] / close[start]) * (1 - 0.0015) ** 2 - 1
        print(f"   {sym}  buy&hold {bret:+.1%}  maxDD {mdd:.1%}   (held-out window is a bear market)")
        for k, v in ho[sym]["results"].items():
            if v["n_trades"] == 0:
                print(f"      {k:<24}{'did not trade':>28}")
                continue
            print(f"      {k:<24}{v['return']:>8.1%}{v['maxDD']:>9.1%}"
                  f"   beats B&H return: {'YES' if v['return'] > bret else 'no ':>3}"
                  f"   lower DD: {'YES' if v['maxDD'] < mdd else 'no'}")

    head("7. E30 selection instability (Layer B) and metric instability")
    lb = d["layer_b"]
    print(f"   picking the best in-sample logic beat the average in {lb['picked_beat_average']}/{lb['n_folds']} folds")
    print(f"   and was genuinely the best in {lb['picked_was_best']}/{lb['n_folds']} (random = {1/5:.0%})")
    cont = d["descriptive_continuous"]
    print("   winner depends on how the question is asked:")
    print("      restart-every-window (Layer A): " +
          ", ".join(f"{k.split('_')[0]} {10000 * math.prod(1 + w['return'] for w in pc[k]):,.0f}"
                    for k in names))
    print("      one continuous path:            " +
          ", ".join(f"{k.split('_')[0]} {cont[k]['final_equity']:,.0f}" for k in names))


# --------------------------------------------------------------------------- #
# 5. Crypto leverage
# --------------------------------------------------------------------------- #
def e31():
    d = load("docs/crypto-leverage-e31.json")
    pc = d["per_candidate"]
    names = list(pc)
    short = [k.split("_")[0] for k in names]
    R = {k: [w["annual"] for w in v] for k, v in pc.items()}
    DD = {k: [w["maxDD"] for w in v] for k, v in pc.items()}
    n = len(R[names[0]])

    head("8. E31 crypto: median hides the ruin, mean hides the median, CAGR tells the truth")
    print(f"   {'':<5}{'median':>9}{'mean':>9}{'CAGR':>9}{'worstDD':>9}{'ruined':>8}")
    for k, s in zip(names, short):
        print(f"   {s:<5}{st.median(R[k]):>9.0%}{st.mean(R[k]):>9.0%}{cagr(R[k], n):>9.1%}"
              f"{max(DD[k]):>9.0%}{sum(1 for w in pc[k] if w['ruined']):>8}")

    head("9. E31 growth-optimal static sleeve fraction (rest in cash, annual reset)")
    print("   HYPOTHESIS GENERATION ONLY — this fraction was chosen after seeing the data.")
    print(f"   {'':<5}{'f*':>6}{'CAGR@f*':>10}{'CAGR@100%':>11}{'worstDD@f*':>12}")
    for k, s in zip(names, short):
        best = (None, -9.0)
        for i in range(1, 21):
            f = i / 20
            scaled = [f * x for x in R[k]]
            if min(scaled) <= -1:
                continue
            g = cagr(scaled, n)
            if g > best[1]:
                best = (f, g)
        if best[0] is None:
            print(f"   {s:<5}{'ruined at every fraction':>39}")
            continue
        full = cagr(R[k], n)
        print(f"   {s:<5}{best[0]:>6.2f}{best[1]:>10.1%}"
              f"{(f'{full:.1%}' if full == full else 'ruined'):>11}"
              f"{max(best[0] * x for x in DD[k]):>12.0%}")


def main():
    print("Meta-analysis of recorded experiments — no new run, no tuning, no promotion.")
    aot()
    e30()
    e31()
    head("Standing constraints (unchanged)")
    print("   ValidationGate criteria C1-C7 are untouched. Nothing here is promoted.")
    print("   No live trading. Every hypothesis surfaced here needs its own")
    print("   pre-declared criteria and its own held-out data before it means anything.")


if __name__ == "__main__":
    main()
