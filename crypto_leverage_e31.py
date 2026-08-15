"""E31 — is there a crypto strategy that makes 2-3x per year, out of sample?

Criteria declared in `docs/CRYPTO_E31_CRITERIA.md` BEFORE this ran. Run:

    python crypto_leverage_e31.py

Read-only backtest over a 33-symbol daily panel with real per-symbol funding,
intrabar liquidation, and delisting handled as an exit. No order path exists.
"""

import json
import os
from datetime import datetime, timezone

import numpy as np

from dynamic_grid import leveraged as lv

DATA = os.path.join(os.path.dirname(__file__), "data", "universe")
WARMUP = 200
YEAR = 365          # crypto trades every day: one window is one real year
INITIAL = 10_000.0
TARGET = 2.00       # +200% per year


def build_panel():
    with open(os.path.join(DATA, "spot_1d.json")) as f:
        raw = json.load(f)
    with open(os.path.join(DATA, "funding_daily.json")) as f:
        fund_raw = json.load(f)

    days = sorted({k[0] for bars in raw.values() for k in bars})
    idx = {d: i for i, d in enumerate(days)}
    symbols = sorted(raw)
    n, m = len(days), len(symbols)
    closes = np.full((n, m), np.nan)
    highs = np.full((n, m), np.nan)
    lows = np.full((n, m), np.nan)
    funding = np.full((n, m), np.nan)

    for j, s in enumerate(symbols):
        for k in raw[s]:
            i = idx[k[0]]
            highs[i, j] = float(k[2])
            lows[i, j] = float(k[3])
            closes[i, j] = float(k[4])
        table = fund_raw.get(s, {})
        for k in raw[s]:
            i = idx[k[0]]
            day = datetime.fromtimestamp(k[0] / 1000, timezone.utc).date().isoformat()
            if day in table:
                funding[i, j] = table[day]

    # symbols with no perp fall back to that day's universe median funding
    med = np.nanmedian(funding, axis=1)
    for j in range(m):
        miss = np.isnan(funding[:, j]) & ~np.isnan(closes[:, j])
        funding[miss, j] = np.where(np.isnan(med[miss]), 0.0, med[miss])

    dates = [datetime.fromtimestamp(d / 1000, timezone.utc).date().isoformat()
             for d in days]
    return dates, symbols, closes, highs, lows, funding


def make_candidates(panel, btc):
    return [
        (lambda: lv.BuyHold(panel, btc), lv.SPOT_COST, False),
        (lambda: lv.LeveredTrend(panel, btc, leverage=3.0), lv.PERP_COST, True),
        (lambda: lv.LeveredTrend(panel, btc, leverage=3.0, two_sided=True),
         lv.PERP_COST, True),
        (lambda: lv.CrossSectionalMomentum(panel, k=5, leverage=1.0),
         lv.SPOT_COST, False),
        (lambda: lv.CrossSectionalMomentum(panel, k=5, leverage=3.0,
                                           name="K4_xsec_mom_top5_3x"),
         lv.PERP_COST, True),
        (lambda: lv.LongShortMomentum(panel, k=5, leverage=2.0),
         lv.PERP_COST, True),
        (lambda: lv.VolTargetTrend(panel, btc), lv.PERP_COST, True),
        (lambda: lv.LeveredBuyHold(panel, btc, leverage=3.0), lv.PERP_COST, True),
    ]


def pct(x, nd=1):
    return "       -" if x is None else f"{x * 100:+8.{nd}f}%"


def main():
    dates, symbols, closes, highs, lows, funding = build_panel()
    panel = lv._Panel(closes, highs, lows, symbols)
    btc = symbols.index("BTC")
    n = len(dates)
    n_win = (n - WARMUP) // YEAR
    offset = n - n_win * YEAR
    print(f"universe: {len(symbols)} symbols, {n} days, "
          f"{dates[0]} -> {dates[-1]}")
    print(f"windows: {n_win} x {YEAR} days, warm-up {offset} days\n")

    names, rows = [], {}
    for build, cost, use_f in make_candidates(panel, btc):
        name = build().name
        names.append(name)
        rows[name] = []
        for w in range(n_win):
            start = offset + w * YEAR
            end = start + YEAR
            sub = lv._Panel(closes[:end], highs[:end], lows[:end], symbols)
            strat = build()
            strat.p = sub
            res = lv.simulate(dates, closes[:end], highs[:end], lows[:end],
                              funding[:end], strat, start=start,
                              initial_equity=INITIAL, cost=cost,
                              use_funding=use_f)
            rows[name].append({
                "window": w + 1,
                "start": dates[start], "end": dates[end - 1],
                "annual": res.annualised,
                "maxDD": res.max_drawdown,
                "robust": res.robust,
                "final": res.final_equity,
                "liquidations": res.liquidations,
                "ruined": res.ruined,
                "mean_gross_leverage": res.mean_gross_leverage,
            })

    print("=" * 118)
    print("ANNUAL RETURN PER OOS WINDOW (each window is one real year, "
          "start 10,000 USDT)")
    print("=" * 118)
    hdr = f"{'window':<26}" + "".join(f"{x.split('_')[0]:>11}" for x in names)
    print(hdr)
    for w in range(n_win):
        line = f"{rows[names[0]][w]['start']} {rows[names[0]][w]['end']}  "
        for nm in names:
            line += f"{rows[nm][w]['annual'] * 100:>10.0f}%"
        print(line)
    print("-" * 118)

    summary = {}
    k7 = rows["K7_btc_buy_hold_3x"]
    k7_med = float(np.median([r["annual"] for r in k7]))
    for nm in names:
        ann = [r["annual"] for r in rows[nm]]
        summary[nm] = {
            "median_annual": float(np.median(ann)),
            "mean_annual": float(np.mean(ann)),
            "windows_hitting_target": sum(1 for a in ann if a >= TARGET),
            "windows_positive": sum(1 for a in ann if a > 0),
            "windows": len(ann),
            "mean_maxDD": float(np.mean([r["maxDD"] for r in rows[nm]])),
            "worst_maxDD": float(max(r["maxDD"] for r in rows[nm])),
            "mean_robust": float(np.mean([r["robust"] for r in rows[nm]])),
            "liquidations": sum(r["liquidations"] for r in rows[nm]),
            "ruined_windows": sum(1 for r in rows[nm] if r["ruined"]),
            "median_ex_best": float(np.median(sorted(ann)[:-1])),
            "mean_gross_leverage": float(np.mean(
                [r["mean_gross_leverage"] for r in rows[nm]])),
        }

    print(f"{'candidate':<26}{'medAnn':>10}{'meanAnn':>10}{'>=200%':>8}"
          f"{'pos':>6}{'meanDD':>9}{'worstDD':>9}{'robust':>10}{'liq':>5}"
          f"{'ruin':>6}{'lev':>6}{'medExBest':>11}")
    for nm in names:
        s = summary[nm]
        print(f"{nm:<26}{pct(s['median_annual'], 0)}{pct(s['mean_annual'], 0)}"
              f"{s['windows_hitting_target']:>5}/{s['windows']:<2}"
              f"{s['windows_positive']:>3}/{s['windows']:<2}"
              f"{pct(s['mean_maxDD'], 0)}{pct(s['worst_maxDD'], 0)}"
              f"{pct(s['mean_robust'], 0)}{s['liquidations']:>5}"
              f"{s['ruined_windows']:>6}{s['mean_gross_leverage']:>6.1f}"
              f"{pct(s['median_ex_best'], 0)}")

    print("\n" + "=" * 118)
    print("VERDICT vs the declared criteria")
    print("=" * 118)
    verdicts = {}
    for nm in names:
        s = summary[nm]
        v = {
            "T1_median_ge_200": s["median_annual"] >= TARGET,
            "T2_half_windows_ge_200":
                s["windows_hitting_target"] / s["windows"] >= 0.5,
            "T3_no_ruin": s["ruined_windows"] == 0,
            "T4_robust_positive": s["mean_robust"] > 0,
            "T5_beats_naive_3x": s["median_annual"] > k7_med,
            "T6_majority_positive": s["windows_positive"] / s["windows"] > 0.5,
            "T7_median_ex_best_ge_200": s["median_ex_best"] >= TARGET,
        }
        v["PASS"] = all(v.values())
        verdicts[nm] = v
        marks = " ".join(("OK " if v[k] else "-- ") + k.split("_")[0]
                         for k in list(v)[:-1])
        print(f"{nm:<26}{marks}   => {'PASS' if v['PASS'] else 'FAIL'}")

    # ----------------------------------------------------------------------
    # Diagnostics. No criterion is attached to either; neither may promote or
    # demote a candidate. They exist to say how much of the result is the
    # market and how much is my own modelling assumption.
    # ----------------------------------------------------------------------
    print("\n" + "=" * 118)
    print("DIAGNOSTIC 1 — how much of the damage is the adversarial wick "
          "assumption? (wicks forgiven, close-to-close only)")
    print("=" * 118)
    bracket = {}
    print(f"{'candidate':<26}{'medAnn strict':>15}{'medAnn forgiving':>18}"
          f"{'liq strict':>12}{'liq forgiving':>15}")
    for build, cost, use_f in make_candidates(panel, btc):
        nm = build().name
        ann, liqs = [], 0
        for w in range(n_win):
            start = offset + w * YEAR
            end = start + YEAR
            strat = build()
            strat.p = lv._Panel(closes[:end], highs[:end], lows[:end], symbols)
            res = lv.simulate(dates, closes[:end], highs[:end], lows[:end],
                              funding[:end], strat, start=start,
                              initial_equity=INITIAL, cost=cost,
                              use_funding=use_f, intrabar_liquidation=False)
            ann.append(res.annualised)
            liqs += res.liquidations
        bracket[nm] = {"median_annual_forgiving": float(np.median(ann)),
                       "liquidations_forgiving": liqs}
        print(f"{nm:<26}{pct(summary[nm]['median_annual'], 0):>15}"
              f"{pct(float(np.median(ann)), 0):>18}"
              f"{summary[nm]['liquidations']:>12}{liqs:>15}")

    print("\n" + "=" * 118)
    print("DIAGNOSTIC 2 — what leverage would BTC trend need to reach "
          "+200%/yr, and what breaks on the way?")
    print("=" * 118)
    sweep = {}
    print(f"{'leverage':>10}{'medAnn':>10}{'meanAnn':>10}{'>=200%':>9}"
          f"{'worstDD':>10}{'liq':>6}{'ruin':>7}{'medExBest':>12}")
    for lev in (1, 2, 3, 4, 5, 6, 8, 10):
        ann, dds, liqs, ruin = [], [], 0, 0
        for w in range(n_win):
            start = offset + w * YEAR
            end = start + YEAR
            strat = lv.LeveredTrend(
                lv._Panel(closes[:end], highs[:end], lows[:end], symbols),
                btc, leverage=float(lev))
            res = lv.simulate(dates, closes[:end], highs[:end], lows[:end],
                              funding[:end], strat, start=start,
                              initial_equity=INITIAL, cost=lv.PERP_COST,
                              use_funding=True)
            ann.append(res.annualised)
            dds.append(res.max_drawdown)
            liqs += res.liquidations
            ruin += int(res.ruined)
        sweep[lev] = {
            "median_annual": float(np.median(ann)),
            "mean_annual": float(np.mean(ann)),
            "windows_hitting_target": sum(1 for a in ann if a >= TARGET),
            "worst_maxDD": float(max(dds)), "liquidations": liqs,
            "ruined_windows": ruin,
            "median_ex_best": float(np.median(sorted(ann)[:-1])),
        }
        s = sweep[lev]
        print(f"{lev:>9}x{pct(s['median_annual'], 0)}{pct(s['mean_annual'], 0)}"
              f"{s['windows_hitting_target']:>6}/{n_win:<2}"
              f"{pct(s['worst_maxDD'], 0)}{s['liquidations']:>6}"
              f"{s['ruined_windows']:>7}{pct(s['median_ex_best'], 0)}")

    out = {
        "experiment": "E31",
        "diagnostic_wick_bracket": bracket,
        "diagnostic_leverage_sweep": sweep,
        "generated": datetime.now(timezone.utc).isoformat(),
        "universe": symbols,
        "data": {"days": n, "first": dates[0], "last": dates[-1],
                 "window_days": YEAR, "windows": n_win},
        "config": {"initial_equity": INITIAL, "target_annual": TARGET,
                   "spot_cost": lv.SPOT_COST, "perp_cost": lv.PERP_COST,
                   "maintenance_margin": lv.MAINTENANCE},
        "per_candidate": rows,
        "summary": summary,
        "verdicts": verdicts,
    }
    path = os.path.join(os.path.dirname(__file__), "docs",
                        "crypto-leverage-e31.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"\nraw output -> {path}")


if __name__ == "__main__":
    main()
