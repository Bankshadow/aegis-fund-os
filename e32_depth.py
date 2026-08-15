"""E32 depth — the questions that decide whether the E32 numbers mean anything.

Diagnostics only. No criteria are declared, changed, or judged here; nothing is
promoted. Every section attacks one specific way a trend-following backtest is
usually wrong, using the same panel, engine and costs as E32.

  1. Mechanism    — does "above the 200-day average" actually predict anything,
                    or is the whole result an artefact of the equity path?
  2. Best/worst   — is the edge from dodging the worst days or from missing the
                    best ones? Both are always true; the ratio is the edge.
  3. Timing luck  — how much of the result is the accident of the start date?
  4. Decay        — is the edge dying as the market matures?
  5. Costs        — at what cost per side does it vanish? What about funding?
  6. Lag          — what if the fill is a day late, as it is in real life?
  7. Ensemble     — voting across filters instead of picking the best one, which
                    E30 §C7 showed is worth exactly as much as a coin flip.
  8. Episodes     — is it all two trades? Drop the best one and look again.
  9. Deflated SR  — after ~40 variants were looked at, what Sharpe would the
                    best of them show under the null of no skill at all?

Run:  python e32_depth.py
"""

import json
import math
import os
import statistics as st

import numpy as np

from crypto_leverage_e31 import build_panel
from dynamic_grid import leveraged as lv
from dynamic_grid import trend_overlay as t
from trend_leverage_e32 import _BuyHold, _Donchian, INITIAL, WARMUP, run

OUT = os.path.join(os.path.dirname(__file__), "docs", "trend-depth-e32.json")
EULER = 0.5772156649015329


def head(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def pct(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


def norm_ppf(p):
    """Inverse normal CDF (Acklam's rational approximation, |err| < 1.15e-9)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class Lagged:
    """Execute yesterday's decision today. The honest version of a daily system."""

    def __init__(self, inner, days=1):
        self.inner, self.days = inner, days
        self.queue = []
        self.name = f"{inner.name}_lag{days}"

    def weights(self, i):
        self.queue.append(self.inner.weights(i))
        if len(self.queue) <= self.days:
            return np.zeros_like(self.queue[0])
        return self.queue.pop(0)


class Ensemble:
    """Position = share of filters that are long. No filter is chosen."""

    def __init__(self, voters, leverage=1.0, name="ENS_vote"):
        # deliberately NOT called `parts`: that name means (strategy, share)
        # pairs to trend_leverage_e32.run, which would try to unpack it
        self.voters, self.lev, self.name = voters, leverage, name

    def weights(self, i):
        votes = [v.weights(i) for v in self.voters]
        stacked = np.sum([(v > 0).astype(float) for v in votes], axis=0)
        return self.lev * stacked / len(self.voters)


def episodes(gross, equity, initial):
    """Contiguous in-market stretches and the P&L of each."""
    curve = np.concatenate(([initial], equity))
    out, start = [], None
    g = np.asarray(gross)
    for i, x in enumerate(g):
        live = x > 1e-9
        if live and start is None:
            start = i
        elif not live and start is not None:
            out.append((start, i, curve[i] / curve[start] - 1.0))
            start = None
    if start is not None:
        out.append((start, len(g), curve[len(g)] / curve[start] - 1.0))
    return out


def main():
    dates, symbols, closes, highs, lows, funding = build_panel()
    btc = symbols.index("BTC")
    stats = t.Stats(closes)
    n = len(dates)
    n_win = (n - WARMUP) // 365
    offset = n - n_win * 365
    rep = {}

    print("E32 depth — nine ways this result could be fake, checked one at a time")
    print(f"panel: {len(symbols)} symbols, {n} days, {dates[0]} -> {dates[-1]}")
    print("diagnostics only: no criteria, no verdict, no promotion\n")

    # ------------------------------------------------------------------ 1
    head("1. MECHANISM — is the state actually predictive? (no strategy involved)")
    print("   For every day, classify by whether the close is above its own 200-day")
    print("   average, then look ONLY at the NEXT day's return. If the two buckets")
    print("   are the same, the filter is decoration.")
    print(f"   {'asset':<6}{'state':<8}{'days':>7}{'mean/day':>11}{'ann.mean':>10}"
          f"{'ann.vol':>9}{'Sharpe':>8}{'P(up)':>8}{'worst':>9}")
    cond = {}
    for sym in ("BTC", "ETH", "SOL"):
        if sym not in symbols:
            continue
        j = symbols.index(sym)
        c = closes[:, j]
        sma = stats.sma(200)[:, j]
        fwd = np.full(n, np.nan)
        fwd[:-1] = c[1:] / c[:-1] - 1.0
        above = (~np.isnan(c)) & (~np.isnan(sma)) & (c > sma) & (~np.isnan(fwd))
        below = (~np.isnan(c)) & (~np.isnan(sma)) & (c <= sma) & (~np.isnan(fwd))
        row = {}
        for label, mask in (("above", above), ("below", below)):
            r = fwd[mask]
            if len(r) < 30:
                continue
            m, sd = float(r.mean()), float(r.std(ddof=1))
            ann_m = (1 + m) ** 365.25 - 1
            ann_v = sd * math.sqrt(365.25)
            row[label] = {"days": int(len(r)), "mean": m, "ann_mean": ann_m,
                          "ann_vol": ann_v, "sharpe": m / sd * math.sqrt(365.25),
                          "p_up": float((r > 0).mean()), "worst": float(r.min())}
            print(f"   {sym:<6}{label:<8}{len(r):>7}{m * 100:>10.3f}%"
                  f"{pct(ann_m):>10}{pct(ann_v):>9}"
                  f"{row[label]['sharpe']:>8.2f}{pct(row[label]['p_up'], 0):>8}"
                  f"{pct(row[label]['worst']):>9}")
        cond[sym] = row
        if "above" in row and "below" in row:
            print(f"   {'':6}{'-> gap':<8}{'':>7}"
                  f"{(row['above']['mean'] - row['below']['mean']) * 100:>10.3f}%"
                  f"{'':>10}{pct(row['above']['ann_vol'] - row['below']['ann_vol']):>9}")
    rep["conditional_state"] = cond
    print("\n   read: the return gap is the smaller half of the story; the VOLATILITY")
    print("   gap is what a trend filter is really harvesting.")

    # ------------------------------------------------------------------ 2
    head("2. BEST DAYS vs WORST DAYS — what the filter is actually dodging")
    print(f"   {'asset':<6}{'worst 20 days out':>20}{'best 20 days out':>19}"
          f"{'ratio':>8}{'worst-50 out':>14}{'best-50 out':>13}")
    bw = {}
    for sym in ("BTC", "ETH", "SOL"):
        if sym not in symbols:
            continue
        j = symbols.index(sym)
        c = closes[:, j]
        sma = stats.sma(200)[:, j]
        fwd = np.full(n, np.nan)
        fwd[:-1] = c[1:] / c[:-1] - 1.0
        ok = (~np.isnan(fwd)) & (~np.isnan(sma)) & (~np.isnan(c))
        idx = np.flatnonzero(ok)
        order = idx[np.argsort(fwd[idx])]
        out_of_market = c[idx] <= sma[idx]
        pos = {k: i for i, k in enumerate(idx)}
        def share(sel):
            return float(np.mean([out_of_market[pos[k]] for k in sel]))
        w20, b20 = share(order[:20]), share(order[-20:])
        w50, b50 = share(order[:50]), share(order[-50:])
        bw[sym] = {"worst20_out": w20, "best20_out": b20,
                   "worst50_out": w50, "best50_out": b50,
                   "ratio": w20 / b20 if b20 else float("inf")}
        print(f"   {sym:<6}{pct(w20, 0):>20}{pct(b20, 0):>19}"
              f"{bw[sym]['ratio']:>8.2f}{pct(w50, 0):>14}{pct(b50, 0):>13}")
    rep["best_worst_days"] = bw
    print("\n   a ratio above 1 means the filter sits out more of the disasters than")
    print("   of the fireworks. That asymmetry, not prediction, is the whole edge.")

    # ------------------------------------------------------------------ 3
    head("3. TIMING LUCK — same strategy, twelve different start dates")
    print("   one month of start-date shift is not a different strategy. If the")
    print("   result moves a lot, the number you were shown was an accident.")
    print(f"   {'engine':<24}{'median CAGR':>13}{'min':>9}{'max':>9}"
           f"{'spread':>9}{'median DD':>11}")
    luck = {}
    engines = [
        ("BTC buy & hold", lambda: _BuyHold(stats, btc), lv.SPOT_COST, False),
        ("SMA-200 1x", lambda: t.SmaRegime(stats, btc, 200, 1.0, "s1"), lv.SPOT_COST, False),
        ("Donchian-55 1x", lambda: _Donchian(stats, btc, 55, 1.0), lv.SPOT_COST, False),
        ("Donchian-55 2x", lambda: _Donchian(stats, btc, 55, 2.0), lv.PERP_COST, True),
    ]
    for label, build, cost, use_f in engines:
        cs, dds = [], []
        for k in range(12):
            s0 = offset + k * 30
            if s0 + 365 * 5 > n:
                continue
            m, _ = run(dates, closes, highs, lows, funding, symbols, build,
                       cost, use_f, s0, n)
            cs.append(m["cagr"])
            dds.append(m["worst_dd"])
        luck[label] = {"cagrs": cs, "median": st.median(cs), "min": min(cs),
                       "max": max(cs), "spread": max(cs) - min(cs),
                       "median_dd": st.median(dds)}
        print(f"   {label:<24}{pct(st.median(cs)):>13}{pct(min(cs)):>9}"
              f"{pct(max(cs)):>9}{pct(max(cs) - min(cs)):>9}{pct(st.median(dds)):>11}")
    rep["timing_luck"] = luck

    # ------------------------------------------------------------------ 4
    head("4. DECAY — rolling two-year edge over buy & hold")
    print(f"   {'window':<22}{'B&H CAGR':>11}{'SMA-200':>10}{'Donchian':>10}"
          f"{'edge SMA':>10}{'edge Donch':>12}")
    decay = []
    step = 182
    span = 730
    s0 = offset
    while s0 + span <= n:
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _BuyHold(stats, btc), lv.SPOT_COST, False, s0, s0 + span)
        a, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: t.SmaRegime(stats, btc, 200, 1.0, "s1"), lv.SPOT_COST,
                   False, s0, s0 + span)
        d, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _Donchian(stats, btc, 55, 1.0), lv.SPOT_COST, False,
                   s0, s0 + span)
        decay.append({"start": dates[s0], "end": dates[s0 + span - 1],
                      "bh": b["cagr"], "sma": a["cagr"], "don": d["cagr"]})
        print(f"   {dates[s0][:7]}..{dates[s0 + span - 1][:7]:<11}{pct(b['cagr']):>11}"
              f"{pct(a['cagr']):>10}{pct(d['cagr']):>10}"
              f"{pct(a['cagr'] - b['cagr']):>10}{pct(d['cagr'] - b['cagr']):>12}")
        s0 += step
    first_half = decay[:len(decay) // 2]
    second_half = decay[len(decay) // 2:]
    for nm, key in (("SMA-200", "sma"), ("Donchian-55", "don")):
        e1 = st.mean(x[key] - x["bh"] for x in first_half)
        e2 = st.mean(x[key] - x["bh"] for x in second_half)
        print(f"   {nm}: mean edge first half {pct(e1)}  second half {pct(e2)}"
              f"   change {pct(e2 - e1)}")
    rep["decay"] = decay

    # ------------------------------------------------------------------ 5
    head("5. COST AND FUNDING SENSITIVITY — where does the edge die?")
    print(f"   {'cost/side':<12}{'SMA-200 1x':>13}{'Donchian 1x':>14}"
          f"{'Donchian 2x':>14}{'B&H':>9}")
    costs = {}
    for c in (0.0, 0.0005, 0.0010, 0.0015, 0.0030, 0.0050, 0.0100):
        a, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: t.SmaRegime(stats, btc, 200, 1.0, "s1"), c, False, offset, n)
        d1, _ = run(dates, closes, highs, lows, funding, symbols,
                    lambda: _Donchian(stats, btc, 55, 1.0), c, False, offset, n)
        d2, _ = run(dates, closes, highs, lows, funding, symbols,
                    lambda: _Donchian(stats, btc, 55, 2.0), c, True, offset, n)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _BuyHold(stats, btc), c, False, offset, n)
        costs[f"{c:.4f}"] = {"sma": a["cagr"], "don1": d1["cagr"],
                             "don2": d2["cagr"], "bh": b["cagr"]}
        print(f"   {c * 100:>8.2f}%    {pct(a['cagr']):>13}{pct(d1['cagr']):>14}"
              f"{pct(d2['cagr']):>14}{pct(b['cagr']):>9}")
    d2_nf, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _Donchian(stats, btc, 55, 2.0), lv.PERP_COST, False,
                   offset, n)
    d2_f, _ = run(dates, closes, highs, lows, funding, symbols,
                  lambda: _Donchian(stats, btc, 55, 2.0), lv.PERP_COST, True,
                  offset, n)
    print(f"\n   funding alone on Donchian 2x: {pct(d2_nf['cagr'])} without,"
          f" {pct(d2_f['cagr'])} with  -> costs {pct(d2_nf['cagr'] - d2_f['cagr'])}/yr")
    rep["cost_sensitivity"] = costs

    # ------------------------------------------------------------------ 6
    head("6. EXECUTION LAG — the fill is a day late, as it is in real life")
    print(f"   {'engine':<24}{'lag 0':>10}{'lag 1':>10}{'lag 2':>10}"
          f"{'lag 3':>10}{'loss/day of lag':>18}")
    lagrep = {}
    for label, build, cost, use_f in engines[1:]:
        row = []
        for L in (0, 1, 2, 3):
            def wrapped(b=build, LL=L):
                s = b()
                return s if LL == 0 else Lagged(s, LL)
            m, _ = run(dates, closes, highs, lows, funding, symbols, wrapped,
                       cost, use_f, offset, n)
            row.append(m["cagr"])
        lagrep[label] = row
        print(f"   {label:<24}" + "".join(pct(x).rjust(10) for x in row)
              + f"{pct((row[3] - row[0]) / 3):>18}")
    rep["execution_lag"] = lagrep

    # ------------------------------------------------------------------ 7
    head("7. ENSEMBLE — vote across filters instead of choosing one")
    print("   E30 C7 measured that picking the best backtest is worth 20% (= random).")
    print("   The reply to an unpickable set is not to pick.")

    def build_ens(lev):
        def f():
            return Ensemble([t.SmaRegime(stats, btc, 200, 1.0, "s"),
                             _Donchian(stats, btc, 55, 1.0),
                             t.MaCross(stats, btc, 50, 200, 1.0, "x")], lev)
        return f

    print(f"   {'book':<28}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'Sharpe':>8}"
          f"{'expo':>7}{'TUW':>7}")
    ens = {}
    for lev in (1.0, 1.5, 2.0):
        cost = lv.SPOT_COST if lev <= 1.0 else lv.PERP_COST
        m, _ = run(dates, closes, highs, lows, funding, symbols, build_ens(lev),
                   cost, lev > 1.0, offset, n)
        ens[f"{lev:g}x"] = m
        print(f"   {'vote of 3 filters @ ' + format(lev, 'g') + 'x':<28}"
              f"{pct(m['cagr'])}{pct(m['worst_dd'])}{m['mar']:>6.2f}"
              f"{m['sharpe']:>8.2f}{pct(m['exposure'], 0):>7}"
              f"{m['max_time_under_water']:>7}")
    for label, build, cost, use_f in engines:
        m, _ = run(dates, closes, highs, lows, funding, symbols, build, cost,
                   use_f, offset, n)
        print(f"   {label + ' (reference)':<28}{pct(m['cagr'])}{pct(m['worst_dd'])}"
              f"{m['mar']:>6.2f}{m['sharpe']:>8.2f}{pct(m['exposure'], 0):>7}"
              f"{m['max_time_under_water']:>7}")
    # held-out for the ensemble
    print("\n   held-out, same vote, same parameters:")
    for sym in ("ETH", "SOL"):
        j = symbols.index(sym)
        first = int(np.argmax(~np.isnan(closes[:, j])))
        s0 = max(first + WARMUP, offset)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _BuyHold(stats, j), lv.SPOT_COST, False, s0, n)

        def ens_j():
            return Ensemble([t.SmaRegime(stats, j, 200, 1.0, "s"),
                             _Donchian(stats, j, 55, 1.0),
                             t.MaCross(stats, j, 50, 200, 1.0, "x")], 1.0)
        m, _ = run(dates, closes, highs, lows, funding, symbols, ens_j,
                   lv.SPOT_COST, False, s0, n)
        ens[sym] = {"ensemble": m, "buy_hold": b}
        print(f"   {sym}: vote CAGR {pct(m['cagr'])} DD {pct(m['worst_dd'])} "
              f"MAR {m['mar']:.2f}   |   buy&hold CAGR {pct(b['cagr'])} "
              f"DD {pct(b['worst_dd'])} MAR {b['mar']:.2f}")
    rep["ensemble"] = ens

    # ------------------------------------------------------------------ 8
    head("8. EPISODES — is it all two trades?")
    print(f"   {'engine':<24}{'episodes':>10}{'win rate':>10}{'best':>9}"
          f"{'top-1 share':>13}{'top-3 share':>13}{'CAGR ex-best':>14}")
    epi = {}
    for label, build, cost, use_f in engines[1:]:
        m, res = run(dates, closes, highs, lows, funding, symbols, build, cost,
                     use_f, offset, n)
        eps = episodes(res.gross_leverage, res.equity, INITIAL)
        rets = [e[2] for e in eps]
        if not rets:
            continue
        growth = [1 + r for r in rets]
        total = math.prod(growth)
        srt = sorted(range(len(rets)), key=lambda k: rets[k], reverse=True)
        top1 = math.log1p(max(rets)) / math.log(total) if total > 1 else float("nan")
        top3 = sum(math.log1p(rets[k]) for k in srt[:3]) / math.log(total) \
            if total > 1 else float("nan")
        ex_best = math.prod(1 + rets[k] for k in range(len(rets)) if k != srt[0])
        yrs = m["days"] / t.TRADING_DAYS
        epi[label] = {"n": len(rets), "win_rate": float(np.mean([r > 0 for r in rets])),
                      "best": max(rets), "top1_share": top1, "top3_share": top3,
                      "cagr_ex_best": ex_best ** (1 / yrs) - 1, "cagr": m["cagr"]}
        print(f"   {label:<24}{len(rets):>10}"
              f"{pct(epi[label]['win_rate'], 0):>10}{pct(max(rets), 0):>9}"
              f"{pct(top1, 0):>13}{pct(top3, 0):>13}"
              f"{pct(epi[label]['cagr_ex_best']):>14}")
    rep["episodes"] = epi
    print("\n   'top-1 share' = fraction of total log growth from the single best")
    print("   in-market stretch. Above ~50% means the track record is one trade.")

    # ------------------------------------------------------------------ 9
    head("9. DEFLATED SHARPE — what would the best of 40 lucky coins have shown?")
    sharpes = []
    trials = []
    for w in (100, 200, 300):
        for L in (1.0, 2.0, 3.0, 4.0):
            cost = lv.SPOT_COST if L <= 1 else lv.PERP_COST
            m, _ = run(dates, closes, highs, lows, funding, symbols,
                       (lambda ww=w, LL=L: t.SmaRegime(stats, btc, ww, LL, "s")),
                       cost, L > 1, offset, n)
            sharpes.append(m["sharpe"]); trials.append((f"sma{w}", L, m["sharpe"]))
    for ch in (27, 55, 83):
        for L in (1.0, 2.0, 3.0, 4.0):
            cost = lv.SPOT_COST if L <= 1 else lv.PERP_COST
            m, _ = run(dates, closes, highs, lows, funding, symbols,
                       (lambda cc=ch, LL=L: _Donchian(stats, btc, cc, LL)),
                       cost, L > 1, offset, n)
            sharpes.append(m["sharpe"]); trials.append((f"don{ch}", L, m["sharpe"]))
    N = len(sharpes)
    sd_sr = float(np.std(sharpes, ddof=1))
    sr0 = sd_sr * ((1 - EULER) * norm_ppf(1 - 1.0 / N)
                   + EULER * norm_ppf(1 - 1.0 / (N * math.e)))
    best_label = max(trials, key=lambda x: x[2])
    best = best_label[2]

    m, res = run(dates, closes, highs, lows, funding, symbols,
                 lambda: _Donchian(stats, btc, 55, 2.0), lv.PERP_COST, True,
                 offset, n)
    curve = np.concatenate(([INITIAL], res.equity))
    r = curve[1:] / curve[:-1] - 1.0
    mu, sd = r.mean(), r.std(ddof=1)
    skew = float(np.mean(((r - mu) / sd) ** 3))
    kurt = float(np.mean(((r - mu) / sd) ** 4))
    T = len(r)
    sr_daily = mu / sd
    sr0_daily = sr0 / math.sqrt(365.25)
    denom = math.sqrt(max(1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2, 1e-12))
    dsr = norm_cdf((sr_daily - sr0_daily) * math.sqrt(T - 1) / denom)
    print(f"   variants examined in this experiment family      N = {N}")
    print(f"   spread of their Sharpes                          sd = {sd_sr:.3f}")
    print(f"   expected best Sharpe under the null of NO skill  SR0 = {sr0:.3f} (annualised)")
    print(f"   best Sharpe actually observed                    {best:.3f} "
          f"({best_label[0]} @ {best_label[1]:g}x)")
    print(f"   Donchian-55 2x Sharpe {m['sharpe']:.3f}, skew {skew:+.2f}, "
          f"kurtosis {kurt:.1f}, T = {T}")
    print(f"   deflated Sharpe probability (skill > luck):       {dsr:.3f}")
    print("\n   SR0 is what the LUCKIEST of N worthless strategies would show. If the")
    print("   observed best is not far above it, the ranking carries no information.")
    rep["deflated_sharpe"] = {"N": N, "sd_sr": sd_sr, "sr0_annual": sr0,
                              "best_observed": best, "best_variant": best_label[0],
                              "dsr_donchian2x": dsr, "skew": skew, "kurtosis": kurt}

    # ------------------------------------------------------------------ 10
    head("10. THE ENSEMBLE PUT THROUGH THE SAME NINE TESTS")
    print("   Section 7 made the vote look like the best thing in the file. Anything")
    print("   that survives one test and is then believed is how this repo got E23-E25.")
    ens_check = {}

    cs, dds = [], []
    for k in range(12):
        s0 = offset + k * 30
        if s0 + 365 * 5 > n:
            continue
        m, _ = run(dates, closes, highs, lows, funding, symbols, build_ens(1.0),
                   lv.SPOT_COST, False, s0, n)
        cs.append(m["cagr"]); dds.append(m["worst_dd"])
    ens_check["timing_luck"] = {"median": st.median(cs), "min": min(cs),
                                "max": max(cs), "spread": max(cs) - min(cs)}
    print(f"\n   timing luck: median {pct(st.median(cs))}  range "
          f"{pct(min(cs))} .. {pct(max(cs))}  spread {pct(max(cs) - min(cs))}"
          f"   (Donchian 2x spread was 25.5%)")

    rows, s0 = [], offset
    while s0 + 730 <= n:
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _BuyHold(stats, btc), lv.SPOT_COST, False, s0, s0 + 730)
        e, _ = run(dates, closes, highs, lows, funding, symbols, build_ens(1.0),
                   lv.SPOT_COST, False, s0, s0 + 730)
        rows.append({"start": dates[s0], "bh": b["cagr"], "ens": e["cagr"]})
        s0 += 182
    h1 = st.mean(r["ens"] - r["bh"] for r in rows[:len(rows) // 2])
    h2 = st.mean(r["ens"] - r["bh"] for r in rows[len(rows) // 2:])
    ens_check["decay"] = {"rows": rows, "first_half_edge": h1, "second_half_edge": h2}
    print(f"   decay: mean 2-year edge over B&H, first half {pct(h1)}, "
          f"second half {pct(h2)}, change {pct(h2 - h1)}")
    print("     " + "  ".join(f"{r['start'][:7]}:{(r['ens'] - r['bh']) * 100:+.0f}"
                              for r in rows))

    lagrow = []
    for L in (0, 1, 2, 3):
        def wrapped(LL=L):
            s = build_ens(1.0)()
            return s if LL == 0 else Lagged(s, LL)
        m, _ = run(dates, closes, highs, lows, funding, symbols, wrapped,
                   lv.SPOT_COST, False, offset, n)
        lagrow.append(m["cagr"])
    ens_check["lag"] = lagrow
    print(f"   execution lag: " + "  ".join(f"lag{i} {pct(x)}" for i, x in enumerate(lagrow)))

    m, res = run(dates, closes, highs, lows, funding, symbols, build_ens(1.0),
                 lv.SPOT_COST, False, offset, n)
    eps = [e[2] for e in episodes(res.gross_leverage, res.equity, INITIAL)]
    total = math.prod(1 + r for r in eps)
    srt = sorted(range(len(eps)), key=lambda k: eps[k], reverse=True)
    top1 = math.log1p(max(eps)) / math.log(total)
    ex_best = math.prod(1 + eps[k] for k in range(len(eps)) if k != srt[0])
    yrs = m["days"] / t.TRADING_DAYS
    ens_check["episodes"] = {"n": len(eps), "top1_share": top1,
                             "cagr": m["cagr"],
                             "cagr_ex_best": ex_best ** (1 / yrs) - 1}
    print(f"   episodes: {len(eps)} stretches, best one is {pct(top1, 0)} of total "
          f"log growth, CAGR without it {pct(ex_best ** (1 / yrs) - 1)}"
          f" (with it {pct(m['cagr'])})")

    curve = np.concatenate(([INITIAL], res.equity))
    r = curve[1:] / curve[:-1] - 1.0
    mu, sd = r.mean(), r.std(ddof=1)
    skew = float(np.mean(((r - mu) / sd) ** 3))
    kurt = float(np.mean(((r - mu) / sd) ** 4))
    sr_d = mu / sd
    denom = math.sqrt(max(1 - skew * sr_d + (kurt - 1) / 4 * sr_d ** 2, 1e-12))
    dsr_e = norm_cdf((sr_d - sr0 / math.sqrt(365.25)) * math.sqrt(len(r) - 1) / denom)
    ens_check["deflated_sharpe"] = {"sharpe": m["sharpe"], "dsr": dsr_e,
                                    "skew": skew, "kurtosis": kurt}
    print(f"   deflated Sharpe: SR {m['sharpe']:.3f}, skew {skew:+.2f}, "
          f"kurtosis {kurt:.1f}  ->  DSR {dsr_e:.3f}"
          f"   (Donchian 2x was {dsr:.3f}; 0.95 is the usual bar)")

    print("\n   NOTE: the vote was assembled after seeing sections 1-6. Its components")
    print("   are textbook and its combination rule has no parameter, which is the")
    print("   mildest form of hindsight — but it is still hindsight. It cannot be")
    print("   called validated until it is pre-declared and run on data not used here.")
    rep["ensemble_stress"] = ens_check

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, default=float)
    print(f"\nraw -> {os.path.relpath(OUT, os.path.dirname(__file__))}")
    print("Diagnostics only. No promotion, no criteria touched, no live trading.")


if __name__ == "__main__":
    main()
