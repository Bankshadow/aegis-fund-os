"""E33 — Screened Trend-Vote Basket, judged on the coins never used to build it.

Criteria declared in `docs/E33_CRITERIA.md` BEFORE this file existed. Run:

    python stvb_e33.py
    python -m unittest tests.test_trend_overlay

Read-only backtest. Same 33-symbol panel and same engine as E31/E32. Gross
exposure is capped at 1.0 by the setup, so nothing here can be liquidated —
H4 exists to catch a bug, not a risk. No order path exists in this file.
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
from trend_leverage_e32 import _BuyHold, INITIAL, WARMUP, run

OUT = os.path.join(os.path.dirname(__file__), "docs", "stvb-e33.json")
BURNED = ("BTC", "ETH", "SOL")


class EqualWeightHold:
    """Benchmark: hold everything in the group, equal weight, gross 1.0."""

    def __init__(self, stats, assets, rebalance=5, name="BH_equal_weight"):
        self.s, self.assets, self.rebalance, self.name = stats, list(assets), rebalance, name
        self._w = np.zeros(stats.closes.shape[1])

    def weights(self, i):
        if i % self.rebalance == 0:
            live = [j for j in self.assets if not np.isnan(self.s.closes[i, j])]
            self._w = np.zeros(self.s.closes.shape[1])
            if live:
                self._w[live] = 1.0 / len(live)
        self._w = np.where(~np.isnan(self.s.closes[i]), self._w, 0.0)
        return self._w.copy()


def head(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def pct(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


def tick(b):
    return "PASS" if b else "FAIL"


def derisked(closes, ref, start, end, target_dd):
    px = closes[start:end, ref]
    base = px / px[0]
    lo, hi = 0.0, 1.0
    for _ in range(60):
        f = (lo + hi) / 2
        curve = INITIAL * (1.0 + f * (base - 1.0))
        if t.risk_metrics(curve[1:], float(curve[0]))["worst_dd"] < target_dd:
            lo = f
        else:
            hi = f
    f = (lo + hi) / 2
    curve = INITIAL * (1.0 + f * (base - 1.0))
    m = t.risk_metrics(curve[1:], float(curve[0]))
    m["fraction"] = f
    return m


def main():
    dates, symbols, closes, highs, lows, funding = build_panel()
    stats = t.Stats(closes)
    n = len(dates)
    btc = symbols.index("BTC")
    clean = [j for j, s in enumerate(symbols) if s not in BURNED]
    burned = [symbols.index(s) for s in BURNED if s in symbols]
    n_win = (n - WARMUP) // 365
    offset = n - n_win * 365

    print("E33 — Screened Trend-Vote Basket")
    print(f"panel {len(symbols)} symbols, {n} days, {dates[0]} -> {dates[-1]}")
    print(f"PRIMARY evidence: the {len(clean)} coins never used to build this "
          f"mechanism")
    print(f"reported but NOT evidence: {', '.join(BURNED)} (burned by E30/E31/E32)")
    print(f"continuous run from {dates[offset]}, {n_win} annual windows")
    print("criteria: docs/E33_CRITERIA.md (declared before this file existed)\n")

    rep = {"criteria": "docs/E33_CRITERIA.md", "clean_universe":
           [symbols[j] for j in clean], "days": n, "first": dates[0],
           "last": dates[-1]}

    def stvb(assets, screen=True, cap=1.0, target=0.40):
        return lambda: t.ScreenedTrendVoteBasket(
            stats, vol_target=target, gross_cap=cap, use_screen=screen,
            assets=assets, name=f"STVB_{'screen' if screen else 'noscreen'}_{cap:g}x")

    # ------------------------------------------------------------------ A
    head("A. PRIMARY — the 30 coins that were never used to design this")
    rows = {}
    tests = [
        ("STVB (screen on)", stvb(clean, True), lv.SPOT_COST, False),
        ("STVB (screen off)", stvb(clean, False), lv.SPOT_COST, False),
        ("equal-weight buy & hold", lambda: EqualWeightHold(stats, clean),
         lv.SPOT_COST, False),
        ("BTC buy & hold", lambda: _BuyHold(stats, btc), lv.SPOT_COST, False),
    ]
    print(f"{'book':<28}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'Sharpe':>8}"
          f"{'Sortino':>9}{'Ulcer':>7}{'expo':>7}{'TUW':>6}{'10k ->':>11}")
    for label, build, cost, use_f in tests:
        m, res = run(dates, closes, highs, lows, funding, symbols, build, cost,
                     use_f, offset, n)
        rows[label] = (m, res)
        print(f"{label:<28}{pct(m['cagr'])}{pct(m['worst_dd'])}{m['mar']:>6.2f}"
              f"{m['sharpe']:>8.2f}{m['sortino']:>9.2f}{m['ulcer']:>7.2f}"
              f"{pct(m['exposure'], 0):>7}{m['max_time_under_water']:>6}"
              f"{m['final_equity']:>11,.0f}")
        rep.setdefault("primary", {})[label] = m

    stv = rows["STVB (screen on)"][0]
    ew = rows["equal-weight buy & hold"][0]
    bh = rows["BTC buy & hold"][0]
    no_screen = rows["STVB (screen off)"][0]
    print(f"\n   contribution of the screen alone: "
          f"CAGR {pct(no_screen['cagr'])} -> {pct(stv['cagr'])}"
          f"   MAR {no_screen['mar']:.2f} -> {stv['mar']:.2f}"
          f"   DD {pct(no_screen['worst_dd'])} -> {pct(stv['worst_dd'])}")

    dr = derisked(closes, btc, offset, n, stv["worst_dd"])
    print(f"   BTC de-risked to the same {pct(stv['worst_dd'])} drawdown "
          f"(f = {dr['fraction']:.2f}): CAGR {pct(dr['cagr'])}")
    rep["derisked_benchmark"] = dr

    # ------------------------------------------------------------------ B
    head("B. SECONDARY — the same setup on the burned coins (reported, not evidence)")
    for label, assets in (("BTC/ETH/SOL only", burned), ("all 33", list(range(len(symbols))))):
        m, _ = run(dates, closes, highs, lows, funding, symbols,
                   stvb(assets, True), lv.SPOT_COST, False, offset, n)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda a=assets: EqualWeightHold(stats, a), lv.SPOT_COST,
                   False, offset, n)
        print(f"   {label:<20} STVB {pct(m['cagr'])} DD {pct(m['worst_dd'])} "
              f"MAR {m['mar']:.2f}   |   equal-weight B&H {pct(b['cagr'])} "
              f"DD {pct(b['worst_dd'])} MAR {b['mar']:.2f}")
        rep.setdefault("secondary", {})[label] = {"stvb": m, "bench": b}

    # ------------------------------------------------------------------ C
    head("C. ANNUAL WINDOWS (primary universe)")
    win = {"stvb": [], "ew": [], "btc": []}
    print(f"{'window':<20}{'STVB':>10}{'eq-wt B&H':>12}{'BTC B&H':>10}{'STVB DD':>10}")
    for w in range(n_win):
        s0, e0 = offset + w * 365, offset + (w + 1) * 365
        a, _ = run(dates, closes, highs, lows, funding, symbols, stvb(clean, True),
                   lv.SPOT_COST, False, s0, e0)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: EqualWeightHold(stats, clean), lv.SPOT_COST, False, s0, e0)
        c, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: _BuyHold(stats, btc), lv.SPOT_COST, False, s0, e0)
        win["stvb"].append(a); win["ew"].append(b); win["btc"].append(c)
        print(f"{dates[s0][:7]}..{dates[e0 - 1][:7]:<9}{pct(a['cagr']):>10}"
              f"{pct(b['cagr']):>12}{pct(c['cagr']):>10}{pct(a['worst_dd']):>10}")
    beats_ew = sum(1 for i in range(n_win) if win["stvb"][i]["cagr"] > win["ew"][i]["cagr"])
    beats_btc = sum(1 for i in range(n_win) if win["stvb"][i]["cagr"] > win["btc"][i]["cagr"])
    print(f"{'beats eq-wt B&H':<20}{beats_ew:>10}/{n_win}"
          f"      beats BTC B&H {beats_btc}/{n_win}")
    print(f"{'median':<20}{pct(st.median(x['cagr'] for x in win['stvb'])):>10}"
          f"{pct(st.median(x['cagr'] for x in win['ew'])):>12}"
          f"{pct(st.median(x['cagr'] for x in win['btc'])):>10}")
    rep["windows"] = {k: [x for x in v] for k, v in win.items()}

    # ------------------------------------------------------------------ D
    head("D. H6 CONCENTRATION — is it one trade again?")
    m, res = rows["STVB (screen on)"]
    eps = [e[2] for e in episodes(res.gross_leverage, res.equity, INITIAL)]
    total = math.prod(1 + r for r in eps)
    srt = sorted(range(len(eps)), key=lambda k: eps[k], reverse=True)
    top1 = math.log1p(max(eps)) / math.log(total)
    top3 = sum(math.log1p(eps[k]) for k in srt[:3]) / math.log(total)
    yrs = m["days"] / t.TRADING_DAYS
    ex_best = math.prod(1 + eps[k] for k in range(len(eps)) if k != srt[0]) ** (1 / yrs) - 1
    print(f"   in-market stretches                 {len(eps)}")
    print(f"   win rate                            {pct(float(np.mean([r > 0 for r in eps])), 0)}")
    print(f"   best stretch share of log growth    {pct(top1, 0)}   (H6 needs < 40%)")
    print(f"   best three share                    {pct(top3, 0)}")
    print(f"   CAGR with the best stretch removed  {pct(ex_best)}   "
          f"vs eq-wt B&H {pct(ew['cagr'])}   (H6 needs >)")
    rep["concentration"] = {"episodes": len(eps), "top1": top1, "top3": top3,
                            "cagr_ex_best": ex_best}

    # ------------------------------------------------------------------ E
    head("E. H7 DECAY — rolling two-year edge over equal-weight buy & hold")
    dec, s0 = [], offset
    while s0 + 730 <= n:
        a, _ = run(dates, closes, highs, lows, funding, symbols, stvb(clean, True),
                   lv.SPOT_COST, False, s0, s0 + 730)
        b, _ = run(dates, closes, highs, lows, funding, symbols,
                   lambda: EqualWeightHold(stats, clean), lv.SPOT_COST, False,
                   s0, s0 + 730)
        dec.append({"start": dates[s0], "stvb": a["cagr"], "bench": b["cagr"],
                    "edge": a["cagr"] - b["cagr"]})
        s0 += 182
    for d in dec:
        print(f"   {d['start'][:7]}   STVB {pct(d['stvb'])}   bench {pct(d['bench'])}"
              f"   edge {pct(d['edge'])}")
    h1 = st.mean(d["edge"] for d in dec[:len(dec) // 2])
    h2 = st.mean(d["edge"] for d in dec[len(dec) // 2:])
    print(f"\n   mean edge: first half {pct(h1)}   second half {pct(h2)}   "
          f"(H7 needs second half >= 0)")
    rep["decay"] = {"rows": dec, "first_half": h1, "second_half": h2}

    # ------------------------------------------------------------------ F
    head("F. H8 TIMING LUCK and H9 EXECUTION LAG")
    cs = []
    for k in range(12):
        s0 = offset + k * 30
        if s0 + 365 * 5 > n:
            continue
        a, _ = run(dates, closes, highs, lows, funding, symbols, stvb(clean, True),
                   lv.SPOT_COST, False, s0, n)
        cs.append(a["cagr"])
    spread = max(cs) - min(cs)
    print(f"   timing luck: median {pct(st.median(cs))}  range {pct(min(cs))} .. "
          f"{pct(max(cs))}  spread {pct(spread)}   (H8 needs < 15%)")
    lags = []
    for L in (0, 1, 2, 3):
        def wrapped(LL=L):
            s = stvb(clean, True)()
            return s if LL == 0 else Lagged(s, LL)
        a, _ = run(dates, closes, highs, lows, funding, symbols, wrapped,
                   lv.SPOT_COST, False, offset, n)
        lags.append(a["cagr"])
    print(f"   execution lag: " + "  ".join(f"lag{i} {pct(x)}" for i, x in enumerate(lags))
          + f"   loss at lag 1 = {pct(lags[0] - lags[1])}   (H9 needs < 3%)")
    rep["timing_luck"] = {"cagrs": cs, "spread": spread}
    rep["lag"] = lags

    # ------------------------------------------------------------------ G
    head("G. H10 DEFLATED SHARPE across the whole E32+E33 family")
    sharpes = []
    for target in (0.20, 0.30, 0.40, 0.60):
        for screen in (True, False):
            a, _ = run(dates, closes, highs, lows, funding, symbols,
                       stvb(clean, screen, 1.0, target), lv.SPOT_COST, False,
                       offset, n)
            sharpes.append(a["sharpe"])
    N = 24 + len(sharpes)          # 24 from E32-depth section 9
    sd_sr = float(np.std(sharpes + [stv["sharpe"], ew["sharpe"]], ddof=1))
    sr0 = sd_sr * ((1 - EULER) * norm_ppf(1 - 1.0 / N)
                   + EULER * norm_ppf(1 - 1.0 / (N * math.e)))
    curve = np.concatenate(([INITIAL], res.equity))
    r = curve[1:] / curve[:-1] - 1.0
    mu, sd = r.mean(), r.std(ddof=1)
    skew = float(np.mean(((r - mu) / sd) ** 3))
    kurt = float(np.mean(((r - mu) / sd) ** 4))
    sr_d = mu / sd
    denom = math.sqrt(max(1 - skew * sr_d + (kurt - 1) / 4 * sr_d ** 2, 1e-12))
    dsr = norm_cdf((sr_d - sr0 / math.sqrt(365.25)) * math.sqrt(len(r) - 1) / denom)
    print(f"   variants in the family              N = {N}")
    print(f"   expected best Sharpe under no skill SR0 = {sr0:.3f}")
    print(f"   STVB Sharpe {stv['sharpe']:.3f}, skew {skew:+.2f}, kurtosis {kurt:.1f}")
    print(f"   deflated Sharpe                     DSR = {dsr:.3f}   (H10 needs >= 0.95)")
    rep["deflated_sharpe"] = {"N": N, "sr0": sr0, "dsr": dsr, "skew": skew,
                              "kurtosis": kurt, "sharpe": stv["sharpe"]}

    # ------------------------------------------------------------------ H
    head("H. VERDICT — criteria declared in docs/E33_CRITERIA.md before the run")
    H = {
        "H1 CAGR > equal-weight B&H": stv["cagr"] > ew["cagr"],
        "H2 MAR > both benchmarks": stv["mar"] > ew["mar"] and stv["mar"] > bh["mar"],
        "H3 CAGR > de-risked B&H at same DD": stv["cagr"] > dr["cagr"],
        "H4 no liquidation, no ruin": stv["liquidations"] == 0 and not stv["ruined"],
        "H5 beats benchmark >= 5/8 windows": beats_ew >= 5,
        "H6 top-1 < 40% and ex-best still wins": top1 < 0.40 and ex_best > ew["cagr"],
        "H7 second-half edge >= 0": h2 >= 0,
        "H8 timing-luck spread < 15 pts": spread < 0.15,
        "H9 lag-1 loss < 3 pts": (lags[0] - lags[1]) < 0.03,
        "H10 deflated Sharpe >= 0.95": dsr >= 0.95,
    }
    for k, v in H.items():
        print(f"   {k:<44}{tick(v)}")
    rep["verdict"] = {k: bool(v) for k, v in H.items()}
    passed = all(H.values())
    print(f"\n   OVERALL: {'PASS — all ten' if passed else 'FAIL — ' + ', '.join(k.split()[0] for k, v in H.items() if not v)}")
    print("   Nothing is promoted by this file. Paper/testnet remains the only")
    print("   next step allowed, per CLAUDE.md and docs/FIRST_REAL_TRACK_RECORD.md.")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, default=float)
    print(f"\nraw -> {os.path.relpath(OUT, os.path.dirname(__file__))}")


if __name__ == "__main__":
    main()
