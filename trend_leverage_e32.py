"""E32 — put the leverage on the trend filter instead of on buy-and-hold.

Criteria declared in `docs/E32_CRITERIA.md` BEFORE this ran. Run:

    python trend_leverage_e32.py
    python -m unittest tests.test_trend_overlay

Read-only backtest over the same 33-symbol daily panel as E31, with the same
engine: real per-symbol funding, intrabar liquidation, delisting as an exit.
No order path exists anywhere in this file.
"""

import json
import os
from datetime import datetime, timezone

import numpy as np

from crypto_leverage_e31 import build_panel
from dynamic_grid import leveraged as lv
from dynamic_grid import trend_overlay as t

WARMUP = 200
YEAR = 365
INITIAL = 10_000.0
OUT = os.path.join(os.path.dirname(__file__), "docs", "trend-leverage-e32.json")

# Benchmark constants, taken from E31's completed run (declared in the criteria)
K0_CAGR = 0.322
K0_MAR = 0.447


# --------------------------------------------------------------------------
# candidate set — fixed by docs/E32_CRITERIA.md §3, nothing tuned here
# --------------------------------------------------------------------------

def candidates(stats, btc):
    """(builder, cost, use_funding, label). Gross <= 1 trades spot without
    funding, exactly as E31 treated K0/K3; anything that can exceed 1x is a
    perp and pays real funding."""
    spot, perp = lv.SPOT_COST, lv.PERP_COST
    return [
        (lambda: _BuyHold(stats, btc), spot, False, "B0 BTC buy & hold 1x"),
        (lambda: t.SmaRegime(stats, btc, 200, 1.0, "T1_sma200_1x"),
         spot, False, "T1 SMA-200 regime 1x"),
        (lambda: t.SmaRegime(stats, btc, 200, 2.0, "T2_sma200_2x"),
         perp, True, "T2 SMA-200 regime 2x"),
        (lambda: t.SmaRegime(stats, btc, 200, 3.0, "T3_sma200_3x"),
         perp, True, "T3 SMA-200 regime 3x"),
        (lambda: t.MaCross(stats, btc, 50, 200, 2.0, "T4_cross50_200_2x"),
         perp, True, "T4 MA cross 50/200 2x"),
        (lambda: t.VolTargetSma(stats, btc, 200, 0.40, 3.0, name="T5_sma200_voltgt40"),
         perp, True, "T5 SMA-200 + vol target 40% (cap 3x)"),
        (lambda: _Donchian(stats, btc, 55, 2.0), perp, True, "T6 Donchian-55 2x (E31 K1 at 2x)"),
        (lambda: t.TimeSeriesMomentumBasket(stats, 200, 1.0, "equal",
                                            name="T7_tsmom_equal_1x"),
         spot, False, "T7 TS-momentum basket, equal weight 1x"),
        (lambda: t.TimeSeriesMomentumBasket(stats, 200, 1.0, "invvol",
                                            name="T8_tsmom_invvol_1x"),
         spot, False, "T8 TS-momentum basket, inverse vol 1x"),
        (lambda: t.TimeSeriesMomentumBasket(stats, 200, 2.0, "invvol",
                                            name="T9_tsmom_invvol_2x"),
         perp, True, "T9 TS-momentum basket, inverse vol 2x"),
        (lambda: t.Blend([(t.SmaRegime(stats, btc, 200, 2.0), 0.5),
                          (t.TimeSeriesMomentumBasket(stats, 200, 2.0, "invvol"), 0.5)],
                         "T10_blend_sma2x_tsmom2x"),
         perp, True, "T10 50% T2 + 50% T9"),
    ]


class _BuyHold:
    name = "B0_btc_buy_hold"

    def __init__(self, stats, asset):
        self.s, self.a = stats, asset

    def weights(self, i):
        w = np.zeros(self.s.closes.shape[1])
        if not np.isnan(self.s.closes[i, self.a]):
            w[self.a] = 1.0
        return w


class _Donchian:
    """E31's K1 mechanism, re-expressed against the Stats panel."""

    def __init__(self, stats, asset, channel=55, leverage=2.0):
        self.s, self.a, self.ch, self.lev = stats, asset, channel, leverage
        self.state = 0
        self.name = f"T6_donchian{channel}_{leverage:g}x"

    def weights(self, i):
        c = self.s.closes
        if i >= self.ch:
            hi = np.nanmax(c[i - self.ch:i, self.a])
            lo = np.nanmin(c[i - self.ch:i, self.a])
            if not np.isnan(c[i, self.a]):
                if c[i, self.a] > hi:
                    self.state = 1
                elif c[i, self.a] < lo:
                    self.state = 0
        w = np.zeros(c.shape[1])
        if not np.isnan(c[i, self.a]):
            w[self.a] = self.state * self.lev
        return w


# --------------------------------------------------------------------------
# runners
# --------------------------------------------------------------------------

def run(dates, closes, highs, lows, funding, symbols, build, cost, use_f,
        start, end):
    sub_stats = t.Stats(closes[:end])
    strat = build()
    strat.s = sub_stats
    if hasattr(strat, "parts"):
        for part, _ in strat.parts:
            part.s = sub_stats
    if hasattr(strat, "inner"):
        strat.inner.s = sub_stats
    res = lv.simulate(dates, closes[:end], highs[:end], lows[:end],
                      funding[:end], strat, start=start,
                      initial_equity=INITIAL, cost=cost, use_funding=use_f)
    m = t.risk_metrics(res.equity, INITIAL)
    m["liquidations"] = res.liquidations
    m["ruined"] = res.ruined
    m["exposure"] = t.exposure_days(res.gross_leverage)
    m["mean_gross_leverage"] = res.mean_gross_leverage
    m["funding_paid"] = res.funding_paid
    m["name"] = res.name
    return m, res


def derisked_benchmark(closes, btc, start, end, target_dd):
    """BTC spot held at fraction f with the rest in cash, f solved so that the
    worst drawdown equals `target_dd`. Exact, no leverage, no rebalancing."""
    px = closes[start:end, btc]
    base = px / px[start - start] if False else px / px[0]
    lo, hi = 0.0, 1.0
    for _ in range(60):
        f = (lo + hi) / 2
        curve = INITIAL * (1.0 + f * (base - 1.0))
        dd = t.risk_metrics(curve[1:], float(curve[0]))["worst_dd"]
        if dd < target_dd:
            lo = f
        else:
            hi = f
    f = (lo + hi) / 2
    curve = INITIAL * (1.0 + f * (base - 1.0))
    m = t.risk_metrics(curve[1:], float(curve[0]))
    m["fraction"] = f
    return m


def fmt(x, nd=1):
    return f"{x * 100:>7.{nd}f}%"


# --------------------------------------------------------------------------
# diagnostics — these do not decide anything, they explain what decided it
# --------------------------------------------------------------------------

def diagnostics(dates, symbols, closes, highs, lows, funding, stats, btc,
                offset, n, report):
    diag = {}

    print("\n" + "=" * 100)
    print("G. G7 SURFACE for the Donchian mechanism (the candidate that cleared G1-G5)")
    print("=" * 100)
    print(f"{'variant':<34}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'>K0?':>6}{'liq':>5}")
    grid = []
    for ch in (27, 55, 83):                      # +/- 50% of the declared 55
        for lev in (1.0, 2.0, 3.0, 4.0):
            cost = lv.SPOT_COST if lev <= 1.0 else lv.PERP_COST
            m, _ = run(dates, closes, highs, lows, funding, symbols,
                       (lambda c=ch, L=lev: _Donchian(stats, btc, c, L)),
                       cost, lev > 1.0, offset, n)
            ok = m["cagr"] > K0_CAGR
            grid.append({"channel": ch, "leverage": lev, **m, "beats_K0": bool(ok)})
            print(f"{'Donchian-' + str(ch) + ' @ ' + format(lev, 'g') + 'x':<34}"
                  f"{fmt(m['cagr'])}{fmt(m['worst_dd'])}{m['mar']:>6.2f}"
                  f"{'yes' if ok else 'no':>6}{m['liquidations']:>5}")
    flat = sum(1 for g in grid if g["beats_K0"]) / len(grid)
    diag["donchian_surface"] = {"grid": grid, "flat_pct": flat}
    print(f"\n  {sum(1 for g in grid if g['beats_K0'])}/{len(grid)} = {flat:.1%} "
          f"of the Donchian surface beats K0   (G7 needs >= 60%)")

    print("\n" + "=" * 100)
    print("H. WHY LEVERAGE FAILS — measured volatility drag, not a formula")
    print("=" * 100)
    print("   a constant-leverage book rebalanced daily loses (L^2-L)/2 * sigma^2 per")
    print("   year to the rebalance itself, before any fee or funding is charged.")
    print(f"{'mechanism':<20}{'L':>4}{'CAGR':>9}{'L x CAGR(1x)':>14}{'shortfall':>11}"
          f"{'predicted drag':>16}{'funding':>9}")
    drags = []
    for label, builder in (
        ("SMA-200", lambda L: t.SmaRegime(stats, btc, 200, L, f"sma200_{L:g}x")),
        ("Donchian-55", lambda L: _Donchian(stats, btc, 55, L)),
    ):
        base, base_res = run(dates, closes, highs, lows, funding, symbols,
                             (lambda: builder(1.0)), lv.SPOT_COST, False, offset, n)
        curve = np.concatenate(([INITIAL], base_res.equity))
        r1 = curve[1:] / curve[:-1] - 1.0
        sigma = float(np.std(r1, ddof=1) * np.sqrt(t.TRADING_DAYS))
        for L in (2.0, 3.0, 4.0):
            m, res = run(dates, closes, highs, lows, funding, symbols,
                         (lambda LL=L: builder(LL)), lv.PERP_COST, True, offset, n)
            naive = L * base["cagr"]
            predicted = (L * L - L) / 2.0 * sigma * sigma
            yrs = m["days"] / t.TRADING_DAYS
            fund = res.funding_paid / yrs
            drags.append({"mechanism": label, "leverage": L, "cagr": m["cagr"],
                          "naive": naive, "sigma_1x": sigma,
                          "predicted_drag": predicted, "funding_per_year": fund})
            print(f"{label:<20}{L:>4.0f}{fmt(m['cagr'])}{fmt(naive):>14}"
                  f"{fmt(m['cagr'] - naive):>11}{fmt(predicted):>16}{fmt(fund):>9}")
    diag["volatility_drag"] = drags
    print("   (shortfall = what leverage actually delivered minus what it promised)")

    print("\n" + "=" * 100)
    print("I. RISK OF RUIN vs LEVERAGE — block bootstrap on the 1x daily path")
    print("=" * 100)
    print("   2,000 resampled 8-year histories, 60-day blocks (keeps trends and")
    print("   crash clusters intact), leverage applied daily with funding and")
    print("   an intraday-free liquidation check. Ruin = equity below 10% of start.")
    rng = np.random.default_rng(32)
    boot = {}
    for label, builder, cost in (
        ("SMA-200", lambda: t.SmaRegime(stats, btc, 200, 1.0, "sma200_1x"), lv.SPOT_COST),
        ("Donchian-55", lambda: _Donchian(stats, btc, 55, 1.0), lv.SPOT_COST),
    ):
        _, res = run(dates, closes, highs, lows, funding, symbols, builder,
                     cost, False, offset, n)
        curve = np.concatenate(([INITIAL], res.equity))
        r1 = curve[1:] / curve[:-1] - 1.0
        med_funding = float(np.nanmedian(funding[offset:n, btc]))
        print(f"\n   {label}: 1x daily vol {np.std(r1, ddof=1) * np.sqrt(t.TRADING_DAYS):.1%}"
              f" annualised, median funding {med_funding * 100:.3f}%/day")
        print(f"   {'L':>3}{'median CAGR':>13}{'5th pct':>10}{'95th pct':>10}"
              f"{'P(ruin)':>10}{'P(DD>80%)':>11}")
        rows = []
        blocks = 60
        idx_max = len(r1) - blocks
        for L in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
            cagrs, ruins, deep = [], 0, 0
            for _ in range(2000):
                picks = rng.integers(0, idx_max, size=len(r1) // blocks + 1)
                path = np.concatenate([r1[p:p + blocks] for p in picks])[:len(r1)]
                lev_r = L * path - (L * med_funding if L > 1 else 0.0)
                lev_r = np.maximum(lev_r, -0.995)
                eq = INITIAL * np.cumprod(1.0 + lev_r)
                peak = np.maximum.accumulate(np.concatenate(([INITIAL], eq)))
                dd = ((peak - np.concatenate(([INITIAL], eq))) / peak).max()
                if eq.min() < INITIAL * 0.10:
                    ruins += 1
                if dd > 0.80:
                    deep += 1
                yrs = len(lev_r) / t.TRADING_DAYS
                cagrs.append(max(eq[-1] / INITIAL, 1e-12) ** (1 / yrs) - 1)
            cagrs = np.array(cagrs)
            rows.append({"leverage": L, "median_cagr": float(np.median(cagrs)),
                         "p5": float(np.percentile(cagrs, 5)),
                         "p95": float(np.percentile(cagrs, 95)),
                         "p_ruin": ruins / 2000, "p_dd80": deep / 2000})
            print(f"   {L:>3.1f}{np.median(cagrs) * 100:>12.1f}%"
                  f"{np.percentile(cagrs, 5) * 100:>9.1f}%"
                  f"{np.percentile(cagrs, 95) * 100:>9.1f}%"
                  f"{ruins / 2000:>10.1%}{deep / 2000:>11.1%}")
        boot[label] = rows
    diag["bootstrap_ruin"] = boot

    print("\n" + "=" * 100)
    print("J. THE HELD-OUT CLIFF — the same leverage sweep on ETH and SOL")
    print("=" * 100)
    sweep = {}
    for sym in ("ETH", "SOL"):
        if sym not in symbols:
            continue
        j = symbols.index(sym)
        first = int(np.argmax(~np.isnan(closes[:, j])))
        s0 = max(first + WARMUP, offset)
        bench, _ = run(dates, closes, highs, lows, funding, symbols,
                       lambda: _BuyHold(stats, j), lv.SPOT_COST, False, s0, n)
        print(f"\n   {sym} (buy & hold CAGR {fmt(bench['cagr'])}, "
              f"worst DD {fmt(bench['worst_dd'])})")
        print(f"   {'L':>4}{'SMA-200 CAGR':>15}{'DD':>8}{'liq':>5}"
              f"{'Donchian CAGR':>16}{'DD':>8}{'liq':>5}")
        rows = []
        for L in (1.0, 1.5, 2.0, 3.0):
            cost = lv.SPOT_COST if L <= 1.0 else lv.PERP_COST
            a, _ = run(dates, closes, highs, lows, funding, symbols,
                       (lambda LL=L: t.SmaRegime(stats, j, 200, LL, f"s{LL:g}")),
                       cost, L > 1.0, s0, n)
            b, _ = run(dates, closes, highs, lows, funding, symbols,
                       (lambda LL=L: _Donchian(stats, j, 55, LL)),
                       cost, L > 1.0, s0, n)
            rows.append({"leverage": L, "sma": a, "donchian": b})
            print(f"   {L:>4.1f}{fmt(a['cagr']):>15}{fmt(a['worst_dd']):>8}"
                  f"{a['liquidations']:>5}{fmt(b['cagr']):>16}"
                  f"{fmt(b['worst_dd']):>8}{b['liquidations']:>5}")
        sweep[sym] = {"benchmark": bench, "rows": rows}
    diag["held_out_leverage_sweep"] = sweep

    print("\n" + "=" * 100)
    print("K. RISK-BUDGET FRONTIER — CAGR available at a fixed worst-drawdown budget")
    print("=" * 100)
    print("   each engine is held at the cash fraction f that puts its worst drawdown")
    print("   exactly on the budget. f <= 1 always: this is de-risking, never leverage.")
    engines = [
        ("BTC buy & hold 1x", lambda: _BuyHold(stats, btc), lv.SPOT_COST, False),
        ("SMA-200 1x", lambda: t.SmaRegime(stats, btc, 200, 1.0, "s1"), lv.SPOT_COST, False),
        ("SMA-200 + vol target 40%", lambda: t.VolTargetSma(stats, btc, 200, 0.40, 3.0, name="vt"), lv.PERP_COST, True),
        ("Donchian-55 1x", lambda: _Donchian(stats, btc, 55, 1.0), lv.SPOT_COST, False),
        ("Donchian-55 2x", lambda: _Donchian(stats, btc, 55, 2.0), lv.PERP_COST, True),
        ("TS-mom basket invvol 1x", lambda: t.TimeSeriesMomentumBasket(stats, 200, 1.0, "invvol", name="b1"), lv.SPOT_COST, False),
    ]
    budgets = (0.20, 0.30, 0.40, 0.50)
    print(f"{'engine':<28}{'nativeDD':>10}" + "".join(f"{'DD<=' + format(b, '.0%'):>11}" for b in budgets))
    frontier = {}
    for label, build, cost, use_f in engines:
        m, res = run(dates, closes, highs, lows, funding, symbols, build, cost,
                     use_f, offset, n)
        curve = np.concatenate(([INITIAL], res.equity))
        base = curve / INITIAL
        row, cells = {}, []
        for b in budgets:
            lo, hi = 0.0, 1.0
            for _ in range(50):
                f = (lo + hi) / 2
                c2 = INITIAL * (1.0 + f * (base - 1.0))
                dd = t.risk_metrics(c2[1:], float(c2[0]))["worst_dd"]
                if dd < b:
                    lo = f
                else:
                    hi = f
            f = (lo + hi) / 2
            c2 = INITIAL * (1.0 + f * (base - 1.0))
            mm = t.risk_metrics(c2[1:], float(c2[0]))
            row[f"{b:.0%}"] = {"fraction": f, **mm}
            cells.append(f"{mm['cagr'] * 100:>7.1f}% " if f < 0.999 else
                         f"{mm['cagr'] * 100:>6.1f}%* ")
        frontier[label] = row
        print(f"{label:<28}{fmt(m['worst_dd']):>10}" + "".join(f"{c:>11}" for c in cells))
    print("   * the engine's own drawdown is already inside the budget; f is capped at 1.0")
    diag["risk_budget_frontier"] = frontier

    print("\n" + "=" * 100)
    print("L. DIVERSIFYING THE SAME FILTER ACROSS THREE ASSETS (1x, equal weight)")
    print("=" * 100)
    tri = [s for s in ("BTC", "ETH", "SOL") if s in symbols]
    j_list = [symbols.index(s) for s in tri]
    first = max(int(np.argmax(~np.isnan(closes[:, j]))) for j in j_list)
    s0 = max(first + WARMUP, offset)

    class _TriTrend:
        name = "L_sma200_3asset_equal_1x"

        def weights(self, i):
            w = np.zeros(closes.shape[1])
            ma = stats.sma(200)[i]
            live = [j for j in j_list
                    if not np.isnan(closes[i, j]) and not np.isnan(ma[j])
                    and closes[i, j] > ma[j]]
            for j in live:
                w[j] = 1.0 / len(j_list)     # cash when a leg is out, not doubled up
            return w

    m, _ = run(dates, closes, highs, lows, funding, symbols, lambda: _TriTrend(),
               lv.SPOT_COST, False, s0, n)
    singles = {}
    for s, j in zip(tri, j_list):
        sm, _ = run(dates, closes, highs, lows, funding, symbols,
                    (lambda jj=j: t.SmaRegime(stats, jj, 200, 1.0, f"sma_{jj}")),
                    lv.SPOT_COST, False, s0, n)
        singles[s] = sm
    print(f"   from {dates[s0]}   ({', '.join(tri)})")
    print(f"   {'book':<32}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'Sharpe':>8}{'TUW days':>10}")
    for s in tri:
        sm = singles[s]
        print(f"   {s + ' SMA-200 1x alone':<32}{fmt(sm['cagr'])}{fmt(sm['worst_dd'])}"
              f"{sm['mar']:>6.2f}{sm['sharpe']:>8.2f}{sm['max_time_under_water']:>10}")
    print(f"   {'equal weight of the three':<32}{fmt(m['cagr'])}{fmt(m['worst_dd'])}"
          f"{m['mar']:>6.2f}{m['sharpe']:>8.2f}{m['max_time_under_water']:>10}")
    diag["three_asset"] = {"combined": m, "singles": singles, "from": dates[s0]}

    print("\n" + "=" * 100)
    print("M. DOES DIVERSIFICATION BUY BACK ANY LEVERAGE TOLERANCE?")
    print("=" * 100)
    print("   POST-HOC. This combination was assembled after seeing sections A-L, so")
    print("   it is a hypothesis for a future pre-declared run, not a result.")

    class _TriDonchian:
        def __init__(self, lev):
            self.lev = lev
            self.state = {j: 0 for j in j_list}
            self.name = f"M_donchian55_3asset_{lev:g}x"

        def weights(self, i):
            w = np.zeros(closes.shape[1])
            for j in j_list:
                if i >= 55 and not np.isnan(closes[i, j]):
                    hi = np.nanmax(closes[i - 55:i, j])
                    lo = np.nanmin(closes[i - 55:i, j])
                    if closes[i, j] > hi:
                        self.state[j] = 1
                    elif closes[i, j] < lo:
                        self.state[j] = 0
                if self.state[j] and not np.isnan(closes[i, j]):
                    w[j] = self.lev / len(j_list)
            return w

    print(f"   {'book':<34}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'Sharpe':>8}{'liq':>5}")
    tri_rows = []
    for lev in (1.0, 1.5, 2.0, 3.0):
        cost = lv.SPOT_COST if lev <= 1.0 else lv.PERP_COST
        mm, _ = run(dates, closes, highs, lows, funding, symbols,
                    (lambda L=lev: _TriDonchian(L)), cost, lev > 1.0, s0, n)
        tri_rows.append({"leverage": lev, **mm})
        print(f"   {'Donchian-55 x 3 assets @ ' + format(lev, 'g') + 'x':<34}"
              f"{fmt(mm['cagr'])}{fmt(mm['worst_dd'])}{mm['mar']:>6.2f}"
              f"{mm['sharpe']:>8.2f}{mm['liquidations']:>5}")
    single, _ = run(dates, closes, highs, lows, funding, symbols,
                    lambda: _Donchian(stats, btc, 55, 1.0), lv.SPOT_COST, False, s0, n)
    bh3, _ = run(dates, closes, highs, lows, funding, symbols,
                 lambda: _BuyHold(stats, btc), lv.SPOT_COST, False, s0, n)
    print(f"   {'BTC Donchian-55 1x alone':<34}{fmt(single['cagr'])}"
          f"{fmt(single['worst_dd'])}{single['mar']:>6.2f}{single['sharpe']:>8.2f}"
          f"{single['liquidations']:>5}")
    print(f"   {'BTC buy & hold (same window)':<34}{fmt(bh3['cagr'])}"
          f"{fmt(bh3['worst_dd'])}{bh3['mar']:>6.2f}{bh3['sharpe']:>8.2f}"
          f"{bh3['liquidations']:>5}")
    diag["three_asset_donchian"] = {"rows": tri_rows, "btc_single": single,
                                    "btc_buy_hold": bh3, "from": dates[s0]}

    report["diagnostics"] = diag


def main():
    dates, symbols, closes, highs, lows, funding = build_panel()
    btc = symbols.index("BTC")
    n = len(dates)
    stats = t.Stats(closes)
    n_win = (n - WARMUP) // YEAR
    offset = n - n_win * YEAR

    print(f"E32 — leverage on the trend filter, not on buy-and-hold")
    print(f"universe {len(symbols)} symbols, {n} days, {dates[0]} -> {dates[-1]}")
    print(f"continuous run from bar {offset} ({dates[offset]}); "
          f"{n_win} annual windows\n")
    print("criteria: docs/E32_CRITERIA.md (declared before this ran)\n")

    report = {"generated": datetime.now(timezone.utc).isoformat(),
              "criteria": "docs/E32_CRITERIA.md",
              "universe": symbols, "days": n,
              "first": dates[0], "last": dates[-1],
              "benchmark": {"K0_CAGR": K0_CAGR, "K0_MAR": K0_MAR},
              "continuous": {}, "windows": {}, "held_out": {},
              "perturbations": {}, "verdicts": {}}

    # ---------------- continuous full-period run ----------------
    print("=" * 100)
    print("A. CONTINUOUS RUN — one path, {} -> {}".format(dates[offset], dates[-1]))
    print("=" * 100)
    hdr = (f"{'candidate':<38}{'CAGR':>8}{'worstDD':>9}{'MAR':>6}{'Sharpe':>8}"
           f"{'Sortino':>9}{'Ulcer':>7}{'expo':>7}{'liq':>5}{'10k ->':>12}")
    print(hdr)
    cont = {}
    for build, cost, use_f, label in candidates(stats, btc):
        m, _ = run(dates, closes, highs, lows, funding, symbols, build, cost,
                   use_f, offset, n)
        cont[m["name"]] = m
        report["continuous"][m["name"]] = {**m, "label": label}
        print(f"{label:<38}{fmt(m['cagr'])}{fmt(m['worst_dd'])}{m['mar']:>6.2f}"
              f"{m['sharpe']:>8.2f}{m['sortino']:>9.2f}{m['ulcer']:>7.2f}"
              f"{fmt(m['exposure'], 0)}{m['liquidations']:>5}"
              f"{m['final_equity']:>12,.0f}")

    # ---------------- G3: de-risked benchmark at matched drawdown ------------
    print("\n" + "=" * 100)
    print("B. G3 — versus BTC spot held at the fraction that has the SAME worst drawdown")
    print("=" * 100)
    print(f"{'candidate':<38}{'CAGR':>9}{'f':>7}{'BTC@f CAGR':>12}{'edge':>9}{'G3':>5}")
    for name, m in cont.items():
        if name == "B0_btc_buy_hold":
            continue
        b = derisked_benchmark(closes, btc, offset, n, m["worst_dd"])
        edge = m["cagr"] - b["cagr"]
        report["continuous"][name]["derisked_bench"] = b
        report["continuous"][name]["G3_edge"] = edge
        print(f"{name:<38}{fmt(m['cagr'])}{b['fraction']:>7.2f}"
              f"{fmt(b['cagr']):>12}{fmt(edge):>9}{'PASS' if edge > 0 else 'FAIL':>5}")

    # ---------------- annual windows ----------------
    print("\n" + "=" * 100)
    print(f"C. {n_win} ANNUAL WINDOWS — annualised return per window")
    print("=" * 100)
    per_win = {}
    labels = []
    for build, cost, use_f, label in candidates(stats, btc):
        rows = []
        for w in range(n_win):
            s0 = offset + w * YEAR
            e0 = s0 + YEAR
            m, res = run(dates, closes, highs, lows, funding, symbols, build,
                         cost, use_f, s0, e0)
            rows.append({"window": w + 1, "start": dates[s0], "end": dates[e0 - 1],
                         "annual": m["cagr"], "maxDD": m["worst_dd"],
                         "liquidations": m["liquidations"], "ruined": m["ruined"],
                         "exposure": m["exposure"]})
        nm = build().name
        per_win[nm] = rows
        labels.append((nm, label))
        report["windows"][nm] = rows

    names = [nm for nm, _ in labels]
    print(f"{'window':<20}" + "".join(f"{nm.split('_')[0]:>9}" for nm in names))
    for w in range(n_win):
        row = per_win[names[0]][w]
        print(f"{row['start'][:7]}..{row['end'][:7]:<9}"
              + "".join(f"{per_win[nm][w]['annual'] * 100:>8.0f}%" for nm in names))
    print(f"{'median':<20}" + "".join(
        f"{np.median([r['annual'] for r in per_win[nm]]) * 100:>8.0f}%" for nm in names))
    print(f"{'worst window':<20}" + "".join(
        f"{min(r['annual'] for r in per_win[nm]) * 100:>8.0f}%" for nm in names))
    print(f"{'ruined windows':<20}" + "".join(
        f"{sum(1 for r in per_win[nm] if r['ruined']):>9}" for nm in names))
    print(f"{'liquidations':<20}" + "".join(
        f"{sum(r['liquidations'] for r in per_win[nm]):>9}" for nm in names))
    b0 = per_win["B0_btc_buy_hold"]
    print(f"{'beats B0 (of ' + str(n_win) + ')':<20}" + "".join(
        f"{sum(1 for i in range(n_win) if per_win[nm][i]['annual'] > b0[i]['annual']):>9}"
        for nm in names))

    # ---------------- G6 held-out ----------------
    print("\n" + "=" * 100)
    print("D. G6 HELD-OUT — identical mechanism and parameters on ETH and SOL")
    print("=" * 100)
    for sym in ("ETH", "SOL"):
        if sym not in symbols:
            print(f"  {sym}: not in universe")
            continue
        j = symbols.index(sym)
        first = int(np.argmax(~np.isnan(closes[:, j])))
        s0 = max(first + WARMUP, offset)
        bench, _ = run(dates, closes, highs, lows, funding, symbols,
                       lambda: _BuyHold(stats, j), lv.SPOT_COST, False, s0, n)
        print(f"\n  {sym} from {dates[s0]}   buy & hold: CAGR {fmt(bench['cagr'])}"
              f"  worstDD {fmt(bench['worst_dd'])}  MAR {bench['mar']:.2f}")
        print(f"  {'mechanism':<34}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}"
              f"{'G1':>5}{'G2':>5}{'liq':>5}")
        ho = {}
        for label, build, cost, use_f in (
            ("SMA-200 1x", lambda: t.SmaRegime(stats, j, 200, 1.0, "sma200_1x"), lv.SPOT_COST, False),
            ("SMA-200 2x", lambda: t.SmaRegime(stats, j, 200, 2.0, "sma200_2x"), lv.PERP_COST, True),
            ("SMA-200 3x", lambda: t.SmaRegime(stats, j, 200, 3.0, "sma200_3x"), lv.PERP_COST, True),
            ("MA cross 50/200 2x", lambda: t.MaCross(stats, j, 50, 200, 2.0, "cross_2x"), lv.PERP_COST, True),
            ("SMA-200 + vol target 40%", lambda: t.VolTargetSma(stats, j, 200, 0.40, 3.0, name="voltgt"), lv.PERP_COST, True),
            ("Donchian-55 2x", lambda: _Donchian(stats, j, 55, 2.0), lv.PERP_COST, True),
        ):
            m, _ = run(dates, closes, highs, lows, funding, symbols, build,
                       cost, use_f, s0, n)
            g1 = m["cagr"] > bench["cagr"]
            g2 = m["mar"] > bench["mar"]
            ho[label] = {**m, "G1": bool(g1), "G2": bool(g2),
                         "bench_cagr": bench["cagr"], "bench_mar": bench["mar"]}
            print(f"  {label:<34}{fmt(m['cagr'])}{fmt(m['worst_dd'])}"
                  f"{m['mar']:>6.2f}{'ok' if g1 else 'no':>5}"
                  f"{'ok' if g2 else 'no':>5}{m['liquidations']:>5}")
        report["held_out"][sym] = {"benchmark": bench, "results": ho}

    # ---------------- G7 parameter surface ----------------
    print("\n" + "=" * 100)
    print("E. G7 PARAMETER SURFACE — lookback +/-50% and leverage +/-1 step")
    print("=" * 100)
    print(f"{'variant':<34}{'CAGR':>9}{'worstDD':>9}{'MAR':>6}{'>K0?':>6}{'liq':>5}")
    grid = []
    for window in (100, 200, 300):
        for lev in (1.0, 2.0, 3.0, 4.0):
            cost = lv.SPOT_COST if lev <= 1.0 else lv.PERP_COST
            use_f = lev > 1.0
            m, _ = run(dates, closes, highs, lows, funding, symbols,
                       (lambda w=window, L=lev: t.SmaRegime(stats, btc, w, L,
                                                            f"sma{w}_{L:g}x")),
                       cost, use_f, offset, n)
            ok = m["cagr"] > K0_CAGR
            grid.append({"window": window, "leverage": lev, **m, "beats_K0": bool(ok)})
            print(f"{'SMA-' + str(window) + ' @ ' + format(lev, 'g') + 'x':<34}"
                  f"{fmt(m['cagr'])}{fmt(m['worst_dd'])}{m['mar']:>6.2f}"
                  f"{'yes' if ok else 'no':>6}{m['liquidations']:>5}")
    flat = sum(1 for g in grid if g["beats_K0"]) / len(grid)
    report["perturbations"]["sma_grid"] = grid
    report["perturbations"]["flat_pct"] = flat
    print(f"\n  {sum(1 for g in grid if g['beats_K0'])}/{len(grid)} "
          f"= {flat:.1%} of the surface beats K0's CAGR   "
          f"(G7 needs >= 60%)")

    # ---------------- verdicts ----------------
    print("\n" + "=" * 100)
    print("F. VERDICT against the criteria declared before the run")
    print("=" * 100)
    print(f"{'candidate':<26}{'G1':>5}{'G2':>5}{'G3':>5}{'G4':>5}{'G5':>5}"
          f"{'G8':>5}   {'note':<28}")
    for nm, label in labels:
        if nm == "B0_btc_buy_hold":
            continue
        m = cont[nm]
        g1 = m["cagr"] > K0_CAGR
        g2 = m["mar"] > K0_MAR
        g3 = report["continuous"][nm].get("G3_edge", -1) > 0
        rows = per_win[nm]
        g4 = (sum(r["liquidations"] for r in rows) == 0
              and not any(r["ruined"] for r in rows))
        g5 = sum(1 for i in range(n_win)
                 if rows[i]["annual"] > b0[i]["annual"]) >= 5
        g8 = m["exposure"] >= 0.30
        v = {"G1": bool(g1), "G2": bool(g2), "G3": bool(g3), "G4": bool(g4),
             "G5": bool(g5), "G8": bool(g8)}
        report["verdicts"][nm] = v
        tick = lambda b: "ok" if b else "NO"
        note = "all pre-declared gates met" if all(v.values()) else \
               "fails " + ",".join(k for k, val in v.items() if not val)
        print(f"{nm:<26}{tick(g1):>5}{tick(g2):>5}{tick(g3):>5}{tick(g4):>5}"
              f"{tick(g5):>5}{tick(g8):>5}   {note:<28}")

    # ---------------- diagnostics (not criteria — they explain the verdict) --
    diagnostics(dates, symbols, closes, highs, lows, funding, stats, btc,
                offset, n, report)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=float)
    print(f"\nraw results -> {os.path.relpath(OUT, os.path.dirname(__file__))}")
    print("G6 (held-out) and G7 (surface) are read from sections D and E above.")
    print("\nNo promotion. No live trading. ValidationGate C1-C7 untouched.")


if __name__ == "__main__":
    main()
